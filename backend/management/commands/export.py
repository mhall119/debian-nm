# coding: utf-8

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
from django.contrib.auth.models import User
import optparse
import sys
import logging
import json
from backend import models as bmodels

log = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Export all the NM database'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", default=None, help="Disable progress reporting"),
        optparse.make_option("--full", action="store_true", default=None, help="Also export privacy-sensitive information"),
    )

    def handle(self, quiet=False, full=False, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if quiet:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        people = list(bmodels.export_db(full))

        class Serializer(json.JSONEncoder):
            def default(self, o):
                if hasattr(o, "strftime"):
                    return o.strftime("%Y-%m-%d %H:%M:%S")
                return json.JSONEncoder.default(self, o)

        json.dump(people, sys.stdout, cls=Serializer, indent=2)

