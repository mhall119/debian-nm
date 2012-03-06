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

from __future__ import absolute_import
from django.db import models
from django.contrib.auth.models import User
from . import const
import datetime

# Implementation notes
#
#  * Multiple NULL values in UNIQUE fields
#    They are supported in sqlite, postgresql and mysql, and that is good
#    enough.
#    See http://www.sqlite.org/nulls.html
#    See http://stackoverflow.com/questions/454436/unique-fields-that-allow-nulls-in-django
#        for possible Django gotchas
#  * Denormalised fields
#    Some limited redundancy is tolerated for convenience, but it is
#    checked/enforced/recomputed during daily maintenance procedures
#


class Person(models.Model):
    """
    A person (DM, DD, AM, applicant, FD member, DAM, anything)
    """
    class Meta:
        db_table = "person"

    # Link to Django web user information
    user = models.OneToOneField(User, null=True)

    #  enrico> Ok, it's time to try deployment. If it goes like debtags.d.n,
    #          then we need mod_wsgi to be enabled on nono to run
    #          nono:/srv/nm.debian.org/nm2/nm2.wsgi in something like /nm2 (to
    #          be moved to / once it's ready)
    #  enrico> should I do a RT ticket for it?
    # @sgran> please
    #  enrico> sgran: done
    # @sgran> thanks
    #  enrico> For people like Wookey, do you prefer we use only cn or only sn?
    #          "sn" is used currently, and "cn" has a dash, but rather than
    #          cargo-culting that in the new NM 
    # double check it with you 
    # @sgran> cn would be more usual
    # @sgran> cn is the "whole name" and you can split it up into givenName + sn if you like
    #  phil> Except that in Debian LDAP it isn't.
    #  enrico> sgran: ok. should I use 'cn' for potential new cases then?
    # @sgran> phil: indeed
    # @sgran> but if we keep doing it the other way, we'll never be in a position to change
    # @sgran> enrico: please
    #  enrico> sgran: ack

    # First/Given name, or only name in case of only one name
    cn = models.CharField("first name", max_length=250, null=False)
    mn = models.CharField("middle name", max_length=250, null=True, blank=True)
    sn = models.CharField("last name", max_length=250, null=True, blank=True)
    email = models.EmailField("email address", null=False, unique=True)
    # This is null for people who still have not picked one
    uid = models.CharField("Debian account name", max_length=32, null=True, unique=True, blank=True)
    # OpenPGP fingerprint, NULL until one has been provided
    fpr = models.CharField("OpenPGP key fingerprint", max_length=80, null=True, unique=True, blank=True)
    status = models.CharField("current status in the project", max_length=20, null=False,
                              choices=[x[1:3] for x in const.ALL_STATUS])
    fd_comment = models.TextField("Front Desk comments", null=True, blank=True)
    # FIXME: no password field for now; hopefully we can do away with the need
    # of maintaining a password database

    @property
    def is_am(self):
        try:
            return self.am is not None
        except AM.DoesNotExist:
            return False

    def can_be_edited(self, am=None):
        # If the person is already in LDAP, then we cannot edit their info
        if self.status not in (const.STATUS_MM, const.STATUS_DM):
            return False

        # If we do not check by AM, we're done
        if am is None:
            return True

        # FD and DAMs can edit anything
        if am.is_fd or am.is_dam:
            return True

        # Otherwise the AM can edit if manager of an active process
        try:
            for proc in Process.objects.get(manager=am, is_active=True):
                pass
        except Process.DoesNotExist:
            return False

        return True

    @property
    def fullname(self):
        if self.mn is None:
            if self.sn is None:
                return self.cn
            else:
                return "%s %s" % (self.cn, self.sn)
        else:
            if self.sn is None:
                return "%s %s" % (self.cn, self.mn)
            else:
                return "%s %s %s" % (self.cn, self.mn, self.sn)

    def __unicode__(self):
        return u"%s <%s>" % (self.fullname, self.email)

    def __repr__(self):
        return "%s <%s> [uid:%s, status:%s]" % (self.fullname.encode("unicode_escape"), self.email, self.uid, self.status)

    @property
    def active_process(self):
        """
        Return the active Process for this person, if any, else None
        """
        try:
            return Process.objects.get(person=self, is_active=True)
        except Process.DoesNotExist:
            return None

    @property
    def lookup_key(self):
        """
        Return a key that can be used to look up this person in the database
        using Person.lookup.

        Currently, this is the uid if available, else the email.
        """
        if self.uid:
            return self.uid
        else:
            return self.email

    @classmethod
    def lookup(cls, key):
        if "@" in key:
            return cls.objects.get(email=key)
        else:
            return cls.objects.get(uid=key)


class AM(models.Model):
    """
    Extra info for people who are or have been AMs, FD members, or DAMs
    """
    class Meta:
        db_table = "am"

    person = models.OneToOneField(Person, related_name="am")
    slots = models.IntegerField(null=False, default=1)
    is_am = models.BooleanField(null=False, default=True)
    is_fd = models.BooleanField(null=False, default=False)
    is_dam = models.BooleanField(null=False, default=False)
    # Automatically computed as true if any applicant was approved in the last
    # 6 months
    is_am_ctte = models.BooleanField(null=False, default=False)

    def __unicode__(self):
        return u"%s %c%c%c" % (
            unicode(self.person),
            "a" if self.is_am else "-",
            "f" if self.is_fd else "-",
            "d" if self.is_dam else "-",
        )

    def __repr__(self):
        return "%s %c%c%c slots:%d" % (
            repr(self.person),
            "a" if self.is_am else "-",
            "f" if self.is_fd else "-",
            "d" if self.is_dam else "-",
            self.slots)

    def applicant_stats(self):
        """
        Return 4 stats about the am (cur, max, hold, done).

        cur: number of active applicants
        max: number of slots
        hold: number of applicants on hold
        done: number of applicants successfully processed
        """
        cur = 0
        hold = 0
        done = 0
        for p in Process.objects.filter(manager=self):
            if p.progress == const.PROGRESS_DONE:
                done += 1
            elif p.progress == const.PROGRESS_AM_HOLD:
                hold += 1
            else:
                cur += 1
        return cur, self.slots, hold, done

    @classmethod
    def list_free(cls):
        """
        Get a list of active AMs with free slots, ordered by uid.

        Each AM is annotated with stats_active, stats_held and stats_free, with
        the number of NMs, held NMs and free slots.
        """
        from django.db import connection

        # Compute statistics indexed by AM id
        cursor = connection.cursor()
        cursor.execute("""
        SELECT am.id,
               sum(case when process.progress in (%s, %s) then 1 else 0 end) as active,
               sum(case when process.progress=%s then 1 else 0 end) as held
          FROM am
          JOIN process ON process.manager_id=am.id
         WHERE am.is_am AND am.slots > 0
         GROUP BY am.id
        """, (const.PROGRESS_AM_RCVD, const.PROGRESS_AM, const.PROGRESS_AM_HOLD,))
        stats = dict()
        for amid, active, held in cursor:
            stats[amid] = (active, held)

        res = []
        for a in cls.objects.filter(id__in=stats.keys()).order_by("person__uid"):
            active, held = stats.get(a.id, (0, 0, 0))
            a.stats_active = active
            a.stats_held = held
            a.stats_free = a.slots - active
            if a.stats_free <= 0:
                continue
            res.append(a)
        return res


class Process(models.Model):
    """
    A process through which a person gets a new status

    There can be multiple 'Process'es per Person, but only one of them can be
    active at any one time. This is checked during maintenance.
    """
    class Meta:
        db_table = "process"

    person = models.ForeignKey(Person, related_name="processes")
    # 1.3-only: person = models.ForeignKey(Person, related_name="processes", on_delete=models.CASCADE)

    applying_for = models.CharField("target status", max_length=20, null=False,
                                    choices=[x[1:3] for x in const.ALL_STATUS])
    progress = models.CharField(max_length=20, null=False,
                                choices=[x[1:3] for x in const.ALL_PROGRESS])

    # This is NULL until one gets a manager
    manager = models.ForeignKey(AM, related_name="processed", null=True)
    # 1.3-only: manager = models.ForeignKey(AM, related_name="processed", null=True, on_delete=models.PROTECT)

    advocates = models.ManyToManyField(Person, related_name="advocated", blank=True)

    # True if progress NOT IN (PROGRESS_DONE, PROGRESS_CANCELLED)
    is_active = models.BooleanField(null=False, default=False)

    def __unicode__(self):
        return u"%s to become %s (%s)" % (
            unicode(self.person),
            const.ALL_STATUS_DESCS.get(self.applying_for, self.applying_for),
            const.ALL_PROGRESS_DESCS.get(self.progress, self.progress),
        )

    @property
    def lookup_key(self):
        """
        Return a key that can be used to look up this process in the database
        using Process.lookup.

        Currently, this is the email if the process is active, else the id.
        """
        if self.is_active:
            return self.person.email
        else:
            return self.id

    @classmethod
    def lookup(cls, key):
        if key.isdigit():
            return cls.objects.get(id=int(key))
        else:
            p = Person.objects.get(email=key)
            try:
                return p.active_process
            except Process.DoesNotExist:
                from django.db.models import Max
                return p.processes.annotate(last_change=Max("log__logdate")).order_by("-last_change")[0]

    #def get_log(self, desc=False, max=None):
    #    res = orm.object_session(self) \
    #            .query(Log) \
    #            .filter_by(account_id=self.account_id, applying_for=self.applying_for)
    #    if desc:
    #        res = res.order_by(Log.logdate.desc())
    #    else:
    #        res = res.order_by(Log.logdate)
    #    if max:
    #        res = res.limit(max)
    #    return res.all()

    #def make_log_entry(self, editor, text):
    #    """
    #    Create a log entry for the current process
    #    """
    #    return Log(account=self.account,
    #              applying_for=self.applying_for,
    #              logtype=self.progress,
    #              changed_by=editor,
    #              logtext=text)

class Log(models.Model):
    """
    A log entry about anything that happened during a process
    """
    class Meta:
        db_table = "log"

    changed_by = models.ForeignKey(Person, related_name="log_written", null=True)
    # 1.3-only: changed_by = models.ForeignKey(Person, related_name="log_written", on_delete=models.PROTECT, null=True)
    process = models.ForeignKey(Process, related_name="log")
    # 1.3-only: process = models.ForeignKey(Process, related_name="log", on_delete=models.CASCADE)

    # Copied from Process when the log entry is created
    progress = models.CharField(max_length=20, null=False,
                                choices=[x[1:3] for x in const.ALL_PROGRESS])

    logdate = models.DateTimeField(null=False, default=datetime.datetime.utcnow)
    logtext = models.TextField(null=False)

    def __unicode__(self):
        return u"%s: %s" % (self.logdate, self.logtext)
