# nm.debian.org website maintenance
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
import ldap
from backend import models as bmodels
from backend import const
import keyring.models as kmodels

log = logging.getLogger(__name__)

class Importer(object):
    def __init__(self):
        self.people_cache_by_email = dict()
        self.people_cache_by_uid = dict()
        self.todo_advocates = dict()

        log.info("Importing dm keyring...")
        self.dm = frozenset(kmodels.list_dm())
        log.info("Importing dd_u keyring...")
        self.dd_u = frozenset(kmodels.list_dd_u())
        log.info("Importing dd_nu keyring...")
        self.dd_nu = frozenset(kmodels.list_dd_nu())
        log.info("Importing emeritus_dd keyring...")
        self.emeritus_dd = frozenset(kmodels.list_emeritus_dd())
        log.info("Importing removed_dd keyring...")
        self.removed_dd = frozenset(kmodels.list_removed_dd())

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
            self.todo_advocates[pr.id] = proc["advocates"]
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

        for logentry in person["log"]:
            if logentry["applying_for"] not in by_target:
                print logentry["applying_for"], "not in", by_target.keys(), "for", p
            if logentry["logdate"] is None:
                print "Skipping '%s' log entry for %s because of a missing date" % (logentry["logtext"], repr(p))
                continue
            # FIXME: move this to export
            date = get_date(logentry["logdate"])
            if date is None:
                print "Skipping '%s' log entry: cannot parse date: %s" % (logentry["logtext"], logentry["logdate"])
                continue
            l = bmodels.Log(
                changed_by=get_person(logentry["changed_by"]),
                process=by_target[logentry["applying_for"]],
                progress=logentry["logtype"],
                logdate=date,
                logtext=logentry["logtext"],
            )
            l.save()

    def import_ldap(self, server):
        """
        Perform initial data import from LDAP

        Imports cn, sn, nm, fpr, email for DDs and guest accounts.

        Does not set status, that will be taken from keyrings
        """
        #  enrico> Hi. Can you give me an official procedure to check if one is a DD from LDAP info?
        # @weasel> enrico: not really, that's your decision.
        # @weasel> enrico: for one, you can filter on gid 800.  and then filter for having a
        #          fingerprint.  that's usually right
        #  enrico> weasel: what are person accounts without fingerprints for?
        # @weasel> people who screwed up their keys
        # @weasel> we've had that on occasion
        #  enrico> weasel: ack
        # @weasel> enrico: and of course retired people
        # @weasel> we try to set ldap's account status nowadays, but no idea if
        #          that applies to all that ever retired

        search_base = "dc=debian,dc=org"
        l = ldap.initialize(server)
        l.simple_bind_s("","")
        for dn, attrs in l.search_s(search_base, ldap.SCOPE_SUBTREE, "objectclass=inetOrgPerson"):
            def get_field(f):
                if f not in attrs:
                    return None
                f = attrs[f]
                if not f:
                    return None
                return f[0]

            # Try to match the person using uid
            uid = get_field("uid")
            fpr = get_field("keyFingerPrint"),
            try:
                person = bmodels.Person.objects.get(uid=uid)
                person.fpr = fpr
                if person.status == const.STATUS_MM:
                    person.status = const.STATUS_MM_GA
                person.save()
                continue
            except bmodels.Person.DoesNotExist:
                pass

            # Try to match the person using emails
            try:
                person = bmodels.Person.objects.get(email=uid + "@debian.org")
                person.uid = uid
                person.fpr = fpr
                if person.status == const.STATUS_MM:
                    person.status = const.STATUS_MM_GA,
                person.save()
                continue
            except bmodels.Person.DoesNotExist:
                pass

            email = get_field("emailForward")
            try:
                person = bmodels.Person.objects.get(email=email)
                person.uid = uid
                person.fpr = fpr
                if person.status == const.STATUS_MM:
                    person.status = const.STATUS_MM_GA,
                person.save()
                continue
            except bmodels.Person.DoesNotExist:
                pass

            person = bmodels.Person(
                cn=get_field("cn"),
                mn=get_field("mn"),
                sn=get_field("sn"),
                fpr=fpr,
                uid=uid,
                # Default to MM_GA: if they are in LDAP, they have at least a
                # guest account
                status=const.STATUS_MM_GA,
            )
            if get_field("gidNumber") == '800':
                person.email = uid + "@debian.org"
            else:
                person.email = email
            if person.email is None:
                log.warning("UID %s from LDAP does not look like a DD and has no email address: skipping import as Person", uid)
                continue
            person.save()


    def import_advocates(self):
        # Clear the uid cache
        self.people_cache_by_uid = dict()
        for id, advocates in self.todo_advocates.iteritems():
            proc = bmodels.Process.objects.get(id=id)
            for adv in advocates:
                a = self.people_cache_by_uid.get(adv, None)
                if a is None:
                    try:
                        a = bmodels.Person.objects.get(uid=adv)
                        self.people_cache_by_uid[adv] = a
                    except bmodels.Person.DoesNotExist:
                        log.warning("advocate %s not found: skipping the DB association and leaving it just in the logs", adv)
                        continue
                proc.advocates.add(a)

    def import_keyrings(self):
        """
        Perform initial import from keyring.d.o

        Detects status by checking what keyring contains the fingerprint
        """
        for person in bmodels.Person.objects.all():
            if not person.fpr:
                log.info("%s/%s has no fingerprint: skipped", person.uid, person.email)
                continue

            old_status = person.status
            if person.fpr in self.dm:
                # If we have a fingerprint in the Person during the initial import,
                # it means they come from LDAP, so they have a guest account
                person.status = const.STATUS_DM_GA
            if person.fpr in self.dd_u:
                person.status = const.STATUS_DD_U
            if person.fpr in self.dd_nu:
                person.status = const.STATUS_DD_NU
            if person.fpr in self.emeritus_dd:
                person.status = const.STATUS_EMERITUS_DD
            if person.fpr in self.removed_dd:
                person.status = const.STATUS_REMOVED_DD

            if old_status != person.status:
                log.info("%s: status changed from %s to %s", person.uid, old_status, person.status)
                person.save()

class Command(BaseCommand):
    help = 'Import a JSON database dump'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("--ldap", action="store", default="ldap://db.debian.org", help="LDAP server to use. Default: %default"),
        #l = ldap.initialize("ldap://localhost:3389")
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
        importer.import_ldap(opts["ldap"])
        importer.import_advocates()
        importer.import_keyrings()

        #log.info("%d patch(es) applied", len(fnames))
