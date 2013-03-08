# nm.debian.org list-of-email reports to be used for generating aliases
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

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
import django.db
from django.conf import settings
from django.db import connection, transaction
from django.contrib.sites.models import Site
from django.db.models import Count, Min, Max
import optparse
import sys
import datetime
import logging
import json
import os
import os.path
import gzip
import re
import time
import codecs
from cStringIO import StringIO
from backend import models as bmodels
from backend import const
from backend import utils

log = logging.getLogger(__name__)

class Reports(object):
    def list_ctte(self):
        """
        List members of NM committee
        """
        from django.db.models import Q
        for am in bmodels.AM.objects.filter(Q(is_am_ctte=True) | Q(is_fd=True) | Q(is_dam=True)):
            yield am.person.email

    def list_fd(self):
        """
        List members of Front Desk
        """
        from django.db.models import Q
        for am in bmodels.AM.objects.filter(Q(is_fd=True) | Q(is_dam=True)):
            yield am.person.email

    def list_dam(self):
        """
        List Debian Account Managers
        """
        for am in bmodels.AM.objects.filter(is_dam=True):
            yield am.person.email

    def list_am(self):
        """
        List active application managers
        """
        from django.db.models import Q
        for am in bmodels.AM.objects.filter(Q(is_am=True) | Q(is_fd=True) | Q(is_dam=True)):
            yield am.person.email


class Command(BaseCommand):
    help = 'List email addresses. Run with --list to get a list of valid groups of people. More than one group can be queried at the same time.'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", default=None, help="Disable progress reporting"),
        optparse.make_option("--list", action="store_true", default=None, help="List available groups"),
    )

    def handle(self, *args, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        reports = Reports()

        # List available reports if requested
        if opts["list"]:
            import inspect
            for name, m in inspect.getmembers(reports, predicate=inspect.ismethod):
                if not name.startswith("list_"): continue
                print name[5:], "-", m.__doc__.strip()
            return

        # Run all reports, merge their results
        result = set()
        for arg in args:
            method = getattr(reports, "list_" + arg, None)
            if method is None:
                print >>sys.stderr, "Report '%s' not found" % arg
                continue
            result.update(method())

        # Sort and print what we got
        for email in sorted(result):
            print email
