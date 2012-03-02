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
from django.db import connection, transaction
import optparse
import sys
import datetime
import logging
import json
from backend import models as bmodels
from backend import const

log = logging.getLogger(__name__)

@transaction.commit_on_success
def compute_am_ctte():
    from django.db.models import Max
    # Set all to False
    bmodels.AM.objects.update(is_am_ctte=False)

    cutoff = datetime.datetime.utcnow()
    cutoff = cutoff - datetime.timedelta(days=30*6)

    # Set the active ones to True
    cursor = connection.cursor()
    cursor.execute("""
    SELECT am.id
      FROM am
      JOIN process p ON p.manager_id=am.id AND p.progress=%s
      JOIN log ON log.process_id=p.id AND log.logdate > %s
     WHERE am.is_am AND NOT am.is_fd AND NOT am.is_dam
     GROUP BY am.id
    """, (const.PROGRESS_DONE, cutoff))
    ids = [x[0] for x in cursor]

    bmodels.AM.objects.filter(id__in=ids).update(is_am_ctte=True)
    log.info("%d CTTE members", bmodels.AM.objects.filter(is_am_ctte=True).count())


def compute_process_is_active():
    """
    Compute Process.is_active from Process.progress
    """
    cursor = connection.cursor()
    cursor.execute("""
    UPDATE process SET is_active=(progress NOT IN (%s, %s))
    """, (const.PROGRESS_DONE, const.PROGRESS_CANCELLED))
    log.info("%d/%d active processes",
             bmodels.Process.objects.filter(is_active=True).count(),
             cursor.rowcount)


def check_one_process_per_person():
    """
    Check that one does not have more than one open process at the current time
    """
    from django.db.models import Count
    for p in bmodels.Person.objects.filter(processes__is_active=True) \
             .annotate(num_processes=Count("processes")) \
             .filter(num_processes__gt=1):
        log.warning("%s has %d open processes", p, p.num_processes)
        for idx, proc in enumerate(p.processes.filter(is_active=True)):
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

        # Run procedures
        for prefix in ("backup", "compute", "check"):
            for k, v in globals().iteritems():
                if not k.startswith(prefix + "_"): continue
                log.info("running %s", k)
                v()
