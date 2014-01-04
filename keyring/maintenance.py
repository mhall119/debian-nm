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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django_maintenance import MaintenanceTask
from django.conf import settings
from backend.maintenance import MakeLink, Inconsistencies
import backend.models as bmodels
from backend import const
from . import models as kmodels
import os
import os.path
import time
import shutil
import logging

log = logging.getLogger(__name__)

KEYRINGS_TMPDIR = getattr(settings, "KEYRINGS_TMPDIR", "/srv/keyring.debian.org/data/tmp_keyrings")

class Keyrings(MaintenanceTask):
    """
    Load keyrings
    """
    NAME = "keyrings"

    def run(self):
        log.info("%s: Importing dm keyring...", self.IDENTIFIER)
        self.dm = frozenset(kmodels.list_dm())
        log.info("%s: Importing dd_u keyring...", self.IDENTIFIER)
        self.dd_u = frozenset(kmodels.list_dd_u())
        log.info("%s: Importing dd_nu keyring...", self.IDENTIFIER)
        self.dd_nu = frozenset(kmodels.list_dd_nu())
        log.info("%s: Importing emeritus_dd keyring...", self.IDENTIFIER)
        self.emeritus_dd = frozenset(kmodels.list_emeritus_dd())
        log.info("%s: Importing removed_dd keyring...", self.IDENTIFIER)
        self.removed_dd = frozenset(kmodels.list_removed_dd())

class CheckKeyringConsistency(MaintenanceTask):
    """
    Show entries that do not match between keyrings and our DB
    """
    DEPENDS = [Keyrings, MakeLink, Inconsistencies]

    def run(self):
        # Prefetch people and index them by fingerprint
        people_by_fpr = dict()
        for p in bmodels.Person.objects.all():
            if p.fpr is None: continue
            people_by_fpr[p.fpr] = p

        keyring_by_status = {
            const.STATUS_DM: self.maint.keyrings.dm,
            const.STATUS_DM_GA: self.maint.keyrings.dm,
            const.STATUS_DD_U: self.maint.keyrings.dd_u,
            const.STATUS_DD_NU: self.maint.keyrings.dd_nu,
            const.STATUS_EMERITUS_DD: self.maint.keyrings.emeritus_dd,
            const.STATUS_REMOVED_DD: self.maint.keyrings.removed_dd,
        }

        self.count = 0

        # Check the fingerprints on our DB
        for fpr, p in sorted(people_by_fpr.iteritems(), key=lambda x:x[1].uid):
            keyring = keyring_by_status.get(p.status)
            # Skip the statuses we currently can't check for
            if keyring is None: continue
            # Skip those that are ok
            if fpr in keyring: continue
            # Look for the key in other keyrings
            found = False
            for status, keyring in keyring_by_status.iteritems():
                if fpr in keyring:
                    self.maint.inconsistencies.log_person(self, p,
                                                                "has status {} but is in {} keyring (fpr: {})".format(p.status, status, fpr),
                                                                keyring_status=status)
                    self.count += 1
                    found = True
                    break
            if not found and p.status != const.STATUS_REMOVED_DD:
                self.maint.inconsistencies.log_person(self, p,
                                                      "has status {} but is not in any keyring (fpr: {})".format(p.status, fpr),
                                                      keyring_status=None)
                self.count += 1

        # Spot fingerprints not in our DB
        for status, keyring in keyring_by_status.iteritems():
            # TODO: not quite sure how to handle the removed_dd keyring, until I
            #       know what exactly is in there
            if status == const.STATUS_REMOVED_DD: continue
            for fpr in keyring:
                if fpr not in people_by_fpr:
                    self.maint.inconsistencies.log_fingerprint(self, fpr,
                                                               "is in {} keyring but not in our db".format(status),
                                                               keyring_status=status)
                    self.count += 1

    def log_stats(self):
        log.info("%s: %d mismatches between keyring and nm.debian.org databases",
                    self.IDENTIFIER, self.count)

    #@transaction.commit_on_success
    #def compute_display_names_from_keyring(self, **kw):
    #    """
    #    Update Person.display_name with data from keyrings
    #    """
    #    # Current display names
    #    info = dict()
    #    for p in bmodels.Person.objects.all():
    #        if not p.fpr: continue
    #        info[p.fpr] = dict(
    #            cur=p.fullname,
    #            pri=None, # Primary uid
    #            deb=None, # Debian uid
    #        )
    #    log.info("%d entries with fingerprints", len(info))

    #    cur_fpr = None
    #    cur_info = None
    #    for keyring in "debian-keyring.gpg", "debian-maintainers.gpg", "debian-nonupload.gpg", "emeritus-keyring.gpg", "removed-keys.gpg":
    #        count = 0
    #        for fpr, u in kmodels.uid_info(keyring):
    #            if fpr != cur_fpr:
    #                cur_info = info.get(fpr, None)
    #                cur_fpr = fpr
    #                if cur_info is not None:
    #                    # Save primary uid
    #                    cur_info["pri"] = u.name

    #            if cur_info is not None and u.email is not None and u.email.endswith("@debian.org"):
    #                cur_info["deb"] = u.name
    #            count += 1
    #        log.info("%s: %d uids checked...", keyring, count)

    #    for fpr, i in info.iteritems():
    #        if not i["pri"] and not i["deb"]: continue
    #        if i["pri"]:
    #            cand = i["pri"]
    #        else:
    #            cand = i["deb"]
    #        if i["cur"] != cand:
    #            log.info("%s: %s %r != %r", keyring, fpr, i["cur"], cand)

class CleanUserKeyrings(MaintenanceTask):
    """
    Remove old user keyrings
    """
    def run(self):
        # Delete everything older than three days ago
        threshold = time.time() - 86400 * 3
        for fn in os.listdir(KEYRINGS_TMPDIR):
            if fn.startswith("."): continue
            pn = os.path.join(KEYRINGS_TMPDIR, fn)
            if not os.path.isdir(pn): continue
            if os.path.getmtime(pn) > threshold: continue

            log.info("%s: removing old user keyring %s", self.IDENTIFIER, pn)
            shutil.rmtree(pn)
