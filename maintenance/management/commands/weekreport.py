# nm.debian.org weekly report generation
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
from django.core.mail import send_mail
import django.db
from django.conf import settings
from django.db import connection, transaction
from django.contrib.sites.models import Site
from django.db.models import Count, Min, Max
from collections import defaultdict
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

# AM Inactivity threshold in days
INACTIVE_AM_PERIOD = 30

# AM_HOLD Inactivity threshold in days
INACTIVE_AMHOLD_PERIOD = 180

# Days one needs to have been DD in order to become AM
NEW_AM_THRESHOLD = 180

class Reporter(object):
    def __init__(self, since=None, until=None, twidth=72, **kw):
        if until is None:
            until = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0)
        if since is None:
            since = until - datetime.timedelta(days=7)
        self.since = since
        self.until = until
        self.twidth = twidth

    def print_proclist(self, out, procs, print_manager=True):
        """Format and print a list of processes to `out`. If `print_manager`
        is True, print a column with the AM login. The `procs` list needs to
        be annotated with a `last_log` property used to display the date."""
        print >>out

        col_uid = 0
        if print_manager:
            for p in procs:
                l = len(p.manager.person.uid)
                if l > col_uid:
                    col_uid = l

        for p in procs:
            if print_manager:
                print >>out, \
                    str(p.last_log.date()).rjust(12), \
                    p.manager.person.uid.ljust(col_uid), \
                    "%s <%s>" % (p.person.fullname, p.person.lookup_key)
            else:
                print >>out, \
                    str(p.last_log.date()).rjust(12), \
                    "%s <%s>" % (p.person.fullname, p.person.lookup_key)
        print >>out



    def subject(self):
        if (self.until - self.since).days == 7:
            return "NM report for week ending %s" % str(self.until.date())
        else:
            return "NM report from %s to %s" % (self.since.date(), self.until.date())

    def rep00_period(self, out, **opts):
        if (self.until - self.since).days == 7:
            print >>out, "For week ending %s." % str(self.until.date())
        else:
            print >>out, "From %s to %s." % (self.since.date(), self.until.date())

    def rep01_summary(self, out, **opts):
        "Weekly Summary Statistics"

        # Processes that started
        # We reuse last_log as that's what print_proclist expects
        new_procs = bmodels.Process.objects.filter(is_active=True) \
                                   .annotate(
                                       last_log=Min("log__logdate")) \
                                   .filter(last_log__gte=self.since)

        counts = defaultdict(list)
        for p in new_procs:
            counts[p.applying_for].append(p)

        for k, processes in sorted(counts.iteritems(), key=lambda x:const.SEQ_STATUS.get(x[0], 0)):
            print >>out, "%d more people applied to become a %s:" % (len(counts[k]), const.ALL_STATUS_DESCS.get(k, "(unknown)"))
            self.print_proclist(out, processes, False)

        # Processes that ended
        new_procs = bmodels.Process.objects.filter(progress=const.PROGRESS_DONE) \
                                   .annotate(
                                       last_log=Max("log__logdate")) \
                                   .filter(last_log__gte=self.since)

        counts = defaultdict(list)
        for p in new_procs:
            counts[p.applying_for].append(p)

        for k, processes in sorted(counts.iteritems(), key=lambda x:const.SEQ_STATUS.get(x[0], 0)):
            print >>out, "%d people became a %s:" % (len(counts[k]), const.ALL_STATUS_DESCS.get(k, "(unknown)"))
            self.print_proclist(out, processes, False)

    def rep02_newams(self, out, **opts):
        "New AM candidates"
        min_date = self.since - datetime.timedelta(days=NEW_AM_THRESHOLD)
        max_date = self.until - datetime.timedelta(days=NEW_AM_THRESHOLD)
        new_procs = bmodels.Process.objects.filter(progress=const.PROGRESS_DONE,
                                                   applying_for__in=[const.STATUS_DD_U, const.STATUS_DD_NU]) \
                                   .annotate(
                                       ended=Max("log__logdate")) \
                                   .filter(ended__gte=min_date, ended__lte=max_date) \
                                   .order_by("ended")
        count = new_procs.count()
        if count:
            print >>out, "%d DDs are now %d days old and can decide to become AMs: ;)" % (
                count, NEW_AM_THRESHOLD)
            print >>out
            for p in new_procs:
                print >>out, "  %s <%s>" % (p.person.fullname, p.person.uid)

    def rep03_amchecks(self, out, **opts):
        "AM checks"

        # Inactive AM processes
        procs = bmodels.Process.objects.filter(is_active=True, progress=const.PROGRESS_AM) \
                               .annotate(
                                   last_log=Max("log__logdate")) \
                               .filter(last_log__lte=self.until - datetime.timedelta(days=INACTIVE_AM_PERIOD)) \
                               .order_by("last_log")
        count = procs.count()
        if count > 0:
            print >>out, "%d processes have had no apparent activity in the last %d days:" % (
                count, INACTIVE_AM_PERIOD)
            self.print_proclist(out, procs)

        # Inactive AM_HOLD processes
        procs = bmodels.Process.objects.filter(is_active=True, progress=const.PROGRESS_AM_HOLD) \
                               .annotate(
                                   last_log=Max("log__logdate")) \
                               .filter(last_log__lte=self.until - datetime.timedelta(days=INACTIVE_AMHOLD_PERIOD)) \
                               .order_by("last_log")
        count = procs.count()
        if count > 0:
            print >>out, "%d processes have been on hold for longer than %d days:" % (
                count, INACTIVE_AMHOLD_PERIOD)
            self.print_proclist(out, procs)


    # $sql = "SELECT forename, surname, email FROM applicant WHERE newmaint IS NOT NULL AND newmaint BETWEEN NOW() - interval '6 months 1 week' AND NOW() - interval '6 months' ORDER BY newmaint DESC";
    #     $sth = $dbh->prepare($sql);
    #         $sth->execute();
    #             $sth->bind_columns(\$firstname, \$surname, \$email);
    #                 if ($sth->rows > 0) {
    #                             print $header;
    #                             print "The following DDs are now 6 months old and can decide to become AMs: ;)\n";
    #                             while($sth->fetch()) {
    #                                             print "$firstname $surname <$email>\n";
    #                                         }
    #                         }


    def run(self, out, **opts):
        """
        Run all weekly report functions
        """
        title = "Weekly Report on Debian New Members"
        print >>out, title.center(self.twidth)
        print >>out, ("=" * len(title)).center(self.twidth)

        import inspect
        for name, meth in sorted(inspect.getmembers(self, predicate=inspect.ismethod)):
            if not name.startswith("rep"): continue
            log.info("running %s", name)

            # Compute output for this method
            mout = StringIO()
            meth(codecs.getwriter("utf8")(mout), **opts)

            # Skip it if it had no output
            if not mout.getvalue():
                log.info("skipping %s as it had no output", name)
                continue

            # Else output it, with title and stuff
            print >>out
            if meth.__doc__:
                title = meth.__doc__.strip().split("\n")[0].strip()
                print >>out, title
                print >>out, "=" * len(title)
            out.write(mout.getvalue())

        print >>out


re_date = re.compile("^\d+-\d+-\d+$")
re_datetime = re.compile("^\d+-\d+-\d+ \d+:\d+:\d+$")
def get_date(s):
    import rfc822
    if re_date.match(s):
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            date = rfc822.parsedate(s)
    elif re_datetime.match(s):
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            date = rfc822.parsedate(s)
    else:
        date = rfc822.parsedate(s)

    if date is None:
        return None
    return datetime.datetime(*date)


class Command(BaseCommand):
    help = 'Daily maintenance of the nm.debian.org database'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", default=None, help="Disable progress reporting"),
        optparse.make_option("--since", action="store", default=None, help="Start of report period (default: a week before the end)"),
        optparse.make_option("--until", action="store", default=None, help="End of report period (default: midnight this morning)"),
        optparse.make_option("--email", action="store", default=None, help="Email address to send the report to (default: print to stdout)"),
    )

    def handle(self, *fnames, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        if opts["since"] is not None:
            opts["since"] = get_date(opts["since"])
        if opts["until"] is not None:
            opts["until"] = get_date(opts["until"])

        reporter = Reporter(**opts)
        if opts["email"]:
            mout = StringIO()
            reporter.run(mout, **opts)
            send_mail(
                reporter.subject(),
                mout.getvalue(),
                "NM Front Desk <nm@debian.org>",
                [opts["email"]])
        else:
            reporter.run(sys.stdout, **opts)
