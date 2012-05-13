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
from django.db import connection, transaction
from django.conf import settings
import optparse
import sys
import os
import logging
import datetime
from backend import models as bmodels
from backend import const

log = logging.getLogger(__name__)

def parse_datetime(s):
    if s is None: return None
    s = s.strip()
    if len(s) == 10:
        return datetime.datetime.strptime(s, "%Y-%m-%d")
    else:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

def current_user():
    """
    Get the Person object for the user running this command
    """
    user = os.environ.get("SUDO_USER", None)
    if user is None:
        user = os.environ.get("USER", None)
    return bmodels.Person.lookup(user)

class Command(BaseCommand):
    help = 'Change the state of a person'
    args = "person_key status -m message"

    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("-m", "--message", action="store", help="Message to use as the progress log entry"),
        optparse.make_option("-d", "--date", action="store", help="Date/time when the status change happened"),
        optparse.make_option("--who", action="store", help="Who performed the change we are recording"),
    )

    def handle(self, person_key, status, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        # Validate input
        p = bmodels.Person.lookup(person_key)
        if p is None:
            log.error("Person with key %s does not exist", person_key)
            sys.exit(1)

        if status not in (x.tag for x in const.ALL_STATUS):
            log.error("Status %s is not valid", status)
            sys.exit(1)

        msg = opts["message"]
        if not msg:
            log.error("Please provide a log message using -m")
            sys.exit(1)

        now = datetime.datetime.utcnow()
        dt = parse_datetime(opts["date"])
        if not dt:
            dt = now

        user = current_user()

        who = opts["who"]
        if who is None:
            who = user
        elif who == "":
            who = None
        else:
            who = bmodels.Person.lookup(who)

        # Ensure we actually change something
        if p.status == status:
            log.error("%s already has status %s", p.fullname, status)
            sys.exit(1)

        # Ensure no process is open
        if p.active_processes:
            log.error("%s already has an active process, to become %s", p.fullname, ", ".join(x.active_processes.applying_for for x in p.active_processes))
            sys.exit(1)

        # Perform the status change

        # Create a process
        pr = bmodels.Process(
            person=p,
            applying_as=p.status,
            applying_for=status,
            progress=const.PROGRESS_DONE,
            is_active=False)
        pr.save()

        # Add a log entry with the custom message
        l = bmodels.Log(
            changed_by=who,
            process=pr,
            progress=const.PROGRESS_DAM_OK,
            logdate=dt,
            logtext=msg
        )
        l.save()

        # Add a log entry about when the change really happened
        l = bmodels.Log(
            changed_by=user,
            process=pr,
            progress=const.PROGRESS_DONE,
            logdate=now,
            logtext="Status change performed via command line management procedure",
        )
        l.save()

        # Change the status itself
        p.status = status
        p.status_changed = dt
        p.save()
