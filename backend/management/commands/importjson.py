# nm.debian.org website backend
#
# Copyright (C) 2012  Enrico Zini <enrico@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.core.management.base import BaseCommand, CommandError
import django.db
from django.conf import settings
import optparse
import sys
import logging
import json
from backend import models as bmodels

log = logging.getLogger(__name__)

class Importer(object):
    def __init__(self):
        self.people_cache_by_email = dict()
        self.people_cache_by_uid = dict()

    def import_person(self, person):
        p = bmodels.Person(
            cn=person["cn"],
            mn=person["mn"],
            sn=person["sn"],
            uid=person["accountname"],
            email=person["mail"],
            status=person["status"])
        p.save()
        self.people_cache_by_email[p.email] = p
        if p.uid: self.people_cache_by_uid[p.uid] = p
        #print "Person:", repr(p)

        if person["am"]:
            src = person["am"]
            am = bmodels.AM(
                person=p,
                slots=src["slots"],
                is_am=src["is_am"],
                is_fd=src["is_fd"],
                is_dam=src["is_dam"])
            am.save()
            print " AM:", repr(am)

    def import_processes(self, person):
        p = self.people_cache_by_email[person["mail"]]
        by_target = dict()
        for proc in person["processes"]:
            if proc["manager"] is None:
                am = None
            else:
                if proc["manager"] not in self.people_cache_by_uid:
                    print proc["manager"], "is not an am"
                m = self.people_cache_by_uid[proc["manager"]]
                if not m.am:
                    print m, "is not an am, but is listed as the am for", p
                am = m.am
            pr = bmodels.Process(
                person=p,
                applying_for=proc["applying_for"],
                progress=proc["progress"],
                manager=am,
            )
            pr.save()
            by_target[pr.applying_for] = pr

        def get_person(uid):
            if uid is None:
                return None
            return self.people_cache_by_uid[uid]

        import re
        re_date = re.compile("^\d+-\d+-\d+$")
        re_datetime = re.compile("^\d+-\d+-\d+ \d+:\d+:\d+$")
        def get_date(s):
            import datetime
            import rfc822
            if re_date.match(s):
                try:
                    return datetime.datetime.strptime(s, "%Y-%m-%d")
                except ValueError:
                    date = rfc822.parsedate(s)
            elif re_datetime.match(s):
                try:
                    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    date = rfc822.parsedate(s)
            else:
                date = rfc822.parsedate(s)

            if date is None:
                return None
            return datetime.datetime(*date)

        for log in person["log"]:
            if log["applying_for"] not in by_target:
                print log["applying_for"], "not in", by_target.keys(), "for", p
            if log["logdate"] is None:
                print "Skipping '%s' log entry for %s because of a missing date" % (log["logtext"], repr(p))
                continue
            # FIXME: move this to export
            date = get_date(log["logdate"])
            if date is None:
                print "Skipping '%s' log entry: cannot parse date: %s" % (log["logtext"], log["logdate"])
                continue
            l = bmodels.Log(
                changed_by=get_person(log["changed_by"]),
                process=by_target[log["applying_for"]],
                progress=log["logtype"],
                logdate=log["logdate"],
                logtext=log["logtext"],
            )
            l.save()


class Command(BaseCommand):
    help = 'Import a JSON database dump'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
    )

    def handle(self, *fnames, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        if not fnames:
            print >>sys.stderr, "please provide a JSON dump file name"
            sys.exit(1)

        with open(fnames[0]) as fd:
            people = json.load(fd)

        importer = Importer()
        for k, v in people.iteritems():
            importer.import_person(v)
        for k, v in people.iteritems():
            importer.import_processes(v)

        #log.info("%d patch(es) applied", len(fnames))
