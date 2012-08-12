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
from django.db import connection, transaction
from django.contrib.sites.models import Site
import optparse
import sys
import datetime
import logging
import os
import os.path
import re
from backend import models as bmodels
from backend import const
from backend import utils
import keyring.models as kmodels

log = logging.getLogger(__name__)

re_date = re.compile("^\d+-\d+-\d+$")
re_datetime = re.compile("^\d+-\d+-\d+ \d+:\d+:\d+$")
def parse_date(s):
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
    return datetime.datetime(*date[:6])

def get_indent(s):
    res = 0
    for c in s:
        if not c.isspace(): break
        res += 1
    return res

class FingerprintLookup(object):
    KEYID_LEN = 16
    def __init__(self):
        self.fprs = dict()

    def add(self, fprs):
        for f in fprs:
            keyid = f[-self.KEYID_LEN:]
            self.fprs[keyid] = f

    def lookup(self, keyid):
        return self.fprs.get(keyid, None)


class EntrySplitter(object):
    def __init__(self):
        self.re_empty = re.compile(r"^\s*$")
        self.re_author = re.compile(r"^\s+\[")
        self.chunks = []
        self.chunk = []
        self.indent = None

    def flush_chunk(self):
        self.indent = None
        if not self.chunk:
            return
        self.chunks.append(self.chunk)
        self.chunk = []

    def split_entry(self, lines):
        self.chunks = []
        self.chunk = []
        self.indent = None

        for l in lines:
            if self.re_empty.match(l):
                self.flush_chunk()
                continue
            if self.re_author.match(l):
                self.flush_chunk()
                continue

            i = get_indent(l)

            if self.indent is None:
                self.indent = i
            elif i <= self.indent:
                self.flush_chunk()
                self.indent = i
            self.chunk.append(l)

        self.flush_chunk()
        return self.chunks

def person_for_key_id(kid):
    try:
        return bmodels.Person.objects.get(fpr__endswith=kid)
    except bmodels.Person.DoesNotExist:
        return None

def parse_changelog(fprs, since=None):
    """
    Parse changes from changelog entries after the given date (non inclusive).
    """
    from debian import changelog

    re_new_dm = re.compile(r"^\s*\*\s+Add new DM key 0x(?P<key>[0-9A-F]+) \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    re_new_dd = re.compile(r"^\s*\*\s+Add new DD key 0x(?P<key>[0-9A-F]+) \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    re_new_dn = re.compile(r"^\s*\*\s+Add new DD key 0x(?P<key>[0-9A-F]+) \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    re_new_em = re.compile(r"^\s*\*\s+Move 0x(?P<key>[0-9A-F]+) to [Ee]meritus \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    re_new_rem = re.compile(r"^\s*\*\s+Move 0x(?P<key>[0-9A-F]+)\s+\([^)]+\) to removed keyring\s+\(RT #(?P<rt>\d+)")
    re_replace = re.compile(r"^\s*\*\s+Replace(?: key)? 0x(?P<key1>[0-9A-F]+) with 0x(?P<key2>[0-9A-F]+) \([^)]+\)\s+\(RT #(?P<rt>\d+)")
    re_import = re.compile(r"^\s*\*\s+Import changes sent to keyring.debian.org HKP interface:")

    fname = os.path.join(kmodels.KEYRINGS, "../changelog")
    with open(fname) as fd:
        changes = changelog.Changelog(file=fd)

    for c in changes:
        d = parse_date(c.date)
        if since is not None and d <= since: continue
        for ch in EntrySplitter().split_entry(c.changes()):
            if re_import.match(ch[0]): continue
            oneline = " ".join(c.strip() for c in ch)
            mo = re_new_dm.match(oneline)
            if mo:
                key, rt = mo.group("key", "rt")
                p = person_for_key_id(key)
                if p is None:
                    print "! New DM %s https://rt.debian.org/Ticket/Display.html?id=%s" % (key, rt)
                elif p.status in (const.STATUS_DM, const.STATUS_DM_GA):
                    print "# %s goes from %s to DM (already known in the database) #%s" % (p.lookup_key, p.status, rt)
                else:
                    if p.status == const.STATUS_MM_GA:
                        new_status = const.STATUS_DM_GA
                    else:
                        new_status = const.STATUS_DM
                    print "./manage.py change_status %s %s --date='%s' --message='imported from keyring changelog, RT #%s'" % (
                        p.lookup_key, new_status, d.strftime("%Y-%m-%d %H:%M:%S"), rt)
                continue
            mo = re_new_dd.match(oneline)
            if mo:
                key, rt = mo.group("key", "rt")
                p = person_for_key_id(key)
                if p is None:
                    print "! New DD %s #%s (no account before??)" % (key, rt)
                elif p.status == const.STATUS_DD_U:
                    print "# %s goes from %s to DD (already known in the database) #%s" % (p.lookup_key, p.status, rt)
                else:
                    print "./manage.py change_status %s %s --date='%s' --message='imported from keyring changelog, RT #%s'" % (
                        p.lookup_key, const.STATUS_DD_U, d.strftime("%Y-%m-%d %H:%M:%S"), rt)
                continue
            mo = re_new_em.match(oneline)
            if mo:
                key, rt = mo.group("key", "rt")
                p = person_for_key_id(key)
                if p is None:
                    print "! New Emeritus DD %s #%s (no account before??)" % (key, rt)
                elif p.status == const.STATUS_EMERITUS_DD:
                    print "# %s goes from %s to emeritus DD (already known in the database) #%s" % (p.lookup_key, p.status, rt)
                else:
                    print "./manage.py change_status %s %s --date='%s' --message='imported from keyring changelog, RT #%s'" % (
                        p.lookup_key, const.STATUS_EMERITUS_DD, d.strftime("%Y-%m-%d %H:%M:%S"), rt)
                continue
            mo = re_new_rem.match(oneline)
            if mo:
                key, rt = mo.group("key", "rt")
                p = person_for_key_id(key)
                if p is None:
                    print "! New removed key %s #%s (no account before??)" % (key, rt)
                else:
                    print "! %s key %s moved to removed keyring (#%s)" % (p.lookup_key, key, rt)
                continue
            mo = re_replace.match(oneline)
            if mo:
                key1, key2, rt = mo.group("key1", "key2", "rt")
                p = person_for_key_id(key1)
                if p is None:
                    p = person_for_key_id(key2)
                    if p is None:
                        print "! Replaced %s with %s (none of which are in the database!) #%s" % (key1, key2, rt)
                    else:
                        print "# Replaced %s with %s (already done in the database) #%s" % (key1, key2, rt)
                else:
                    fpr = fprs.lookup(key2)
                    if fpr is None:
                        print "! %s replaced key %s with %s but could not find %s in keyrings #%s" % (p.lookup_key, key1, key2, key2, rt)
                    print "./manage.py change_key %s %s # rt #%s" % (p.lookup_key, fpr, rt)
                continue
            print "unparsed", repr(oneline)[:100]
            #em = scan_emeritus(ch)
            #if em:
            #    em["status"] = "dd_e"
            #    em["date"] = d
            #    if map_with_nm(em):
            #        make_cmdline(em)
            #    continue

            #rm = scan_removed(ch)
            #if rm:
            #    rm["status"] = "dd_r"
            #    rm["date"] = d
            #    if map_with_nm(rm):
            #        make_cmdline(rm)
            #    continue


#
#
#import datetime
#
#re_is_emeritus = re.compile("emeritus", re.I)
#re_is_removed = re.compile("remove", re.I)
#re_fpr = re.compile(r"([0-9A-F]{8,})")
#re_rt = re.compile(r"\(RT #(\d+)\)")
#
#def scan_emeritus(ch):
#    if not re_is_emeritus.search(ch):
#        return None
#    mo = re_fpr.search(ch)
#    if not mo:
#        return None
#    res = dict(
#        keyid=mo.group(1),
#        rt=None,
#    )
#    mo = re_rt.search(ch)
#    if mo:
#        res["rt"] = int(mo.group(1))
#    return res
#
#def scan_removed(ch):
#    if not re_is_removed.search(ch):
#        return None
#    mo = re_fpr.search(ch)
#    if not mo:
#        return None
#    res = dict(
#        keyid=mo.group(1),
#        rt=None,
#    )
#    mo = re_rt.search(ch)
#    if mo:
#        res["rt"] = int(mo.group(1))
#    return res
#
#
#
#
## Read fingerprint map from nm.d.o
#uid_by_fpr = dict()
#with open("fprmap") as fd:
#    for line in fd:
#        vals = line.strip().split()
#        if len(vals) != 2:
#            print "skipping fprmap line", line.strip()
#        uid_by_fpr[vals[1]] = vals[0]
#
#def map_with_nm(d):
#    # keyid to fpr
#    for fpr in uid_by_fpr.iterkeys():
#        if fpr.endswith(d["keyid"]):
#            d["fpr"] = fpr
#    if "fpr" not in d:
#        #print "NO FPR MAP", d["keyid"]
#        return False
#
#    # fpr to uid
#    uid = uid_by_fpr.get(d["fpr"], None)
#    if uid is None:
#        #print "NO UI DMAP", d["fpr"]
#        return False
#    d["uid"] = uid
#    return True
#
#def make_cmdline(d):
#    rt = d["rt"]
#    if rt:
#        msg = "status change imported from keyring changelog, RT #%d" % rt
#    else:
#        msg = "status change imported from keyring changelog"
#    print "./manage.py change_status %s %s --who='' --date='%s' -m '%s'" % (
#        d["uid"],
#        d["status"],
#        d["date"].strftime("%Y-%m-%d"),
#        msg)
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#class Checker(object):
#    def __init__(self, quick=False, **kw):
#        self.site = Site.objects.get_current()
#        if not quick:
#            log.info("Importing dm keyring...")
#            self.dm = frozenset(kmodels.list_dm())
#            log.info("Importing dd_u keyring...")
#            self.dd_u = frozenset(kmodels.list_dd_u())
#            log.info("Importing dd_nu keyring...")
#            self.dd_nu = frozenset(kmodels.list_dd_nu())
#            log.info("Importing emeritus_dd keyring...")
#            self.emeritus_dd = frozenset(kmodels.list_emeritus_dd())
#            log.info("Importing removed_dd keyring...")
#            self.removed_dd = frozenset(kmodels.list_removed_dd())
#
#    def _link(self, obj):
#        if self.site.domain == "localhost":
#            return "http://localhost:8000" + obj.get_absolute_url()
#        else:
#            return "https://%s%s" % (self.site.domain, obj.get_absolute_url())
#
#    def backup_db(self, **kw):
#        if BACKUP_DIR is None:
#            log.info("BACKUP_DIR is not set: skipping backups")
#            return
#
#        people = list(bmodels.export_db(full=True))
#
#        class Serializer(json.JSONEncoder):
#            def default(self, o):
#                if hasattr(o, "strftime"):
#                    return o.strftime("%Y-%m-%d %H:%M:%S")
#                return json.JSONEncoder.default(self, o)
#
#        # Base filename for the backup
#        fname = os.path.join(BACKUP_DIR, datetime.datetime.utcnow().strftime("%Y%m%d-db-full.json.gz"))
#        # Use a sequential number to avoid overwriting old backups when run manually
#        while os.path.exists(fname):
#            time.sleep(0.5)
#            fname = os.path.join(BACKUP_DIR, datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S-db-full.json.gz"))
#        log.info("backing up to %s", fname)
#        # Write the backup file
#        with utils.atomic_writer(fname, 0640) as fd:
#            try:
#                gzfd = gzip.GzipFile(filename=fname[:-3], mode="w", compresslevel=9, fileobj=fd)
#                json.dump(people, gzfd, cls=Serializer, indent=2)
#            finally:
#                gzfd.close()
#
#
#    @transaction.commit_on_success
#    def compute_am_ctte(self, **kw):
#        from django.db.models import Max
#        # Set all to False
#        bmodels.AM.objects.update(is_am_ctte=False)
#
#        cutoff = datetime.datetime.utcnow()
#        cutoff = cutoff - datetime.timedelta(days=30*6)
#
#        # Set the active ones to True
#        cursor = connection.cursor()
#        cursor.execute("""
#        SELECT am.id
#          FROM am
#          JOIN process p ON p.manager_id=am.id AND p.progress IN (%s, %s)
#          JOIN log ON log.process_id=p.id AND log.logdate > %s
#         WHERE am.is_am AND NOT am.is_fd AND NOT am.is_dam
#         GROUP BY am.id
#        """, (const.PROGRESS_DONE, const.PROGRESS_CANCELLED, cutoff))
#        ids = [x[0] for x in cursor]
#
#        bmodels.AM.objects.filter(id__in=ids).update(is_am_ctte=True)
#        transaction.commit_unless_managed()
#        log.info("%d CTTE members", bmodels.AM.objects.filter(is_am_ctte=True).count())
#
#
#    @transaction.commit_on_success
#    def compute_process_is_active(self, **kw):
#        """
#        Compute Process.is_active from Process.progress
#        """
#        cursor = connection.cursor()
#        cursor.execute("""
#        UPDATE process SET is_active=(progress NOT IN (%s, %s))
#        """, (const.PROGRESS_DONE, const.PROGRESS_CANCELLED))
#        transaction.commit_unless_managed()
#        log.info("%d/%d active processes",
#                 bmodels.Process.objects.filter(is_active=True).count(),
#                 cursor.rowcount)
#
#    @transaction.commit_on_success
#    def compute_progress_finalisations_on_accounts_created(self, **kw):
#        """
#        Update pending dm_ga processes after the account is created
#        """
#        # Get a lits of accounts from DSA
#        dm_ga_uids = set()
#        dd_uids = set()
#        for entry in dmodels.list_people():
#            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None:
#                dd_uids.add(entry.uid)
#            else:
#                dm_ga_uids.add(entry.uid)
#
#        # Check if pending processes got an account
#        for proc in bmodels.Process.objects.filter(is_active=True):
#            if proc.progress != const.PROGRESS_DAM_OK: continue
#            finalised_msg = None
#
#            if proc.applying_for == const.STATUS_DM_GA and proc.person.uid in dm_ga_uids:
#                finalised_msg = "guest LDAP account created by DSA"
#            if proc.applying_for in (const.STATUS_DD_NU, const.STATUS_DD_U) and proc.person.uid in dd_uids:
#                finalised_msg = "LDAP account created by DSA"
#
#            if finalised_msg is not None:
#                old_status = proc.person.status
#                proc.finalize(finalised_msg)
#                log.info(u"%s finalised: %s changes status %s->%s", self._link(proc), proc.person.uid, old_status, proc.person.status)
#
#    @transaction.commit_on_success
#    def compute_new_guest_accounts_from_dsa(self, **kw):
#        """
#        Create new Person entries for guest accounts created by DSA
#        """
#        for entry in dmodels.list_people():
#            # Skip DDs
#            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None: continue
#
#            # Skip people we already know of
#            if bmodels.Person.objects.filter(uid=entry.uid).exists(): continue
#
#            # Skip people without fingerprints
#            if entry.single("keyFingerPrint") is None: continue
#
#            # Skip entries without emails (happens when running outside of the Debian network)
#            if entry.single("emailForward") is None: continue
#
#            # Check for fingerprint duplicates
#            try:
#                p = bmodels.Person.objects.get(fpr=entry.single("keyFingerPrint"))
#                log.warning("%s has the same fingerprint as LDAP uid %s", self._link(p), entry.uid)
#                continue
#            except bmodels.Person.DoesNotExist:
#                pass
#
#            p = bmodels.Person(
#                cn=entry.single("cn"),
#                mn=entry.single("mn"),
#                sn=entry.single("sn"),
#                email=entry.single("emailForward"),
#                uid=entry.uid,
#                fpr=entry.single("keyFingerPrint"),
#                status=const.STATUS_MM_GA,
#            )
#            p.save()
#            log.info("%s (guest account only) imported from LDAP", self._link(p))
#
#    @transaction.commit_on_success
#    def compute_display_names_from_keyring(self, **kw):
#        """
#        Update Person.display_name with data from keyrings
#        """
#        # Current display names
#        info = dict()
#        for p in bmodels.Person.objects.all():
#            if not p.fpr: continue
#            info[p.fpr] = dict(
#                cur=p.fullname,
#                pri=None, # Primary uid
#                deb=None, # Debian uid
#            )
#        log.info("%d entries with fingerprints", len(info))
#
#        cur_fpr = None
#        cur_info = None
#        for keyring in "debian-keyring.gpg", "debian-maintainers.gpg", "debian-nonupload.gpg", "emeritus-keyring.gpg", "removed-keys.gpg":
#            count = 0
#            for fpr, u in kmodels.uid_info(keyring):
#                if fpr != cur_fpr:
#                    cur_info = info.get(fpr, None)
#                    cur_fpr = fpr
#                    if cur_info is not None:
#                        # Save primary uid
#                        cur_info["pri"] = u.name
#
#                if cur_info is not None and u.email is not None and u.email.endswith("@debian.org"):
#                    cur_info["deb"] = u.name
#                count += 1
#            log.info("%s: %d uids checked...", keyring, count)
#
#        for fpr, i in info.iteritems():
#            if not i["pri"] and not i["deb"]: continue
#            if i["pri"]:
#                cand = i["pri"]
#            else:
#                cand = i["deb"]
#            if i["cur"] != cand:
#                log.info("%s: %s %r != %r", keyring, fpr, i["cur"], cand)
#
#    def check_one_process_per_person(self, **kw):
#        """
#        Check that one does not have more than one open process at the current time
#        """
#        from django.db.models import Count
#        for p in bmodels.Person.objects.filter(processes__is_active=True) \
#                 .annotate(num_processes=Count("processes")) \
#                 .filter(num_processes__gt=1):
#            log.warning("%s has %d open processes", self._link(p), p.num_processes)
#            for idx, proc in enumerate(p.processes.filter(is_active=True)):
#                log.warning(" %d: %s (%s)", idx+1, self._link(proc), repr(proc))
#
#    def check_am_must_have_uid(self, **kw):
#        """
#        Check that one does not have more than one open process at the current time
#        """
#        from django.db.models import Count
#        for am in bmodels.AM.objects.filter(person__uid=None):
#            log.warning("AM %d (person %d %s) has no uid", am.id, am.person.id, am.person.email)
#
#    def check_status_progress_match(self, **kw):
#        """
#        Check that the last process with progress 'done' has the same
#        'applying_for' as the person status
#        """
#        from django.db.models import Max
#        for p in bmodels.Person.objects.all():
#            try:
#                last_proc = bmodels.Process.objects.filter(person=p, progress=const.PROGRESS_DONE).annotate(ended=Max("log__logdate")).order_by("-ended")[0]
#            except IndexError:
#                continue
#            if p.status != last_proc.applying_for:
#                log.warning("%s has status %s but the last completed process was applying for %s",
#                            p.uid, p.status, last_proc.applying_for)
#
#    def check_log_progress_match(self, **kw):
#        """
#        Check that the last process with progress 'done' has the same
#        'applying_for' as the person status
#        """
#        from django.db.models import Max
#        for p in bmodels.Process.objects.filter(is_active=True):
#            try:
#                last_log = p.log.order_by("-logdate")[0]
#            except IndexError:
#                log.warning("%s (%s) has no log entries", self._link(p), repr(p))
#                continue
#            if p.progress != last_log.progress:
#                log.warning("%s (%s) has progress %s but the last log entry has progress %s",
#                            self._link(p), repr(p), p.progress, last_log.progress)
#
#    def check_enums(self, **kw):
#        """
#        Consistency check of enum values
#        """
#        statuses = [x.tag for x in const.ALL_STATUS]
#        progresses = [x.tag for x in const.ALL_PROGRESS]
#
#        for p in bmodels.Person.objects.exclude(status__in=statuses):
#            log.warning("%s: invalid status %s", self._link(p), p.status)
#
#        for p in bmodels.Process.objects.exclude(applying_for__in=statuses):
#            log.warning("%s: invalid applying_for %s", self._link(p), p.applying_for)
#
#        for p in bmodels.Process.objects.exclude(progress__in=progresses):
#            log.warning("%s: invalid progress %s", self._link(p), p.progress)
#
#        for l in bmodels.Log.objects.exclude(progress__in=progresses):
#            log.warning("%s: log entry %d has invalid progress %s", self._link(l.process), l.id, l.progress)
#
#    def check_corner_cases(self, **kw):
#        """
#        Check for known corner cases, to be fixed somehow eventually maybe in case
#        they give trouble
#        """
#        c = bmodels.Person.objects.filter(processes__isnull=True).count()
#        if c > 0:
#            log.warning("%d Great Ancients found who have no Process entry", c)
#
#        c = bmodels.Person.objects.filter(status_changed__isnull=True).count()
#        if c > 0:
#            log.warning("%d entries still have a NULL status_changed date", c)
#
#    def check_keyring_consistency(self, quick=False, **kw):
#        """
#        Show entries that do not match between keyrings and our DB
#        """
#        if quick:
#            log.info("Skipping check_keyring_consistency because --quick was used")
#            return
#
#        # Prefetch people and index them by fingerprint
#        people_by_fpr = dict()
#        for p in bmodels.Person.objects.all():
#            if p.fpr is None: continue
#            people_by_fpr[p.fpr] = p
#
#        keyring_by_status = {
#            const.STATUS_DM: self.dm,
#            const.STATUS_DM_GA: self.dm,
#            const.STATUS_DD_U: self.dd_u,
#            const.STATUS_DD_NU: self.dd_nu,
#            const.STATUS_EMERITUS_DD: self.emeritus_dd,
#            const.STATUS_REMOVED_DD: self.removed_dd,
#        }
#
#        count = 0
#
#        # Check the fingerprints on our DB
#        for fpr, p in sorted(people_by_fpr.iteritems(), key=lambda x:x[1].uid):
#            keyring = keyring_by_status.get(p.status)
#            # Skip the statuses we currently can't check for
#            if keyring is None: continue
#            # Skip those that are ok
#            if fpr in keyring: continue
#            # Look for the key in other keyrings
#            found = False
#            for status, keyring in keyring_by_status.iteritems():
#                if fpr in keyring:
#                    log.warning("%s has status %s but is in %s keyring (fpr: %s)", self._link(p), p.status, status, fpr)
#                    count += 1
#                    found = True
#                    break
#            if not found and p.status != const.STATUS_REMOVED_DD:
#                log.warning("%s has status %s but is not in any keyring (fpr: %s)", self._link(p), p.status, fpr)
#                count += 1
#
#        # Spot fingerprints not in our DB
#        for status, keyring in keyring_by_status.iteritems():
#            # TODO: not quite sure how to handle the removed_dd keyring, until I
#            #       know what exactly is in there
#            if status == const.STATUS_REMOVED_DD: continue
#            for fpr in keyring:
#                if fpr not in people_by_fpr:
#                    log.warning("Fingerprint %s is in %s keyring but not in our db", fpr, status)
#                    count += 1
#
#        log.warning("%d mismatches between keyring and nm.debian.org databases", count)
#
#
#    def check_ldap_consistency(self, quick=False, **kw):
#        """
#        Show entries that do not match between LDAP and our DB
#        """
#        # Prefetch people and index them by fingerprint
#        people_by_uid = dict()
#        for p in bmodels.Person.objects.all():
#            if p.uid is None: continue
#            people_by_uid[p.uid] = p
#
#        for entry in dmodels.list_people():
#            try:
#                person = bmodels.Person.objects.get(uid=entry.uid)
#            except bmodels.Person.DoesNotExist:
#                log.warning("Person %s exists in LDAP but not in our db", entry.uid)
#                continue
#
#            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None:
#                if person.status not in (const.STATUS_DD_U, const.STATUS_DD_NU):
#                    log.warning("%s has gidNumber 800 and a key, but the db has state %s", self._link(person), person.status)
#
#    def check_dmlist(self, quick=False, **kw):
#        """
#        Show entries that do not match between projectb DM list and out DB
#        """
#        # Code used to import DMs is at 64a3e35a5c55aa3ee122e6234ad24c74a57dd843
#        # Now this is just a consistency check
#        try:
#            maints = pmodels.Maintainers()
#        except Exception, e:
#            log.info("Skipping check_dmlist: %s", e)
#            return
#
#        def check_status(p):
#            if p.status not in (const.STATUS_DM, const.STATUS_DM_GA):
#                log.info("%s DB status is %s but it appears to projectb to be a DM instead", self._link(p), p.status)
#
#        for maint in maints.db.itervalues():
#            person = bmodels.Person.lookup(maint["fpr"])
#            if person is not None:
#                check_status(person)
#                continue
#
#            person = bmodels.Person.lookup(maint["email"])
#            if person is not None:
#                log.info("%s matches by email %s with projectb but not by key fingerprint", self._link(person), maint["email"])
#                check_status(person)
#                continue
#
#            log.info("%s/%s exists in projectb but not in our DB", maint["email"], maint["fpr"])
#
#
#    def check_django_permissions(self, **kw):
#        from django.contrib.auth.models import User
#        from django.db.models import Q
#
#        # Get the list of users that django thinks are powerful
#        django_power_users = set()
#        for u in User.objects.all():
#            if u.is_staff or u.is_superuser:
#                django_power_users.add(u.id)
#
#        # Get the list of users that we think are powerful
#        nm_power_users = set()
#        for a in bmodels.AM.objects.filter(Q(is_fd=True) | Q(is_dam=True)):
#            if a.person.user is None:
#                log.warning("%s: no corresponding django user", self._link(a.person))
#            else:
#                nm_power_users.add(a.person.user.id)
#
#        for id in (django_power_users - nm_power_users):
#            log.warning("auth.models.User.id %d has powers that the NM site does not know about", id)
#        for id in (nm_power_users - django_power_users):
#            log.warning("auth.models.User.id %d has powers in NM that django does not know about", id)
#
#
#    def run(self, **opts):
#        """
#        Run all checker functions
#        """
#        import inspect
#        for prefix in ("backup", "compute", "check"):
#            for name, meth in inspect.getmembers(self, predicate=inspect.ismethod):
#                if not name.startswith(prefix + "_"): continue
#                log.info("running %s", name)
#                meth(**opts)


class Command(BaseCommand):
    help = 'Daily maintenance of the nm.debian.org database'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("--quick", action="store_true", help="Skip slow checks. Default: %default"),
    )

    def handle(self, since=None, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        if since is not None:
            since = datetime.datetime.strptime(since, "%Y-%m-%d")

        # Read keyrings
        fprs = FingerprintLookup()
        fprs.add(kmodels.list_dm())
        fprs.add(kmodels.list_dd_u())
        fprs.add(kmodels.list_dd_nu())
        fprs.add(kmodels.list_emeritus_dd())
        fprs.add(kmodels.list_removed_dd())
        parse_changelog(fprs, since=since)
        #checker = Checker(**opts)
        #checker.run(**opts)
