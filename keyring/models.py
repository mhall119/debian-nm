# coding: utf-8
# nm.debian.org keyring access functions
#
# Copyright (C) 2012--2013  Enrico Zini <enrico@debian.org>
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
"""
Code used to list entries in keyrings
"""

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.db import models
from django.conf import settings
import os.path
import subprocess
from collections import namedtuple
from backend.utils import StreamStdoutKeepStderr, NamedTemporaryDirectory
import time
import logging

log = logging.getLogger(__name__)

KEYRINGS = getattr(settings, "KEYRINGS", "/srv/keyring.debian.org/keyrings")
#KEYSERVER = getattr(settings, "KEYSERVER", "keys.gnupg.net")
KEYSERVER = getattr(settings, "KEYSERVER", "pgp.mit.edu")

#WithFingerprint = namedtuple("WithFingerprint", (
#    "type", "trust", "bits", "alg", "id", "created", "expiry",
#    "misc8", "ownertrust", "uid", "sigclass", "cap", "misc13",
#    "flag", "misc15"))

Uid = namedtuple("Uid", ("name", "email", "comment"))

def gpg_cmd(*args):
    cmd = [
        "gpg", "-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb",
        "--trust-model", "always", "--with-colons", "--fixed-list-mode",
        "--with-fingerprint"
    ]
    cmd.extend(args)
    return cmd

def gpg_keyring_cmd(keyrings, *args):
    """
    Build a gpg invocation command using the given keyring, or sequence of
    keyring names
    """
    # If we only got one string, make it into a sequence
    if isinstance(keyrings, basestring):
        keyrings = (keyrings, )
    cmd = [
        "gpg", "-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb",
        "--trust-model", "always", "--with-colons", "--fixed-list-mode",
        "--with-fingerprint",
    ]
    for k in keyrings:
        cmd.append("--keyring")
        cmd.append(os.path.join(KEYRINGS, k))
    cmd.extend(args)
    return cmd

def _check_keyring(keyring, fpr):
    """
    Check if a fingerprint exists in a keyring
    """
    cmd = gpg_keyring_cmd(keyring, "--list-keys", fpr)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    result = proc.wait()
    present = None
    if result == 0:
        present = True
    elif result == 2:
        present = False
    else:
        raise RuntimeError("gpg exited with status %d: %s" % (result, stderr.strip()))
    return present

def _list_keyring(keyring):
    """
    List all fingerprints in a keyring
    """
    cmd = gpg_keyring_cmd(keyring, "--list-keys")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.stdin.close()
    lines = StreamStdoutKeepStderr(proc)
    for line in lines:
        if not line.startswith("fpr"): continue
        yield line.split(":")[9]
    result = proc.wait()
    if result != 0:
        raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))

# def _parse_list_keys_line(line):
#     res = []
#     for i in line.split(":"):
#         if not i:
#             res.append(None)
#         else:
#             i = i.decode("string_escape")
#             try:
#                 i = i.decode("utf-8")
#             except UnicodeDecodeError:
#                 pass
#             res.append(i)
#     for i in range(len(res), 15):
#         res.append(None)
#     return WithFingerprint(*res)


# def _list_full_keyring(keyring):
#     keyring = os.path.join(KEYRINGS, keyring)
#
#     cmd = [
#         "gpg",
#         "-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb", "--trust-model", "always",
#         "--keyring", keyring,
#         "--with-colons", "--with-fingerprint", "--list-keys",
#     ]
#     #print " ".join(cmd)
#     proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     proc.stdin.close()
#     lines = StreamStdoutKeepStderr(proc)
#     fprs = []
#     for line in lines:
#         yield _parse_list_keys_line(line)
#     result = proc.wait()
#     if result != 0:
#         raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))

# def uid_info(keyring):
#     re_uid = re.compile(r"^(?P<name>.+?)\s*(?:\((?P<comment>.+)\))?\s*(?:<(?P<email>.+)>)?$")
#
#     fpr = None
#     for l in _list_full_keyring(keyring):
#         if l.type == "pub":
#             fpr = None
#         elif l.type == "fpr":
#             fpr = l.uid
#         elif l.type == "uid":
#             # filter out revoked/expired uids
#             if 'r' in l.trust or 'e' in l.trust:
#                 continue
#             # Parse uid
#             mo = re_uid.match(l.uid)
#             u = Uid(mo.group("name"), mo.group("email"), mo.group("comment"))
#             if not mo:
#                 log.warning("Cannot parse uid %s for key %s in keyring %s" % (l.uid, fpr, keyring))
#             else:
#                 yield fpr, u

def is_dm(fpr):
    return _check_keyring("debian-maintainers.gpg", fpr)

def is_dd_u(fpr):
    return _check_keyring("debian-keyring.gpg", fpr)

def is_dd_nu(fpr):
    return _check_keyring("debian-nonupload.gpg", fpr)


def list_dm():
    return _list_keyring("debian-maintainers.gpg")

def list_dd_u():
    return _list_keyring("debian-keyring.gpg")

def list_dd_nu():
    return _list_keyring("debian-nonupload.gpg")

def list_emeritus_dd():
    return _list_keyring("emeritus-keyring.gpg")

def list_removed_dd():
    return _list_keyring("removed-keys.pgp")

def fetch_key(fpr, dest_keyring):
    cmd = gpg_cmd("--keyring", dest_keyring, "--keyserver", KEYSERVER, "--recv-keys", fpr)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    result = proc.wait()
    if result != 0:
        raise RuntimeError("gpg exited with status %d: %s" % (result, stderr.strip()))

class Key(object):
    def __init__(self, fpr, pub):
        self.pub = pub
        self.fpr = fpr
        self.uids = {}
        self.subkeys = {}

    def get_uid(self, uid):
        uidfpr = uid[7]
        res = self.uids.get(uidfpr, None)
        if res is None:
            self.uids[uidfpr] = res = Uid(self, uid)
        return res

    def add_sub(self, sub):
        subfpr = tuple(sub[3:6])
        self.subkeys[subfpr] = sub

    def keycheck(self):
        return KeycheckKeyResult(self)

class Uid(object):
    def __init__(self, key, uid):
        self.key = key
        self.uid = uid
        self.name = uid[9].decode("utf8", "replace")
        self.sigs = {}

    def add_sig(self, sig):
        # FIXME: missing a full fingerprint, we try to index with as much
        # identifying data as possible
        k = tuple(sig[3:6])
        self.sigs[k] = sig

class KeycheckKeyResult(object):
    def __init__(self, key):
        self.key = key
        self.uids = []
        self.errors = set()
        self.capabilities = {}

        # Check key type from fingerprint length
        if len(key.fpr) == 32:
            self.errors.add("ver3")

        # pub:f:1024:17:C5AF774A58510B5A:2004-04-17:::-:Christoph Berg <cb@df7cb.de>::scESC:

        # Check key size
        keysize = int(key.pub[2])
        if keysize >= 4096:
            pass
        elif keysize >= 2048:
            self.errors.add("key_size_2048")
        else:
            self.errors.add("key_size_small")

        # Check key algorithm
        keyalgo = int(key.pub[3])
        if keyalgo == 1:
            pass
        elif keyalgo == 17:
            self.errors.add("key_algo_dsa")
        else:
            self.errors.add("key_algo_unknown")

        # Check key flags
        flags = key.pub[1]
        if "i" in flags: self.errors.update(("skip", "key_invalid"))
        if "d" in flags: self.errors.update(("skip", "key_disabled"))
        if "r" in flags: self.errors.update(("skip", "key_revoked"))
        if "t" in flags: self.errors.update(("skip", "key_expired"))

        # Check UIDs
        for uid in key.uids.itervalues():
            self.uids.append(KeycheckUidResult(uid))

        def int_expire(x):
            if x is None or x == "": return x
            return int(x)

        def max_expire(a, b):
            """
            Pick the maximum expiration indication between the two.
            a and b can be:
                None: nothing known (sorts lowest)
                number: an expiration timestamp
                "": no expiration (sorts highest)
            """
            if a is None: return int_expire(b)
            if b is None: return int_expire(a)
            if a == "": return int_expire(a)
            if b == "": return int_expire(b)
            return max(int(a), int(b))

        # Check capabilities
        for cap in "es":
            # Check in primary key
            if cap in key.pub[11]:
                self.capabilities[cap] = int_expire(key.pub[6])

            # Check in subkeys
            for sk in key.subkeys.itervalues():
                if cap in sk[11]:
                    oldcap = self.capabilities.get(cap, None)
                    self.capabilities[cap] = max_expire(oldcap, sk[6])

        cutoff = time.time() + 86400 * 90

        c = self.capabilities.get("e", None)
        if c is None:
            self.errors.add("key_encryption_missing")
        elif c is not "" and c < cutoff:
            self.errors.add("key_encryption_expires_soon")

        c = self.capabilities.get("s", None)
        if c is None:
            self.errors.add("key_signing_missing")
        elif c is not "" and c < cutoff:
            self.errors.add("key_signing_expires_soon")


class KeycheckUidResult(object):
    def __init__(self, uid):
        self.uid = uid
        self.errors = set()

        # uid:q::::1241797807::73B85305F2B11D695B610022AF225CCBC6B3F6D9::Enrico Zini <enrico@enricozini.org>:

        # Check uid flags

        flags = uid.uid[1]
        if "i" in flags: self.errors.update(("skip", "uid_invalid"))
        if "d" in flags: self.errors.update(("skip", "uid_disabled"))
        if "r" in flags: self.errors.update(("skip", "uid_revoked"))
        if "t" in flags: self.errors.update(("skip", "uid_expired"))

        # Check signatures
        self.sigs_ok = []
        self.sigs_no_key = []
        self.sigs_not_ok = []
        for sig in uid.sigs.itervalues():
            # dkg says:
            # ! means "verified"
            # - means "not verified" (bad signature, signature from expired key)
            # ? means "signature from a key we don't have"
            if sig[1] == "?" or sig[1] == "-":
                self.sigs_no_key.append(sig)
            elif sig[1] == "!":
                self.sigs_ok.append(sig)
            else:
                self.sigs_not_ok.append(sig)


def read_sigs(cmd):
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.stdin.close()
    lines = StreamStdoutKeepStderr(proc)
    keys = {}
    pub = None
    cur_key = None
    cur_uid = None
    for lineno, line in enumerate(lines, start=1):
        if line.startswith(b"pub:"):
            # Keep track of this pub record, to correlate with the following
            # fpr record
            pub = line.split(b":")
            cur_key = None
            cur_uid = None
        elif line.startswith(b"fpr:"):
            # Correlate fpr with the previous pub record, and start gathering
            # information for a new key
            if pub is None:
                raise Exception("gpg:{}: found fpr line with no previous pub line".format(lineno))
            fpr = line.split(b":")[9]
            cur_key = keys.get(fpr, None)
            if cur_key is None:
                keys[fpr] = cur_key = Key(fpr, pub)
            pub = None
            cur_uid = None
        elif line.startswith(b"uid:"):
            if cur_key is None:
                raise Exception("gpg:{}: found uid line with no previous pub+fpr lines".format(lineno))
            cur_uid = cur_key.get_uid(line.split(b":"))
        elif line.startswith(b"sig:"):
            if cur_uid is None:
                raise Exception("gpg:{}: found sig line with no previous uid line".format(lineno))
            cur_uid.add_sig(line.split(b":"))
        elif line.startswith(b"sub:"):
            if cur_key is None:
                raise Exception("gpg:{}: found sub line with no previous pub+fpr lines".format(lineno))
            cur_key.add_sub(line.split(b":"))

    result = proc.wait()
    if result != 0:
        raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))

    return keys.itervalues()

def keycheck(fpr):
    """
    This little (and maybe bad) function is used to check keys from NM's.

    First it downloads the key of the NM from a keyserver in the local nm.gpg
    file.

    Then it shows the key and all signatures made by existing Debian
    Developers.

    Finally, it checks to make sure that the key has encryption and
    signature capabilities, and will continue to have them one month
    into the future.
    """
    # Based on keycheck,sh
    # Copyright (C) 2003-2007 Joerg Jaspert <joerg@debian.org> and others

    # Return value
    EXIT=0

    with NamedTemporaryDirectory() as tmpdir:
        work_keyring = os.path.join(tmpdir, "keycheck.gpg")

        # Get key
        fetch_key(fpr, work_keyring)

        # Check key
        cmd = gpg_keyring_cmd(("debian-keyring.gpg", "debian-nonupload.gpg"), "--keyring", work_keyring, "--check-sigs", fpr)
        for key in read_sigs(cmd):
            yield key.keycheck()
