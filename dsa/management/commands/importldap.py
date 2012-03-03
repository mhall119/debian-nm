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

log = logging.getLogger(__name__)

class Importer(object):
    """
    Perform initial data import from LDAP

    Imports cn, sn, nm, fpr, email for DDs and guest accounts.

    Does not set status, that will be taken from keyrings
    """
    def __init__(self):
        pass

    def do_import(self):
        #  enrico> Hi. Can you give me an official procedure to check if one is a DD from LDAP info?
        # @weasel> enrico: not really, that's your decision.
        # @weasel> enrico: for one, you can filter on gid 800.  and then filter for having a
        #          fingerprint.  that's usually right
        #  enrico> weasel: what are person accounts without fingerprints for?
        # @weasel> people who screwed up their keys
        # @weasel> we've had that on occasion
        #  enrico> weasel: ack
        # @weasel> enrico: and of course retired people
        # @weasel> we try to set ldap's account status nowadays, but no idea if
        #          that applies to all that ever retired

        search_base = "dc=debian,dc=org"
        l = ldap.initialize("ldap://db.debian.org")
        l.simple_bind_s("","")
        for dn, attrs in l.search_s(search_base, ldap.SCOPE_SUBTREE, "objectclass=inetOrgPerson"):
            uid = attrs["uid"][0]
            try:
                person = bmodels.Person.objects.get(uid=uid)
                continue
            except bmodels.Person.DoesNotExist:
                pass

            try:
                person = bmodels.Person.objects.get(email=uid + "@debian.org")
                person.uid = uid
                person.save()
                continue
            except bmodels.Person.DoesNotExist:
                pass

            def get_field(f):
                if f not in attrs:
                    return None
                f = attrs[f]
                if not f:
                    return None
                return f[0]
            person = bmodels.Person(
                cn=get_field("cn"),
                mn=get_field("mn"),
                sn=get_field("sn"),
                fpr=get_field("keyFingerPrint"),
            )
            if get_field("gidNumber") == '800':
                person.email = uid + "@debian.org"
            else:
                person.email = get_field("emailForward")
            if person.email is None:
                log.warning("Skipping %s because we have no email address", uid)
                continue
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
