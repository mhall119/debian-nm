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
from backend.utils import StreamStdoutKeepStderr
import logging

log = logging.getLogger(__name__)

KEYRINGS = getattr(settings, "KEYRINGS", "/srv/keyring.debian.org/keyrings")

WithFingerprint = namedtuple("WithFingerprint", (
    "type", "trust", "bits", "alg", "id", "created", "expiry",
    "misc8", "ownertrust", "uid", "sigclass", "cap", "misc13",
    "flag", "misc15"))

Uid = namedtuple("Uid", ("name", "email", "comment"))

def gpg_keyring_cmd(keyring, *args):
    keyring = os.path.join(KEYRINGS, keyring)
    cmd = [
        "gpg", "-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb",
        "--trust-model", "always", "--with-colons", "--fixed-list-mode",
        "--with-fingerprint", "--keyring", keyring
    ]
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
