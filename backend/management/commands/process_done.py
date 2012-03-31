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
    help = 'Handle completion of a process'
    args = "url-or-process_key"

    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("-m", "--message", action="store", help="Message to use as the progress log entry"),
        optparse.make_option("-d", "--date", action="store", help="Date/time when the status change happened"),
        optparse.make_option("--who", action="store", help="Who performed the change we are recording"),
    )

    def handle(self, process_key, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        if "/" in process_key:
            process_key = process_key.rsplit("/", 1)[1]

        # Validate input
        pr = bmodels.Process.lookup(process_key)
        if pr is None:
            log.error("Process with key %s does not exist", process_key)
            sys.exit(1)

        if not pr.is_active:
            log.error("Process %s is not active", process_key)
            sys.exit(1)

        msg = opts["message"]
        if not msg:
            msg = None

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


        # Perform the change

        # Add a log entry
        l = bmodels.Log(
            changed_by=who,
            process=pr,
            progress=const.PROGRESS_DONE,
            logdate=dt,
            logtext=msg
        )
        l.save()

        # Mark the process as done
        pr.progress = const.PROGRESS_DONE
        pr.is_active = False
        pr.save()

        # Change the person status
        pr.person.status = pr.applying_for
        pr.person.status_changed = dt
        pr.person.save()
