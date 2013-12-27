# coding: utf-8
# nm.debian.org keycheck interface
#
# Copyright (C) 2013  Enrico Zini <enrico@debian.org>
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
from django.core.management.base import BaseCommand, CommandError
import optparse
import sys
import logging
import keyring.models as kmodels

log = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "keycheck.sh using nm.debian.org's implementation"
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
    )

    def handle(self, fpr, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        for kc in kmodels.keycheck(fpr):
            print("Key {fpr}: {uids} uids, check: {errors}".format(
                fpr=kc.key.fpr,
                uids=len(kc.uids),
                errors=(", ".join(sorted(kc.errors)) if kc.errors else "ok")
            ))
            for ku in kc.uids:
                print("  uid {uid}: sigs: {sigs_ok} ok, {sigs_no_key} unknown, {sigs_not_ok} ??; check: {errors}".format(
                    uid=ku.uid.name,
                    sigs_ok=len(ku.sigs_ok),
                    sigs_no_key=len(ku.sigs_no_key),
                    sigs_not_ok=len(ku.sigs_not_ok),
                    errors=(", ".join(sorted(ku.errors)) if ku.errors else "ok")
                ))

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

        # # this awk script checks to see whether the key details on stdin show
        # # a valid usage flag for a given future date.
        # #    (author: Daniel Kahn Gillmor <dkg@fifthhorseman.net>)
        # #
        # # it needs two variables set before invocation:
        # #  KEYFLAG: which flag are we looking for?  (see http://tools.ietf.org/html/rfc4880#section-5.2.3.21
        # #    gpg supports at least:
        # #      a (authentication), e (encryption), s (signing), c (certification)
        # #  TARGDATE: unix timestamp of date that we care about

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
