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
from . import const
import datetime

class Person(models.Model):
    """
    A person (DM, DD, AM, applicant, FD member, DAM, anything)
    """
    class Meta:
        db_table = "person"

    # FIXME: is this used?
    title = models.CharField(max_length=10, null=True, help_text="title (Dr, Mr, ...)")
    cn = models.CharField("first name", max_length=250, null=False)
    mn = models.CharField("middle name", max_length=250, null=True)
    # This can be null for people like Wookey who only have one name
    sn = models.CharField("last name", max_length=250, null=True)
    email = models.EmailField("email address", null=False, unique=True)
    # This is null for people who still have not picked one
    # FIXME: it should be unique=True, but we need to check DB behaviour of
    # unique=True for NULLs
    uid = models.CharField("Debian account name", max_length=32, null=True)
    # GPG fingerprint, null until one has been provided
    # FIXME: it should be unique=True, but we need to check DB behaviour of
    # unique=True for NULLs
    gpgfpr = models.CharField("GPG key fingerprint", max_length=80, null=True)
    status = models.CharField("current status in the project", max_length=20, null=True,
                              choices=[x[1:3] for x in const.ALL_STATUS])
    # FIXME: no password field for now; hopefully we can do away with the need
    # of maintaining a password database

    @property
    def fullname(self):
        if self.mn is None:
            return "%s %s" % (self.cn, self.sn)
        else:
            return "%s %s %s" % (self.cn, self.mn, self.sn)

    def __unicode__(self):
        return u"%s <%s>" % (self.fullname, self.email)

    def __repr__(self):
        return "%s <%s> [uid:%s, status:%s]" % (self.fullname.encode("unicode_escape"), self.email, self.uid, self.status)


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

class Process(models.Model):
    """
    A process through which a person gets a new status
    """
    # TODO: fsck-style constraint of one Process in-progress per person
    class Meta:
        db_table = "process"
        # FIXME: getting rid of this requirement, so that a Process is a self
        # contained consecutive series of events. One can see the history of a
        # person by looking at the list of past processes.
        # unique_together = ("person", "applying_for")

    person = models.ForeignKey(Person, related_name="processes", on_delete=models.CASCADE)

    applying_for = models.CharField("target status", max_length=20, null=False,
                                    choices=[x[1:3] for x in const.ALL_STATUS])
    progress = models.CharField(max_length=20, null=False,
                                choices=[x[1:3] for x in const.ALL_PROGRESS])

    # This is NULL until one gets a manager
    manager = models.ForeignKey(AM, related_name="processed", null=True, on_delete=models.PROTECT)

    def __unicode__(self):
        return u"%s to become %s (%s)" % (unicode(self.person), self.applying_for, self.progress)

    # FIXME: should we do this just by min(log) (and ended by max(log)) ?
    #started = models.DateTimeField(null=False, default=datetime.datetime.utcnow)

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

    changed_by = models.ForeignKey(Person, related_name="log_written", on_delete=models.PROTECT, null=True)
    process = models.ForeignKey(Process, related_name="log", on_delete=models.CASCADE)

    # Copied from Process when the log entry is created (FIXME: formerly logtype)
    progress = models.CharField(max_length=20, null=False,
                                choices=[x[1:3] for x in const.ALL_PROGRESS])

    # FIXME: this or link to Process?
    #person = models.ForeignKey(Person, related_name="log", on_delete=models.CASCADE)
    #applying_for = models.CharField(" in the project", max_length=20, null=True,
    #                          choices=[x[1:3] for x in const.ALL_STATUS])
    #applying_for = sa.Column(sa.String(10), nullable=False)

    logdate = models.DateTimeField(null=False, default=datetime.datetime.utcnow)
    logtext = models.TextField(null=False)

    def __unicode__(self):
        return u"%s: %s" % (self.logdate, self.logtext)
