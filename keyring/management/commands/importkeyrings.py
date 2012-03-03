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
import ldap
import logging
import json
from backend import models as bmodels
from backend import const
import keyring.models as kmodels

log = logging.getLogger(__name__)

class Importer(object):
    """
    Perform initial import from keyring.d.o

    Detects status by checking what keyring contains the fingerprint
    """
    def __init__(self):
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

    def do_import(self):
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
    help = 'Import people and changes from LDAP'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
    )

    def handle(self, *fnames, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        importer = Importer()
        importer.do_import()

        #log.info("%d patch(es) applied", len(fnames))
