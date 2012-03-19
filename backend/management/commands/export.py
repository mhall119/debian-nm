# coding: utf-8

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
from django.contrib.auth.models import User
import optparse
import sys
import logging
import json
import random
from backend import models as bmodels

log = logging.getLogger(__name__)

MOCK_FD_COMMENTS = [
    "Cannot get GPG signatures because of extremely sensitive teeth",
    "Only has internet connection on days which are prime numbers",
    "Is a werewolf: warn AM to ignore replies when moon is full",
    "Is a vampire: warn AM not to invite him/her into their home",
    "Is a daemon: if unresponsive, contact Enrico for details about summoning ritual",
]

MOCK_LOGTEXTS = [
    "ok", "hmm", "meh", "asdf", "moo", "...", u"üñįç♥ḋə"
]

class Command(BaseCommand):
    help = 'Export all the NM database'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("--full", action="store_true", dest="quiet", default=None, help="Also export privacy-sensitive information"),
    )

    def handle(self, quiet=False, full=False, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if quiet:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        fd = list(bmodels.Person.objects.filter(am__is_fd=True))

        people = dict()
        for idx, p in enumerate(bmodels.Person.objects.all()):
            if idx and idx % 300 == 0:
                log.info("%d people read", idx)

            # Person details
            ep = dict(
                key=p.lookup_key,
                cn=p.cn,
                mn=p.mn,
                sn=p.sn,
                email=p.email,
                uid=p.uid,
                fpr=p.fpr,
                status=p.status,
                status_changed=p.status_changed,
                created=p.created,
                fd_comment=None,
                am=None,
                processes=[],
            )

            people[ep["key"]] = ep

            if full:
                ep["fd_comment"] = p.fd_comment
            else:
                if random.randint(1, 100) < 20:
                    ep["fd_comment"] = random.choice(MOCK_FD_COMMENTS)

            # AM details
            am = p.am_or_none
            if am:
                ep["am"] = dict(
                    slots=am.slots,
                    is_am=am.is_am,
                    is_fd=am.is_fd,
                    is_dam=am.is_dam,
                    is_am_ctte=am.is_am_ctte,
                    created=a.created)

            # Process details
            for pr in p.processes.all():
                epr = dict(
                    applying_for=pr.applying_for,
                    progress=pr.progress,
                    is_active=pr.is_active,
                    manager=None,
                    advocates=[],
                    log=[],
                )
                # Also get a list of actors who can be used for mock logging later
                if pr.manager:
                    epr["manager"] = pr.manager.lookup_key
                    actors = [pr.manager.person] + fd
                else:
                    actors = fd

                for a in pr.advocates.all():
                    epr["advocates"].append(a.lookup_key)

                # Log details
                last_progress = None
                for l in pr.log.all().order_by("logdate"):
                    if not full and last_progress == l.progress:
                        # Consolidate consecutive entries to match simplification
                        # done by public interface
                        continue

                    el = dict(
                        changed_by=None,
                        progress=l.progress,
                        logdate=l.logdate,
                        logtext=None)

                    if full:
                        if l.changed_by:
                            el["changed_by"] = l.changed_by.lookup_key
                        el["logtext"] = l.logtext
                    else:
                        if l.changed_by:
                            el["changed_by"] = random.choice(actors)
                        # TODO: logtext: random
                        pass

                    epr["log"].append(el)

                    last_progress = l.progress

        class Serializer(json.JSONEncoder):
            def default(self, o):
                if hasattr(o, "strftime"):
                    return o.strftime("%Y-%m-%d %H:%M:%S")
                return JSONEncoder.default(self, o)

        json.dump(people, sys.stdout, cls=Serializer, indent=2)

