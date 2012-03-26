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

class Command(BaseCommand):
    help = 'Change information about a person (use an empty string to set to NULL)'
    args = "person_key"

    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("--cn", action="store", help="Set first name"),
        optparse.make_option("--mn", action="store", help="Set middle name"),
        optparse.make_option("--sn", action="store", help="Set last name"),
        optparse.make_option("--email", action="store", help="Set email address"),
        optparse.make_option("--uid", action="store", help="Set Debian uid"),
        optparse.make_option("--fpr", action="store", help="Set OpenPGP key fingerprint"),
        optparse.make_option("--status", action="store", help="Set status"),
        optparse.make_option("--status-changed", action="store", help="Set date when the status last changed"),
        optparse.make_option("--fd-comment", action="store", help="Set FD comment"),
        optparse.make_option("--created", action="store", help="Set date when the person record was created"),
    )

    def handle(self, person_key, **opts):
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

        for field in ("cn", "mn", "sn", "email", "uid", "fpr", "status", "fd_comment"):
            val = opts[field]
            if val is None: continue
            if val == "": val = None
            setattr(p, field, val)
        for field in ("status_changed", "created"):
            val = opts[field]
            if val is None: continue
            val = parse_datetime(val)
            setattr(p, field, val)

        p.save()
