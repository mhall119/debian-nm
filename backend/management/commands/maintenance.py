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
import logging
import json
from backend import models as bmodels
from backend import const

log = logging.getLogger(__name__)

def check_one_process_per_person():
    from django.db.models import Count
    # TODO: use an 'is_open' attribute 
    for p in bmodels.Person.objects.exclude(processes__progress__in=(
        const.PROGRESS_DONE,
        const.PROGRESS_CANCELLED)) \
             .annotate(num_processes=Count("processes")) \
             .filter(num_processes__gt=1):
        log.warning("%s has %d open processes", p, p.num_processes)
        for idx, proc in enumerate(p.processes.exclude(progress__in=(
            const.PROGRESS_DONE,
            const.PROGRESS_CANCELLED))):
            log.warning(" %d: %s (%s)", idx+1, proc.applying_for, proc.progress)


class Command(BaseCommand):
    help = 'Daily maintenance of the nm.debian.org database'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
    )

    def handle(self, *fnames, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        # Run database consistency checks
        for k, v in globals().iteritems():
            if not k.startswith("check_"): continue
            log.info("running %s", k)
            v()

        ## Run other maintenance operations
        #for k, v in globals().iteritems():
        #    if not k.startswith("do_"): continue
        #    log.info("running %s", k)
        #    v()

