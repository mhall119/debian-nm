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
import re
import datetime
import logging

log = logging.getLogger(__name__)

KEYRINGS_TMPDIR = getattr(settings, "KEYRINGS_TMPDIR", "/srv/keyring.debian.org/data/tmp_keyrings")

class Keyrings(MaintenanceTask):
    """
    Load keyrings
    """
    NAME = "keyrings"

    KEYID_LEN = 16

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

        # Keep an index mapping key IDs to fingerprints and keyring type
        self.by_fpr = {}
        self.by_keyid = {}
        duplicate_fprs = []
        duplicate_keyids = []
        for t in ("dm", "dd_u", "dd_nu", "emeritus_dd", "removed_dd"):
            for fpr in getattr(self, t):
                record = (fpr, t)

                # Index by fingerprint
                old_rec = self.by_fpr.get(fpr, None)
                if old_rec is not None:
                    log.warning("%s: duplicate fingerprint %s, found in %s and in %s", self.IDENTIFIER, fpr, old_rec[1], t)
                    duplicate_fprs.append(fpr)
                else:
                    self.by_fpr[fpr] = record

                # Index by key id
                keyid = fpr[-self.KEYID_LEN:]
                old_rec = self.by_keyid.get(keyid, None)
                if old_rec is not None:
                    log.warning("%s: duplicate key id %s, found in %s and in %s", self.IDENTIFIER, keyid, old_rec[1], t)
                    duplicate_keyids.append(keyid)
                else:
                    self.by_keyid[keyid] = record

        # Ignore duplicate fingerprints for lookup purposes
        for fpr in duplicate_fprs:
            del self.by_fpr[fpr]
        for keyid in duplicate_keyids:
            del self.by_keyid[keyid]

    def resolve_fpr(self, fpr):
        """
        Return the keyring type given a fingerprint, or None if the fingerprint
        is unknown
        """
        rec = self.by_fpr.get(fpr, None)
        if rec is None:
            return None
        return rec[1]

    def resolve_keyid(self, keyid):
        """
        Return the (fingerprint, keyring type) given a key id, or (None, None)
        if the key id is unknown
        """
        rec = self.by_keyid.get(keyid, None)
        if rec is None:
            return None, None
        return rec


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
                                                                "has status {} but is in {} keyring".format(p.status, status),
                                                                keyring_status=status)
                    self.count += 1
                    found = True
                    break
            if not found and p.status != const.STATUS_REMOVED_DD:
                self.maint.inconsistencies.log_person(self, p,
                                                      "has status {} but is not in any keyring".format(p.status),
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

def keyring_log_matcher(regexp, **kw):
    def decorator(f):
        f.re = re.compile(regexp)
        for k, v in kw.iteritems():
            setattr(f, k, v)
        return f
    return decorator

class CheckKeyringLogs(MaintenanceTask):
    """
    Show entries that do not match between keyrings and our DB
    """
    DEPENDS = [Inconsistencies, Keyrings]

    def person_for_key_id(self, kid):
        try:
            return bmodels.Person.objects.get(fpr__endswith=kid)
        except bmodels.Person.DoesNotExist:
            return None

    def rturl(self, num):
        return "https://rt.debian.org/" + num

    def _ann_fpr(self, d, rt, fpr, log, **kw):
        if rt is not None:
            self.maint.inconsistencies.annotate_fingerprint(self, fpr,
                                                    "{}, RT #{}".format(log, rt),
                                                    keyring_rt=rt,
                                                    keyring_log_date=d.strftime("%Y%m%d %H%M%S"),
                                                    **kw)
        else:
            self.maint.inconsistencies.annotate_fingerprint(self, fpr, log,
                                                    keyring_log_date=d.strftime("%Y%m%d %H%M%S"),
                                                    **kw)

    def _ann_person(self, d, rt, person, log, **kw):
        if rt is not None:
            self.maint.inconsistencies.annotate_person(self, person,
                                                    "{}, RT #{}".format(log, rt),
                                                    keyring_rt=rt,
                                                    keyring_log_date=d.strftime("%Y%m%d %H%M%S"),
                                                    **kw)
        else:
            self.maint.inconsistencies.annotate_person(self, person, log,
                                                    keyring_log_date=d.strftime("%Y%m%d %H%M%S"),
                                                    **kw)

    @keyring_log_matcher(r"^\s*\*\s+Add new DM key 0x(?P<key>[0-9A-F]+) \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    def do_new_dm(self, d, key, rt):
        p = self.person_for_key_id(key)
        if p is None:
            fpr, ktype = self.maint.keyrings.resolve_keyid(key)
            if fpr is None:
                log.info("%s: unknown key ID %s found in log for %s RT#ss", self.IDENTIFIER, key, d, rt)
            else:
                # TODO: connect to RT and try to fetch person details
                self._ann_fpr(d, rt, fpr, "keyring logs report a new DM",
                              keyring_status=const.STATUS_DM,
                              fix_cmdline="./manage.py dm_from_rt {}".format(rt))
        elif p.status in (const.STATUS_DM, const.STATUS_DM_GA):
            #print("# %s goes from %s to DM (already known in the database) %s" % (p.lookup_key, p.status, self.rturl(rt)))
            pass # Already a DM
        else:
            if p.status == const.STATUS_MM_GA:
                new_status = const.STATUS_DM_GA
            else:
                new_status = const.STATUS_DM
            self._ann_person(d, rt, p, "keyring logs report change from {} to {}".format(p.status, new_status),
                             keyring_status=new_status,
                             fix_cmdline="./manage.py change_status {} {} --date='{}' --message='imported from keyring changelog, RT #{}'".format(
                                 p.lookup_key, new_status, d.strftime("%Y-%m-%d %H:%M:%S"), rt))

    @keyring_log_matcher(r"^\s*\*\s+Add new DD key 0x(?P<key>[0-9A-F]+) \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    def do_new_dd(self, d, key, rt):
        p = self.person_for_key_id(key)
        if p is None:
            fpr, ktype = self.maint.keyrings.resolve_keyid(key)
            self._ann_fpr(d, rt, fpr, "keyring logs report a new DD, with no known record in our database", keyring_status=ktype)
            #print("! New DD %s %s (no account before??)" % (key, self.rturl(rt)))
        elif p.status == const.STATUS_DD_U:
            #print("# %s goes from %s to DD (already known in the database) %s" % (p.lookup_key, p.status, self.rturl(rt)))
            pass # Already a DD
        else:
            self._ann_person(d, rt, p, "keyring logs report change from {} to {}".format(p.status, const.STATUS_DD_U),
                             keyring_status=const.STATUS_DD_U,
                             fix_cmdline="./manage.py change_status {} {} --date='{}' --message='imported from keyring changelog, RT #{}'".format(
                                 p.lookup_key, const.STATUS_DD_U, d.strftime("%Y-%m-%d %H:%M:%S"), rt))

    @keyring_log_matcher(r"^\s*\*\s+Move 0x(?P<key>[0-9A-F]+) to [Ee]meritus \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    def do_new_em(self, d, key, rt):
        p = self.person_for_key_id(key)
        if p is None:
            fpr, ktype = self.maint.keyrings.resolve_keyid(key)
            self._ann_fpr(d, rt, fpr, "keyring logs report a new emeritus DD, with no known record in our database", keyring_status=ktype)
            #print("! New Emeritus DD %s %s (no account before??)" % (key, self.rturl(rt)))
        elif p.status == const.STATUS_EMERITUS_DD:
            # print("# %s goes from %s to emeritus DD (already known in the database) %s" % (p.lookup_key, p.status, self.rturl(rt)))
            pass # Already emeritus
        else:
            self._ann_person(d, rt, p, "keyring logs report change from {} to {}".format(p.status, const.STATUS_EMERITUS_DD),
                             keyring_status=const.STATUS_EMERITUS_DD,
                             fix_cmdline="./manage.py change_status {} {} --date='{}' --message='imported from keyring changelog, RT {}'".format(
                                 p.lookup_key, const.STATUS_EMERITUS_DD, d.strftime("%Y-%m-%d %H:%M:%S"), rt))

    @keyring_log_matcher(r"^\s*\*\s+Move 0x(?P<key>[0-9A-F]+)\s+\([^)]+\) to removed keyring\s+\(RT #(?P<rt>\d+)")
    def do_new_rem(self, d, key, rt):
        p = self.person_for_key_id(key)
        if p is None:
            fpr, ktype = self.maint.keyrings.resolve_keyid(key)
            self._ann_fpr(d, rt, fpr, "keyring logs report a new removed DD, with no known record in our database", keyring_status=ktype)
            #print("! New removed key %s %s (no account before??)" % (key, self.rturl(rt)))
        else:
            #print("! %s key %s moved to removed keyring %s" % (p.lookup_key, key, self.rturl(rt)))
            self._ann_person(d, rt, p, "keyring logs report change from {} to removed".format(p.status, const.STATUS_REMOVED_DD), keyring_status=const.STATUS_REMOVED_DD)

    @keyring_log_matcher(r"^\s*\*\s+Replace(?: key)? 0x(?P<key1>[0-9A-F]+) with 0x(?P<key2>[0-9A-F]+) \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    def do_replace(self, d, key1, key2, rt):
        p1 = self.person_for_key_id(key1)
        p2 = self.person_for_key_id(key2)
        if p1 is None and p2 is None:
            # No before or after match with our records
            fpr1, ktype1 = self.maint.keyrings.resolve_keyid(key1)
            fpr2, ktype2 = self.maint.keyrings.resolve_keyid(key2)
            if fpr1 is not None:
                if fpr2 is not None:
                    # Before and after keyrings known
                    if ktype1 != ktype2:
                        # Keyring moved
                        self._ann_fpr(d, rt, fpr1,
                             "keyring logs report that this key has been replaced with {}, and moved from the {} to the {} keyring".format(fpr2, ktype1, ktype2),
                             keyring_status=ktype2,
                             keyring_fpr=fpr2)
                    else:
                        # Same keyring
                        self._ann_fpr(d, rt, fpr1,
                             "keyring logs report that this key has been replaced with {} in the {} keyring".format(fpr2, ktype2),
                             keyring_status=ktype2,
                             keyring_fpr=fpr2)
                else:
                    # Only 'before' keyring known
                    self._ann_fpr(self, fpr1,
                         "keyring logs report that this key has been replaced with unkonwn key {}".format(key2),
                         keyring_status=ktype1)
            else:
                if fpr2 is not None:
                    # Only 'after' keyring known
                    self._ann_fpr(self, fpr2,
                         "keyring logs report that this key has replaced unknown key {} in the {} keyring".format(key1, ktype2),
                         keyring_status=ktype2)
                else:
                    # Neither before nor after are known
                    pass
                    # print("! Replaced %s with %s (none of which are in the database!) %s" % (key1, key2, self.rturl(rt)))
        elif p1 is None and p2 is not None:
            #self.maint.inconsistencies.annotate_person(self, p,
            #                                            "keyring logs report key change from {} to {}, RT#{}".format(key1, key2, rt),
            #                                            keyring_rt=rt,
            #                                            keyring_log_date=d,
            #                                            keyring_fpr=key2)
            #print("# Replaced %s with %s (already done in the database) %s" % (key1, key2, self.rturl(rt)))
            pass # Already known
        elif p1 is not None and p2 is None:
            fpr, ktype = self.maint.keyrings.resolve_keyid(key2)
            if fpr is None:
                self._ann_person(d, rt, p1, "key changed to unknown key {}".format(key2))
                # print("! %s replaced key %s with %s but could not find %s in keyrings %s" % (p.lookup_key, key1, key2, key2, self.rturl(rt)))
            else:
                self._ann_person(d, rt, p1, "key changed to {}".format(fpr),
                                 keyring_fpr=fpr,
                                 keyring_status=ktype,
                                 fix_cmdline="./manage.py change_key {} {}".format(p1.lookup_key, fpr))
        else:
            # This is very weird, so we log instead of just annotating
            for p in (p1, p2):
                self.maint.inconsistencies.log_person(self, p,
                                                        "keyring logs report key change from {} to {}, but the keys belong to two different people, {} and {}. RT #{}".format(key1, key2, p1.lookup_key, p2.lookup_key, rt),
                                                        keyring_rt=rt,
                                                        keyring_log_date=d.strftime("%Y%m%d %H%M%S"))

    @keyring_log_matcher(r"^\s*\*\s+(?P<line>.*0x[0-9A-F]+.+)", fallback=True)
    def do_fallback(self, d, line):
        # We get a line that contains at least one key id
        keys = re.findall(r"0x(?P<key>[0-9A-F]+)", line)
        rtmo = re.search(r"RT #(?P<rt>\d+)", line)
        if rtmo:
            rt = int(rtmo.group("rt"))
        else:
            rt = None

        # Log the line in all relevant bits found
        for key in keys:
            p = self.person_for_key_id(key)
            if p is not None:
                self._ann_person(d, rt, p, "relevant but unparsed log entry: \"{}\"".format(line))
                continue

            fpr, ktype = self.maint.keyrings.resolve_keyid(key)
            if fpr is not None:
                self._ann_fpr(d, rt, fpr, "relevant but unparsed log entry: \"{}\"".format(line))


    def _find_matchers(self):
        """
        Return a sequence of (regexp, method) to use to match changelog lines
        """
        import inspect
        matchers = []
        for name, meth in inspect.getmembers(self, lambda x:(inspect.ismethod(x) and hasattr(x, "re"))):
            matchers.append(meth)
        return matchers

    def _run_matchers(self, matchers, d, line, fallback=False):
        for method in matchers:
            is_fallback = getattr(method, "fallback", False)
            if fallback != is_fallback: continue
            mo = method.re.match(line)
            if mo:
                method(d, **mo.groupdict())
                return True
        return False

    def run(self):
        """
        Parse changes from changelog entries after the given date (non inclusive).
        """
        re_import = re.compile(r"^\s*\*\s+Import changes sent to keyring.debian.org HKP interface:")

        matchers = self._find_matchers()

        changelog = kmodels.Changelog()
        for d, lines in changelog.read(since=datetime.datetime.utcnow() - datetime.timedelta(days=60)):
            if re_import.match(lines[0]): continue
            oneline = " ".join(c.strip() for c in lines)
            if not self._run_matchers(matchers, d, oneline):
                self._run_matchers(matchers, d, oneline, fallback=True)
                # If not even the fallback matchers find anything, give it up
