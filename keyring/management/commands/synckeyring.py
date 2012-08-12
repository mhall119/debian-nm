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

    def rturl(num):
        return "https://rt.debian.org/" + num

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
                    print "! New DM %s %s" % (key, rturl(rt))
                elif p.status in (const.STATUS_DM, const.STATUS_DM_GA):
                    print "# %s goes from %s to DM (already known in the database) %s" % (p.lookup_key, p.status, rturl(rt))
                else:
                    if p.status == const.STATUS_MM_GA:
                        new_status = const.STATUS_DM_GA
                    else:
                        new_status = const.STATUS_DM
                    print "./manage.py change_status %s %s --date='%s' --message='imported from keyring changelog, RT #%s' # %s" % (
                        p.lookup_key, new_status, d.strftime("%Y-%m-%d %H:%M:%S"), rt, rturl(rt))
                continue
            mo = re_new_dd.match(oneline)
            if mo:
                key, rt = mo.group("key", "rt")
                p = person_for_key_id(key)
                if p is None:
                    print "! New DD %s %s (no account before??)" % (key, rturl(rt))
                elif p.status == const.STATUS_DD_U:
                    print "# %s goes from %s to DD (already known in the database) %s" % (p.lookup_key, p.status, rturl(rt))
                else:
                    print "./manage.py change_status %s %s --date='%s' --message='imported from keyring changelog, RT #%s' # %s" % (
                        p.lookup_key, const.STATUS_DD_U, d.strftime("%Y-%m-%d %H:%M:%S"), rt, rturl(rt))
                continue
            mo = re_new_em.match(oneline)
            if mo:
                key, rt = mo.group("key", "rt")
                p = person_for_key_id(key)
                if p is None:
                    print "! New Emeritus DD %s %s (no account before??)" % (key, rturl(rt))
                elif p.status == const.STATUS_EMERITUS_DD:
                    print "# %s goes from %s to emeritus DD (already known in the database) %s" % (p.lookup_key, p.status, rturl(rt))
                else:
                    print "./manage.py change_status %s %s --date='%s' --message='imported from keyring changelog, RT %s' # %s" % (
                        p.lookup_key, const.STATUS_EMERITUS_DD, d.strftime("%Y-%m-%d %H:%M:%S"), rt, rturl(rt))
                continue
            mo = re_new_rem.match(oneline)
            if mo:
                key, rt = mo.group("key", "rt")
                p = person_for_key_id(key)
                if p is None:
                    print "! New removed key %s %s (no account before??)" % (key, rturl(rt))
                else:
                    print "! %s key %s moved to removed keyring %s" % (p.lookup_key, key, rturl(rt))
                continue
            mo = re_replace.match(oneline)
            if mo:
                key1, key2, rt = mo.group("key1", "key2", "rt")
                p = person_for_key_id(key1)
                if p is None:
                    p = person_for_key_id(key2)
                    if p is None:
                        print "! Replaced %s with %s (none of which are in the database!) %s" % (key1, key2, rturl(rt))
                    else:
                        print "# Replaced %s with %s (already done in the database) %s" % (key1, key2, rturl(rt))
                else:
                    fpr = fprs.lookup(key2)
                    if fpr is None:
                        print "! %s replaced key %s with %s but could not find %s in keyrings %s" % (p.lookup_key, key1, key2, key2, rturl(rt))
                    print "./manage.py change_key %s %s # rt # %s" % (p.lookup_key, fpr, rturl(rt))
                continue
            print "unparsed", repr(oneline)[:100]


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
        log.info("Reading DM keyring...")
        fprs.add(kmodels.list_dm())
        log.info("Reading DD keyring...")
        fprs.add(kmodels.list_dd_u())
        log.info("Reading DN keyring...")
        fprs.add(kmodels.list_dd_nu())
        log.info("Reading emeritus keyring...")
        fprs.add(kmodels.list_emeritus_dd())
        log.info("Reading removed keyring...")
        fprs.add(kmodels.list_removed_dd())
        log.info("Processing changelog...")
        parse_changelog(fprs, since=since)
