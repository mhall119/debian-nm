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
import re
import logging
import datetime
from backend import models as bmodels
from backend import const

log = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Change the fingerprint of a person'
    args = "person_key new_fpr"

    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
    )

    def handle(self, person_key, fpr, **opts):
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

        fpr = fpr.replace(" ", "")
        fpr = fpr.upper()

        if len(fpr) != 40:
            log.error("Fingerprint %s is not 40 characters long", fpr)
            sys.exit(1)

        if not re.match("^[0-9A-F]+", fpr):
            log.error("Fingerprint %s contains invalid characters", fpr)
            sys.exit(1)

        p.fpr = fpr
        p.save()

        # TODO: log something somewhere?
