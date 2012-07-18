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

from __future__ import absolute_import
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from . import const
import datetime
import urllib
import os.path

PROCESS_MAILBOX_DIR = getattr(settings, "PROCESS_MAILBOX_DIR", "/org/nm.debian.org/mbox/applicants/")


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

# See http://stackoverflow.com/questions/454436/unique-fields-that-allow-nulls-in-django
class CharNullField(models.CharField):
    description = "CharField that stores NULL but returns ''"

    # this is the value right out of the db, or an instance
    def to_python(self, value):
       if isinstance(value, models.CharField): # if an instance, just return the instance
           return value
       if value is None:
           # if the db has a NULL, convert it into the Django-friendly '' string
           return ""
       else:
           # otherwise, return just the value
           return value

    # catches value right before sending to db
    def get_db_prep_value(self, value, connection, prepared=False):
       if value=="":
           # if Django tries to save '' string, send the db None (NULL)
           return None
       else:
           # otherwise, just pass the value
           return value

class TextNullField(models.TextField):
    description = "TextField that stores NULL but returns ''"

    # this is the value right out of the db, or an instance
    def to_python(self, value):
       if isinstance(value, models.TextField): # if an instance, just return the instance
           return value
       if value is None:
           # if the db has a NULL, convert it into the Django-friendly '' string
           return ""
       else:
           # otherwise, return just the value
           return value

    # catches value right before sending to db
    def get_db_prep_value(self, value, connection, prepared=False):
       if value=="":
           # if Django tries to save '' string, send the db None (NULL)
           return None
       else:
           # otherwise, just pass the value
           return value


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
    uid = CharNullField("Debian account name", max_length=32, null=True, unique=True, blank=True)
    # OpenPGP fingerprint, NULL until one has been provided
    fpr = CharNullField("OpenPGP key fingerprint", max_length=80, null=True, unique=True, blank=True)
    status = models.CharField("current status in the project", max_length=20, null=False,
                              choices=[(x.tag, x.ldesc) for x in const.ALL_STATUS])
    status_changed = models.DateTimeField("when the status last changed", null=False, default=datetime.datetime.utcnow)
    fd_comment = models.TextField("Front Desk comments", null=True, blank=True)
    # null=True because we currently do not have the info for old entries
    created = models.DateTimeField("Person record created", null=True, default=datetime.datetime.utcnow)

    @property
    def is_am(self):
        try:
            return self.am is not None
        except AM.DoesNotExist:
            return False

    @property
    def is_admin(self):
        am = self.am_or_none
        if am is None: return False
        return am.is_admin

    @property
    def am_or_none(self):
        try:
            return self.am
        except AM.DoesNotExist:
            return None

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

        # Otherwise the AM can edit if manager of an active process for this person
        try:
            Process.objects.get(manager=am, person=self, is_active=True)
        except Process.DoesNotExist:
            return False

        return True

    def can_advocate_as_dd(self, person):
        """
        Check if this person can advocate that person as DD
        """
        dd_statuses = (const.STATUS_DD_U, const.STATUS_DD_NU)
        # Advocate must be DD
        if self.status not in dd_statuses:
            return False

        # Applicant must not be DD
        if person.status in dd_statuses:
            return False

        # One must not be advocate already
        for p in person.processes.filter(is_active=True, applying_for__in=dd_statuses):
            if self in p.advocates.all():
                return False

        return True

    @property
    def fullname(self):
        if not self.mn:
            if not self.sn:
                return self.cn
            else:
                return "%s %s" % (self.cn, self.sn)
        else:
            if not self.sn:
                return "%s %s" % (self.cn, self.mn)
            else:
                return "%s %s %s" % (self.cn, self.mn, self.sn)

    def __unicode__(self):
        return u"%s <%s>" % (self.fullname, self.email)

    def __repr__(self):
        return "%s <%s> [uid:%s, status:%s]" % (self.fullname.encode("unicode_escape"), self.email, self.uid, self.status)

    @models.permalink
    def get_absolute_url(self):
        return ("person", (), dict(key=self.lookup_key))

    def get_ddpo_url(self):
        return u"http://qa.debian.org/developer.php?%s" % urllib.urlencode(dict(login=self.email))

    def get_portfolio_url(self):
        parms = dict(
            email=self.email,
            name=self.fullname.encode("utf-8"),
            gpgfp="",
            username="",
            nonddemail=self.email,
            aliothusername="",
            wikihomepage="",
            forumsid=""
        )
        if self.fpr:
            parms["gpgfp"] = self.fpr
        if self.uid:
            parms["username"] = self.uid
        return u"http://portfolio.debian.net/result?%s" % urllib.urlencode(parms)

    def get_allowed_processes(self):
        "Return a lits of processes that this person can begin"
        already_applying = frozenset(x["applying_for"] for x in self.processes.filter(is_active=True).values("applying_for"))

        pre_dd_statuses = frozenset((const.STATUS_MM, const.STATUS_MM_GA,
                                     const.STATUS_DM, const.STATUS_DM_GA,
                                     const.STATUS_EMERITUS_DD, const.STATUS_EMERITUS_DM,
                                     const.STATUS_REMOVED_DD, const.STATUS_REMOVED_DM))

        already_applying_for_dd = const.STATUS_DD_U in already_applying or const.STATUS_DD_NU in already_applying

        res = []
        if self.status == const.STATUS_MM and const.STATUS_MM_GA not in already_applying:
            res.append(const.STATUS_MM_GA)
        if self.status == const.STATUS_DM and const.STATUS_DM_GA not in already_applying:
            res.append(const.STATUS_DM_GA)
        if self.status == const.STATUS_MM and const.STATUS_DM not in already_applying:
            res.append(const.STATUS_DM)
        if self.status == const.STATUS_MM_GA and const.STATUS_DM_GA not in already_applying:
            res.append(const.STATUS_DM_GA)
        if self.status in pre_dd_statuses and not already_applying_for_dd:
            res.append(const.STATUS_DD_U)
            res.append(const.STATUS_DD_NU)
        return res

    @property
    def active_processes(self):
        """
        Return a list of all the active Processes for this person, if any; else
        the empty list.
        """
        return list(Process.objects.filter(person=self, is_active=True).order_by("id"))

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
        try:
            if "@" in key:
                return cls.objects.get(email=key)
            elif len(key) > 32:
                return cls.objects.get(fpr=key)
            else:
                return cls.objects.get(uid=key)
        except cls.DoesNotExist:
            return None


class AM(models.Model):
    """
    Extra info for people who are or have been AMs, FD members, or DAMs
    """
    class Meta:
        db_table = "am"

    person = models.OneToOneField(Person, related_name="am")
    slots = models.IntegerField(null=False, default=1)
    is_am = models.BooleanField("Active AM", null=False, default=True)
    is_fd = models.BooleanField("FD member", null=False, default=False)
    is_dam = models.BooleanField("DAM", null=False, default=False)
    # Automatically computed as true if any applicant was approved in the last
    # 6 months
    is_am_ctte = models.BooleanField("NM CTTE member", null=False, default=False)
    # null=True because we currently do not have the info for old entries
    created = models.DateTimeField("AM record created", null=True, default=datetime.datetime.utcnow)

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

    @models.permalink
    def get_absolute_url(self):
        return ("person", (), dict(key=self.person.lookup_key))

    @property
    def is_admin(self):
        return self.is_fd or self.is_dam

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
          LEFT OUTER JOIN process ON process.manager_id=am.id
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

    @property
    def lookup_key(self):
        """
        Return a key that can be used to look up this manager in the database
        using AM.lookup.

        Currently, this is the lookup key of the person.
        """
        return self.person.lookup_key

    @classmethod
    def lookup(cls, key):
        p = Person.lookup(key)
        if p is None: return None
        return p.am_or_none


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

    applying_as = models.CharField("original status", max_length=20, null=False,
                                    choices=[x[1:3] for x in const.ALL_STATUS])
    applying_for = models.CharField("target status", max_length=20, null=False,
                                    choices=[x[1:3] for x in const.ALL_STATUS])
    progress = models.CharField(max_length=20, null=False,
                                choices=[x[1:3] for x in const.ALL_PROGRESS])

    # This is NULL until one gets a manager
    manager = models.ForeignKey(AM, related_name="processed", null=True, blank=True)
    # 1.3-only: manager = models.ForeignKey(AM, related_name="processed", null=True, on_delete=models.PROTECT)

    advocates = models.ManyToManyField(Person, related_name="advocated", blank=True,
                                limit_choices_to={ "status__in": (const.STATUS_DD_U, const.STATUS_DD_NU) })

    # True if progress NOT IN (PROGRESS_DONE, PROGRESS_CANCELLED)
    is_active = models.BooleanField(null=False, default=False)

    archive_key = models.CharField("mailbox archive key", max_length=128, null=False, unique=True)

    def save(self, *args, **kw):
        if not self.archive_key:
            ts = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            if self.person.uid:
                self.archive_key = "%s-%s-%s" % (ts, self.applying_for, self.person.uid)
            else:
                self.archive_key = "%s-%s-%s" % (ts, self.applying_for, self.person.email)
        super(Process, self).save(*args, **kw)

    def __unicode__(self):
        return u"%s to become %s (%s)" % (
            unicode(self.person),
            const.ALL_STATUS_DESCS.get(self.applying_for, self.applying_for),
            const.ALL_PROGRESS_DESCS.get(self.progress, self.progress),
        )

    def __repr__(self):
        return "%s %s->%s" % (
            self.person.lookup_key,
            self.person.status,
            self.applying_for)

    @models.permalink
    def get_absolute_url(self):
        return ("public_process", (), dict(key=self.lookup_key))

    @property
    def lookup_key(self):
        """
        Return a key that can be used to look up this process in the database
        using Process.lookup.

        Currently, this is the email if the process is active, else the id.
        """
        if self.is_active:
            if self.person.processes.filter(is_active=True).count() == 1:
                return self.person.email
            else:
                return self.id
        else:
            return self.id

    @classmethod
    def lookup(cls, key):
        if key.isdigit():
            try:
                return cls.objects.get(id=int(key))
            except cls.DoesNotExist:
                return None
        else:
            try:
                if "@" not in key:
                    p = Person.objects.get(uid=key)
                else:
                    p = Person.objects.get(email=key)
            except Person.DoesNotExist:
                return None

            res = p.active_processes
            if res: return res[0]

            try:
                from django.db.models import Max
                return p.processes.annotate(last_change=Max("log__logdate")).order_by("-last_change")[0]
            except IndexError:
                return None

    @property
    def mailbox_file(self):
        """
        Return the pathname of the archival mailbox, or None if it does not
        exist
        """
        fname = os.path.join(PROCESS_MAILBOX_DIR, self.archive_key) + ".mbox"
        if os.path.exists(fname):
            return fname
        return None

    def can_be_edited(self, am=None):
        # FD and DAM can edit anything
        if am is not None and (am.is_fd or am.is_dam):
            return True

        # If the process is closed, then AMs cannot edit it
        if not self.is_active:
            return False

        # If we do not check by AM, we're done
        if am is None:
            return True

        # Otherwise the AM can edit if manager of this process
        return self.manager == am

    class DurationStats(object):
        AM_STATUSES = frozenset((const.PROGRESS_AM_HOLD, const.PROGRESS_AM))

        def __init__(self):
            self.first = None
            self.last = None
            self.last_progress = None
            self.total_am_time = 0
            self.total_amhold_time = 0
            self.last_am_time = 0
            self.last_amhold_time = 0
            self.last_am_history = []
            self.last_log_text = None

        def process_last_am_history(self, end=None):
            """
            Compute AM duration stats.

            end is the datetime of the end of the AM stats period. If None, the
            current datetime is used.
            """
            if not self.last_am_history: return
            if end is None:
                end = datetime.datetime.utcnow()

            time_for_progress = dict()
            period_start = None
            for l in self.last_am_history:
                if period_start is None:
                    period_start = l
                elif l.progress != period_start.progress:
                    days = (l.logdate - period_start.logdate).days
                    time_for_progress[period_start.progress] = \
                            time_for_progress.get(period_start.progress, 0) + days
                    period_start = l

            if period_start:
                days = (end - period_start.logdate).days
                time_for_progress[period_start.progress] = \
                        time_for_progress.get(period_start.progress, 0) + days

            self.last_am_time = time_for_progress.get(const.PROGRESS_AM, 0)
            self.last_amhold_time = time_for_progress.get(const.PROGRESS_AM_HOLD, 0)
            self.total_am_time += self.last_am_time
            self.total_amhold_time += self.last_amhold_time

            self.last_am_history = []

        def process_log(self, l):
            """
            Process a log entry. Log entries must be processed in cronological
            order.
            """
            if self.first is None: self.first = l

            if l.progress in self.AM_STATUSES:
                if self.last_progress not in self.AM_STATUSES:
                    self.last_am_time = 0
                    self.last_amhold_time = 0
                self.last_am_history.append(l)
            elif self.last_progress in self.AM_STATUSES:
                self.process_last_am_history(end=l.logdate)

            self.last = l
            self.last_progress = l.progress

        def stats(self):
            """
            Compute a dict with statistics
            """
            # Process pending AM history items: happens when the last log has
            # AM_STATUSES status
            self.process_last_am_history()

            return dict(
                # Date the process started
                log_first=self.first,
                # Date of the last log entry
                log_last=self.last,
                # Total duration in days
                total_duration=(self.last.logdate-self.first.logdate).days,
                # Days spent in AM
                total_am_time=self.total_am_time,
                # Days spent in AM_HOLD
                total_amhold_time=self.total_amhold_time,
                # Days spent in AM with the last AM
                last_am_time=self.last_am_time,
                # Days spent in AM_HOLD with the last AM
                last_amhold_time=self.last_amhold_time,
                # Last nonempty log text
                last_log_text=self.last_log_text,
            )

    def duration_stats(self):
        stats_maker = self.DurationStats()
        for l in self.log.order_by("logdate"):
            stats_maker.process_log(l)
        return stats_maker.stats()

    def annotate_with_duration_stats(self):
        s = self.duration_stats()
        for k, v in s.iteritems():
            setattr(self, k, v)

    def finalize(self, logtext, tstamp=None):
        """
        Bring the process to completion, by setting its progress to DONE,
        adding a log entry and updating the person status.
        """
        if self.progress != const.PROGRESS_DAM_OK:
            raise ValueError("cannot finalise progress %s: status is %s instead of %s" % (
                unicode(self), self.progress, const.PROGRESS_DAM_OK))

        if tstamp is None:
            tstamp = datetime.datetime.utcnow()

        self.progress = const.PROGRESS_DONE
        self.person.status = self.applying_for
        self.person.status_changed = tstamp
        l = Log(
            changed_by=None,
            process=self,
            progress=self.progress,
            logdate=tstamp,
            logtext=logtext
        )
        l.save()
        self.save()
        self.person.save()

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
                                choices=[(x.tag, x.ldesc) for x in const.ALL_PROGRESS])

    logdate = models.DateTimeField(null=False, default=datetime.datetime.utcnow)
    logtext = TextNullField(null=True, blank=True)

    def __unicode__(self):
        return u"%s: %s" % (self.logdate, self.logtext)

    @classmethod
    def for_process(cls, proc, **kw):
        kw.setdefault("process", proc)
        kw.setdefault("progress", proc.progress)
        return cls(**kw)


MOCK_FD_COMMENTS = [
    "Cannot get GPG signatures because of extremely sensitive teeth",
    "Only has internet connection on days which are prime numbers",
    "Is a werewolf: warn AM to ignore replies when moon is full",
    "Is a vampire: warn AM not to invite him/her into their home",
    "Is a daemon: if unresponsive, contact Enrico for details about summoning ritual",
]

MOCK_LOGTEXTS = [
    "ok", "hmm", "meh", "asdf", "moo", "...", u"üñįç♥ḋə"
]

def export_db(full=False):
    """
    Export the whole databae into a json-serializable array.

    If full is False, then the output is stripped of privacy-sensitive
    information.
    """
    import random

    fd = list(Person.objects.filter(am__is_fd=True))

    # Use order_by so that dumps are easier to diff
    for idx, p in enumerate(Person.objects.all().order_by("uid", "email")):
        # Person details
        ep = dict(
            key=p.lookup_key,
            cn=p.cn,
            mn=p.mn,
            sn=p.sn,
            email=p.email,
            uid=p.uid,
            fpr=p.fpr,
            status=p.status,
            status_changed=p.status_changed,
            created=p.created,
            fd_comment=None,
            am=None,
            processes=[],
        )

        if full:
            ep["fd_comment"] = p.fd_comment
        else:
            if random.randint(1, 100) < 20:
                ep["fd_comment"] = random.choice(MOCK_FD_COMMENTS)

        # AM details
        am = p.am_or_none
        if am:
            ep["am"] = dict(
                slots=am.slots,
                is_am=am.is_am,
                is_fd=am.is_fd,
                is_dam=am.is_dam,
                is_am_ctte=am.is_am_ctte,
                created=am.created)

        # Process details
        for pr in p.processes.all().order_by("applying_for"):
            epr = dict(
                applying_as=pr.applying_as,
                applying_for=pr.applying_for,
                progress=pr.progress,
                is_active=pr.is_active,
                archive_key=pr.archive_key,
                manager=None,
                advocates=[],
                log=[],
            )
            ep["processes"].append(epr)

            # Also get a list of actors who can be used for mock logging later
            if pr.manager:
                epr["manager"] = pr.manager.lookup_key
                actors = [pr.manager.person] + fd
            else:
                actors = fd

            for a in pr.advocates.all():
                epr["advocates"].append(a.lookup_key)

            # Log details
            last_progress = None
            for l in pr.log.all().order_by("logdate"):
                if not full and last_progress == l.progress:
                    # Consolidate consecutive entries to match simplification
                    # done by public interface
                    continue

                el = dict(
                    changed_by=None,
                    progress=l.progress,
                    logdate=l.logdate,
                    logtext=None)

                if full:
                    if l.changed_by:
                        el["changed_by"] = l.changed_by.lookup_key
                    el["logtext"] = l.logtext
                else:
                    if l.changed_by:
                        el["changed_by"] = random.choice(actors).lookup_key
                    el["logtext"] = random.choice(MOCK_LOGTEXTS)

                epr["log"].append(el)

                last_progress = l.progress

        yield ep

