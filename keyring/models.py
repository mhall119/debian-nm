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

def read_sigs(cmd):
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.stdin.close()
    lines = StreamStdoutKeepStderr(proc)
    pub = None
    fpr = None
    uid = None
    sigs = []
    for line in lines:
        if line.startswith(b"pub:"):
            if pub:
                yield pub, fpr, uid, sigs
            pub = line.split(b":")
            fpr = None
            uid = None
            sigs = []
        elif line.startswith(b"fpr:"):
            fpr = line.split(b":")[9]
        elif line.startswith(b"uid:"):
            if uid:
                yield pub, fpr, uid, sigs
            uid = line.split(b":")
            sigs = []
        elif line.startswith(b"sig:"):
            sigs.append(line.split(b":"))
    if pub:
        yield pub, fpr, uid, sigs

    result = proc.wait()
    if result != 0:
        raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))

class KeycheckResult(object):
    def __init__(self, pub, fpr, uid, sigs):
        self.pub = pub
        self.fpr = fpr
        self.uid = uid
        self.uid_name = uid[9].decode("utf8", "replace")
        self.sigs_ok = []
        self.sigs_no_key = []
        self.sigs_not_ok = []
        for sig in sigs:
            if sig[1] == "?":
                self.sigs_no_key.append(sig)
            elif sig[1] == "!":
                self.sigs_ok.append(sig)
            else:
                self.sigs_not_ok.append(sig)

        self.errors = set()

        if len(fpr) == 32:
            self.errors.add("ver3")

        # pub:f:1024:17:C5AF774A58510B5A:2004-04-17:::-:Christoph Berg <cb@df7cb.de>::scESC:

        # Check key and uid validity

        flags = pub[1]
        if "i" in flags: self.errors.update(("skip", "key_invalid"))
        if "d" in flags: self.errors.update(("skip", "key_disabled"))
        if "r" in flags: self.errors.update(("skip", "key_revoked"))
        if "t" in flags: self.errors.update(("skip", "key_expired"))

        flags = uid[1]
        if "i" in flags: self.errors.update(("skip", "uid_invalid"))
        if "d" in flags: self.errors.update(("skip", "uid_disabled"))
        if "r" in flags: self.errors.update(("skip", "uid_revoked"))
        if "t" in flags: self.errors.update(("skip", "uid_expired"))

        # Check key size
        keysize = int(pub[2])
        # FIXME: proper reporting
        if keysize >= 4096:
            pass
        elif keysize >= 2048:
            self.errors.add("key_size_2048")
        else:
            self.errors.add("key_size_small")

        # Check key algorithm
        keyalgo = int(pub[3])
        if keyalgo == 1:
            #echo "This is an RSA key."
            pass
        elif keyalgo == 17:
            self.errors.add("key_algo_dsa")
        else:
            self.errors.add("key_algo_unknown")


    ## FIXME: return warnings properly
    #if len(fpr) == 32:
    #    print("Warning: It looks like this key is an version 3 GPG key. This is bad.")
    #    print("This is not accepted for the NM ID Step. Please doublecheck and then")
    #    print("get your applicant to send you a correct key if this is script isnt wrong.")
    #    EXIT=1
    #else:
    #    print("Key is OpenPGP version 4 or greater.")

    #    if keysize >= 4096:
    #        print("Key has {} bits.".format(keysize))
    #    elif keysize >= 2048:
    #        print("Key has only {} bits.  Please explain why this key size is used".format(keysize))
    #        print("(see [KM] for details).")
    #        print("[KM] http://lists.debian.org/debian-devel-announce/2010/09/msg00003.html")
    #        EXIT=1
    #    else:
    #        print("Key has only {} bits.  This is not acceptable if the application".format(keysize))
    #        print("was started after October 1st, 2010 (see [KM] for details).")
    #        print("[KM] http://lists.debian.org/debian-devel-announce/2010/09/msg00003.html")
    #        EXIT=1

    #    if keyalgo == 1:
    #        #echo "This is an RSA key."
    #        pass
    #    elif keyalgo == 17:
    #        print("This is an DSA key.  This might need an explanation (see [KM] for details).")
    #        print("[KM] http://lists.debian.org/debian-devel-announce/2010/09/msg00003.html")
    #        EXIT=1
    #    else:
    #        print("Unknown key algorithm", keyalgo)
    #        EXIT=1


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

    # For the rsync of the debian keyrings and for the nm.gpg
    #DESTDIR="${DEBHOME:-"$HOME/debian"}/keyring.debian.org/keyrings"
    # Don't try to access the network? (-n)
    #NONET=""
    # Keep nm.gpg after check? (-k)
    # nm.gpg holds all keys you checked with this script.
    #KEEP=""
    # The options for the gpg call in this script.
    # Contains only options used in ALL gpg calls.
    #GPGOPTS="-q --no-options --no-default-keyring --no-auto-check-trustdb --keyring $DESTDIR/nm.gpg --trust-model always"
    # Return value
    EXIT=0

    with NamedTemporaryDirectory() as tmpdir:
        work_keyring = os.path.join(tmpdir, "keycheck.gpg")

        # Get key
        fetch_key(fpr, work_keyring)

        # Check key
        cmd = gpg_keyring_cmd(("debian-keyring.gpg", "debian-nonupload.gpg"), "--keyring", work_keyring, "--check-sigs", fpr)
        for pub, fpr, uid, sigs in read_sigs(cmd):
            res = KeycheckResult(pub, fpr, uid, sigs)
            print("Key {fpr}: {sigs_ok} good sigs, {sigs_no_key} unknown sigs, {sigs_not_ok} ?? sigs".format(
                fpr=fpr, sigs_ok=len(res.sigs_ok), sigs_no_key=len(res.sigs_no_key), sigs_not_ok=len(res.sigs_not_ok)))
            if res.errors:
                print("    errors:", ", ".join(sorted(res.errors)))

        # # this awk script checks to see whether the key details on stdin show
        # # a valid usage flag for a given future date.
        # #    (author: Daniel Kahn Gillmor <dkg@fifthhorseman.net>)
        # #
        # # it needs two variables set before invocation:
        # #  KEYFLAG: which flag are we looking for?  (see http://tools.ietf.org/html/rfc4880#section-5.2.3.21
        # #    gpg supports at least:
        # #      a (authentication), e (encryption), s (signing), c (certification)
        # #  TARGDATE: unix timestamp of date that we care about
        # AWK_CHECKDATE='
        # BEGIN {
        # PRIFLAGS = "";
        # SUBFOUND = 0;
        # }
        # $1 == "pub" && $2 != "r" {
        # PRIFLAGS = $12;
        # PRIEXP = $7;
        # PRIFPR = $5;
        # }
        # $1 == "sub" && $2 != "r" && $12 ~ KEYFLAG {
        # if (!SUBFOUND || $7 == "" || (SUBEXP != "" && $7 > SUBEXP) )
        #     SUBEXP = $7;
        # SUBFOUND = 1;
        # }
        # END {
        # if (PRIFLAGS ~ KEYFLAG)
        # EXPIRES=PRIEXP;
        # else if (!SUBFOUND)
        # { print "No valid \"" KEYFLAG "\" usage flag set on key " PRIFPR "!" ; exit 1 }
        # else if (PRIEXP != "" && PRIEXP < SUBEXP)
        # EXPIRES=PRIEXP;
        # else
        # EXPIRES=SUBEXP;
        # if ( "" == EXPIRES )
        # print "Valid \"" KEYFLAG "\" flag, no expiration.";
        # else if ( EXPIRES > TARGDATE )
        # print "Valid \"" KEYFLAG "\" flag, expires " strftime("%c", EXPIRES) ".";
        # else {
        # print "Valid \"" KEYFLAG "\" flag, but it expires " strftime("%c", EXPIRES) ".";
        # print "This is too soon!";
        # print "Please ask the applicant to extend the lifetime of their OpenPGP key.";
        # exit 1;
        # }
        # }
        # '

        # # we want to make sure that there will be usable, valid keys three months in the future:
        # EXPCUTOFF=$(( $(date +%s) + 86400*30*3 ))

        # gpg ${GPGOPTS} --with-colons --fixed-list-mode --list-key "$KEYID" | \
        # gawk -F : -v KEYFLAG=e -v "TARGDATE=$EXPCUTOFF" "$AWK_CHECKDATE" || EXIT=$?
        # gpg ${GPGOPTS} --with-colons --fixed-list-mode --list-key "$KEYID" | \
        # gawk -F : -v KEYFLAG=s -v "TARGDATE=$EXPCUTOFF" "$AWK_CHECKDATE" || EXIT=$?

        # # Clean up

        # if [ "$EXIT" != 0 ] ; then
        #     cat <<EOF

        # #########################################################################
        # ### There are problems with the key that might make it unusable for   ###
        # ### inclusion in the Debian keyring or usage with Debian's LDAP       ###
        # ### directory.  If unsure, please get in touch with the NM front-desk ###
        # ### nm@debian.org to resolve these problems.                          ###
        # ### (Please do not include this notice in the AM report.)             ###
        # #########################################################################
        # EOF
        # fi

        # exit $EXIT

        return EXIT
