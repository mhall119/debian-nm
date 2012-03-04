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

class Updater(object):
    """
    Perform data updates from LDAP

    Updates cn, sn, nm, email for DDs and guest accounts.
    """
    def __init__(self):
        pass

    def do_update(self):
        search_base = "dc=debian,dc=org"
        l = ldap.initialize("ldap://db.debian.org")
        l.simple_bind_s("","")
        for dn, attrs in l.search_s(search_base, ldap.SCOPE_SUBTREE, "objectclass=inetOrgPerson"):
            uid = attrs["uid"][0]
            try:
                person = bmodels.Person.objects.get(uid=uid)
            except bmodels.Person.DoesNotExist:
                log.warning("Person %s exists in LDAP but not in NM database", uid)
                continue

            def get_field(f):
                if f not in attrs:
                    return None
                f = attrs[f]
                if not f:
                    return None
                return f[0]

            # TODO: if cn is '-', then set cn=sn and sn=None
            changed = False
            for field in ("cn", "mn", "sn"):
                val = get_field(field)
                if val is not None:
                    for encoding in ("utf8", "latin1"):
                        try:
                            val = val.decode(encoding)
                            good = True
                            break
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            good = False
                    if not good:
                        log.warning("Field %s=%s for %s has invalid unicode information: skipping", field, repr(val), uid)
                        continue

                old = getattr(person, field)
                if old is not None:
                    for encoding in ("utf8", "latin1"):
                        try:
                            old = old.decode(encoding)
                            good = True
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            good = False
                    if not good:
                        old = "<invalid encoding>"

                if val != old:
                    try:
                        log.info("Person %s changed %s from %s to %s", uid, field, old, val)
                    except UnicodeDecodeError:
                        print "Problems with", uid
                        continue
                    setattr(person, field, val)
                    changed = True

            if changed:
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

        updater = Updater()
        updater.do_update()

        #log.info("%d patch(es) applied", len(fnames))
