# nm.debian.org website maintenance
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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf import settings
from django_maintenance import MaintenanceTask
from django.db import connection, transaction
from django.contrib.sites.models import Site
from . import models as bmodels
from . import utils, const
import gzip
import datetime
import time
import json
import os.path
import logging

log = logging.getLogger(__name__)

BACKUP_DIR = getattr(settings, "BACKUP_DIR", None)

class MakeLink(MaintenanceTask):
    NAME = "link"

    def __init__(self, *args, **kw):
        super(MakeLink, self).__init__(*args, **kw)
        self.site = Site.objects.get_current()

    def __call__(self, obj):
        if self.site.domain == "localhost":
            return "http://localhost:8000" + obj.get_absolute_url()
        else:
            return "https://%s%s" % (self.site.domain, obj.get_absolute_url())

class BackupDB(MaintenanceTask):
    """
    Backup of the whole database
    """
    def run(self):
        if BACKUP_DIR is None:
            log.info("BACKUP_DIR is not set: skipping backups")
            return

        people = list(bmodels.export_db(full=True))

        class Serializer(json.JSONEncoder):
            def default(self, o):
                if hasattr(o, "strftime"):
                    return o.strftime("%Y-%m-%d %H:%M:%S")
                return json.JSONEncoder.default(self, o)

        # Base filename for the backup
        fname = os.path.join(BACKUP_DIR, datetime.datetime.utcnow().strftime("%Y%m%d-db-full.json.gz"))
        log.info("%s: backing up to %s", self.IDENTIFIER, fname)
        if self.maint.dry_run: return

        # Use a sequential number to avoid overwriting old backups when run manually
        while os.path.exists(fname):
            time.sleep(0.5)
            fname = os.path.join(BACKUP_DIR, datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S-db-full.json.gz"))
        # Write the backup file
        with utils.atomic_writer(fname, 0640) as fd:
            try:
                gzfd = gzip.GzipFile(filename=fname[:-3], mode="w", compresslevel=9, fileobj=fd)
                json.dump(people, gzfd, cls=Serializer, indent=2)
            finally:
                gzfd.close()

class ComputeAMCTTE(MaintenanceTask):
    """
    Compute AM Committee membership
    """
    DEPENDS = [BackupDB]

    @transaction.commit_on_success
    def run(self):
        # Set all to False
        bmodels.AM.objects.update(is_am_ctte=False)

        cutoff = datetime.datetime.utcnow()
        cutoff = cutoff - datetime.timedelta(days=30*6)

        # Set the active ones to True
        cursor = connection.cursor()
        cursor.execute("""
        SELECT am.id
          FROM am
          JOIN process p ON p.manager_id=am.id AND p.progress IN (%s, %s)
          JOIN log ON log.process_id=p.id AND log.logdate > %s
         WHERE am.is_am AND NOT am.is_fd AND NOT am.is_dam
         GROUP BY am.id
        """, (const.PROGRESS_DONE, const.PROGRESS_CANCELLED, cutoff))
        ids = [x[0] for x in cursor]

        bmodels.AM.objects.filter(id__in=ids).update(is_am_ctte=True)
        transaction.commit_unless_managed()
        log.info("%s: %d CTTE members", self.IDENTIFIER, bmodels.AM.objects.filter(is_am_ctte=True).count())

class ComputeProcessActiveFlag(MaintenanceTask):
    """
    Compute Process.is_active from Process.progress
    """
    DEPENDS = [BackupDB]

    @transaction.commit_on_success
    def run(self):
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE process SET is_active=(progress NOT IN (%s, %s))
        """, (const.PROGRESS_DONE, const.PROGRESS_CANCELLED))
        transaction.commit_unless_managed()
        log.info("%s: %d/%d active processes",
                 self.IDENTIFIER,
                 bmodels.Process.objects.filter(is_active=True).count(),
                 cursor.rowcount)

class PersonExpires(MaintenanceTask):
    """
    Expire old Person records
    """
    DEPENDS = [BackupDB, MakeLink]

    @transaction.commit_on_success
    def run(self):
        """
        Generate a sequence of Person objects that have expired
        """
        today = datetime.date.today()
        for p in bmodels.Person.objects.filter(expires__lt=today):
            if p.status != const.STATUS_MM:
                log.info("%s: removing expiration date for %s who has become %s",
                         self.IDENTIFIER, self.maint.link(p), p.status)
                p.expires = None
                p.save()
            elif p.processes.exists():
                log.info("%s: removing expiration date for %s who now has process history",
                         self.IDENTIFIER, self.maint.link(p))
                p.expires = None
                p.save()
            else:
                log.info("%s: deleting expired Person %s", self.IDENTIFIER, p)
                p.delete()

class CheckOneProcessPerPerson(MaintenanceTask):
    """
    Check that one does not have more than one open process at the current time
    """
    DEPENDS = [MakeLink]

    def run(self):
        from django.db.models import Count
        for p in bmodels.Person.objects.filter(processes__is_active=True) \
                 .annotate(num_processes=Count("processes")) \
                 .filter(num_processes__gt=1):
            log.warning("%s: %s has %d open processes", self.IDENTIFIER, self.maint.link(p), p.num_processes)
            for idx, proc in enumerate(p.processes.filter(is_active=True)):
                log.warning("%s: %d: %s (%s)", self.IDENTIFIER, idx+1, self.maint.link(proc), repr(proc))

class CheckAMMustHaveUID(MaintenanceTask):
    """
    Check that AMs have a Debian login
    """
    def run(self):
        for am in bmodels.AM.objects.filter(person__uid=None):
            log.warning("%s: AM %d (person %d %s) has no uid", self.IDENTIFIER, am.id, am.person.id, am.person.email)

class CheckStatusProgressMatch(MaintenanceTask):
    """
    Check that the last process with progress 'done' has the same
    'applying_for' as the person status
    """
    def run(self):
        from django.db.models import Max
        for p in bmodels.Person.objects.all():
            try:
                last_proc = bmodels.Process.objects.filter(person=p, progress=const.PROGRESS_DONE).annotate(ended=Max("log__logdate")).order_by("-ended")[0]
            except IndexError:
                continue
            if p.status != last_proc.applying_for:
                log.warning("%s: %s has status %s but the last completed process was applying for %s",
                            self.IDENTIFIER, p.uid, p.status, last_proc.applying_for)

class CheckLogProgressMatch(MaintenanceTask):
    """
    Check that the last process with progress 'done' has the same
    'applying_for' as the person status
    """
    DEPENDS = [MakeLink]

    def run(self):
        for p in bmodels.Process.objects.filter(is_active=True):
            try:
                last_log = p.log.order_by("-logdate")[0]
            except IndexError:
                log.warning("%s: %s (%s) has no log entries", self.IDENTIFIER, self.maint.link(p), repr(p))
                continue
            if p.progress != last_log.progress:
                log.warning("%s: %s (%s) has progress %s but the last log entry has progress %s",
                            self.IDENTIFIER, self.maint.link(p), repr(p), p.progress, last_log.progress)

class CheckEnums(MaintenanceTask):
    """
    Consistency check of enum values
    """
    DEPENDS = [MakeLink]

    def run(self):
        statuses = [x.tag for x in const.ALL_STATUS]
        progresses = [x.tag for x in const.ALL_PROGRESS]

        for p in bmodels.Person.objects.exclude(status__in=statuses):
            log.warning("%s: %s: invalid status %s", self.IDENTIFIER, self.maint.link(p), p.status)

        for p in bmodels.Process.objects.exclude(applying_for__in=statuses):
            log.warning("%s: %s: invalid applying_for %s", self.IDENTIFIER, self.maint.link(p), p.applying_for)

        for p in bmodels.Process.objects.exclude(progress__in=progresses):
            log.warning("%s: %s: invalid progress %s", self.IDENTIFIER, self.maint.link(p), p.progress)

        for l in bmodels.Log.objects.exclude(progress__in=progresses):
            log.warning("%s: %s: log entry %d has invalid progress %s",
                        self.IDENTIFIER, self.maint.link(l.process), l.id, l.progress)

class CheckCornerCases(MaintenanceTask):
    """
    Check for known corner cases, to be fixed somehow eventually maybe in case
    they give trouble
    """
    def run(self):
        c = bmodels.Person.objects.filter(processes__isnull=True).count()
        if c > 0:
            log.warning("%s: %d Great Ancients found who have no Process entry", self.IDENTIFIER, c)

        c = bmodels.Person.objects.filter(status_changed__isnull=True).count()
        if c > 0:
            log.warning("%s: %d entries still have a NULL status_changed date", self.IDENTIFIER, c)

class CheckDjangoPermissions(MaintenanceTask):
    """
    Check consistency between Django permissions and flags in the AM model
    """
    DEPENDS = [MakeLink]

    def run(self):
        from django.contrib.auth.models import User
        from django.db.models import Q

        # Get the list of users that django thinks are powerful
        django_power_users = set()
        for u in User.objects.all():
            if u.is_staff or u.is_superuser:
                django_power_users.add(u.id)

        # Get the list of users that we think are powerful
        nm_power_users = set()
        for a in bmodels.AM.objects.filter(Q(is_fd=True) | Q(is_dam=True)):
            if a.person.user is None:
                log.warning("%s: %s: no corresponding django user", self.IDENTIFIER, self.maint.link(a.person))
            else:
                nm_power_users.add(a.person.user.id)

        for id in (django_power_users - nm_power_users):
            log.warning("%s: auth.models.User.id %d has powers that the NM site does not know about",
                        self.IDENTIFIER, id)
        for id in (nm_power_users - django_power_users):
            log.warning("%s: auth.models.User.id %d has powers in NM that django does not know about",
                        self.IDENTIFIER, id)

class Inconsistencies(MaintenanceTask):
    """
    Keep track of inconsistencies
    """
    NAME = "inconsistencies"
    DEPENDS = [MakeLink]

    def __init__(self, *args, **kw):
        super(Inconsistencies, self).__init__(*args, **kw)
        self.logger = log
        try:
            import inconsistencies.models as imodels
            self.imodels = imodels
        except ImportError:
            self.imodels = None

    def run(self):
        """
        Reset the inconsistency log at the start of maintenance
        """
        if not self.imodels: return
        self.imodels.InconsistentPerson.objects.all().delete()
        self.imodels.InconsistentProcess.objects.all().delete()
        self.imodels.InconsistentFingerprint.objects.all().delete()

    def log(self, *args, **kw):
        if self.imodels:
            self.logger.info(*args, **kw)
        else:
            self.logger.warning(*args, **kw)

    def log_person(self, maintproc, person, log, **kw):
        if self.imodels:
            self.imodels.InconsistentPerson.add_info(person, log=log, **kw)
        self.log("%s: %s %s", maintproc.IDENTIFIER, self.maint.link(person), log)

    def log_process(self, maintproc, process, log, **kw):
        if self.imodels:
            self.imodels.InconsistentProcess.add_info(process, log=log, **kw)
        self.log("%s: %s %s", maintproc.IDENTIFIER, self.maint.link(process), log)

    def log_fingerprint(self, maintproc, fpr, log, **kw):
        fpr = fpr.replace(" ", "")
        if self.imodels:
            self.imodels.InconsistentFingerprint.add_info(fpr, log=log, **kw)
        self.log("%s: %s %s", maintproc.IDENTIFIER, fpr, log)
