# coding: utf-8
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

from django.core.management.base import BaseCommand, CommandError
import django.db
from django.db import connection, transaction
from django.conf import settings
import optparse
import sys
import os
import re
import logging
import datetime
import cookielib
import urllib
import urllib2
import rfc822
import tempfile
import subprocess
from cStringIO import StringIO
from backend import models as bmodels
from backend import const

log = logging.getLogger(__name__)

class RT(object):
    URI = 'https://rt.debian.org/REST/1.0/'
    def __init__(self):
        # Log into RT
        self.cj = cookielib.LWPCookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
        urllib2.install_opener(opener)
        data = settings.RT_LOGIN_INFO
        ldata = urllib.urlencode(data)
        login = urllib2.Request(self.URI, ldata)
        res = urllib2.urlopen(login)
        log.info("Login: %s", res.read().replace("\n", ";"))

    def parse_result(self, r):
        """
        Return a list of rfc822 message headers
        """
        status = r.readline()
        log.info("Result status: %s", status)
        buf = StringIO()
        # Skip leading empty lines and comments
        for l in r:
            if l.isspace(): continue
            if not l: continue
            if l[0] == '#': continue
            buf.write(l)
            break
        buf.write(r.read())
        buf.seek(0)
        res = []
        while buf.tell() < len(buf.getvalue()):
            res.append(rfc822.Message(buf))
        return res

    def ticket_summary(self, rt_id):
        return self.parse_result(urllib2.urlopen('%sticket/%d/show' % (self.URI, rt_id)))

    def ticket_history(self, rt_id):
        return self.parse_result(urllib2.urlopen('%sticket/%d/history' % (self.URI, rt_id)))

    def ticket_history_content(self, rt_id, h_id):
        return self.parse_result(urllib2.urlopen('%sticket/%d/history/id/%d' % (self.URI, rt_id, h_id)))

    def demangle_content(self, buf):
        """
        Demangle an RT content header, returning the plain text.

        Returns a StringIO file descriptor
        """
        fd = StringIO(buf)
        outfd = StringIO()
        outfd.write(fd.readline().lstrip())
        for l in fd:
            outfd.write(l[9:])
        outfd.seek(0)
        return outfd

class Command(BaseCommand):
    help = 'Create a DM from a RT ticket'
    args = "rt-id"

    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
    )

    def handle(self, rt_id, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        if not rt_id.isdigit():
            log.error("RT id %s needs to be numeric", rt_id)
            sys.exit(1)
        rt_id = int(rt_id)

        # Log into RT
        rt = RT()

        summary = rt.ticket_summary(rt_id)[0]
        ticket_closed = datetime.datetime(*summary.getdate("Resolved")[:6])

        # Find the ID of the first history item
        r = rt.ticket_history(rt_id)[0]
        first_history = r.headers[0]
        h_id = int(first_history.split(":")[0])
        log.info("First history: %d", h_id)

        re_keyid = re.compile(r"^\s*please add key ID\s*(?P<fpr>[0-9A-F]+)")
        re_namemail = re.compile(r"^Comment: Add (?P<name>.+?)\s+<(?P<email>[^>]+)> as a Debian Maintainer")

        # Get the contents of the first history item
        c = rt.ticket_history_content(rt_id, h_id)
        info = dict()
        for m in c:
            if 'Content' in m:
                # Demangle content
                fd = rt.demangle_content(m.getrawheader("Content"))
                for line in fd:
                    mo = re_keyid.match(line)
                    if mo:
                        info["fpr"] = mo.group("fpr")
                        continue
                    mo = re_namemail.match(line)
                    if mo:
                        # Arbitrary name splitting
                        names = mo.group("name").split()
                        if len(names) == 2:
                            info["cn"] = names[0]
                            info["mn"] = ""
                            info["sn"] = names[1]
                        elif len(names) == 3:
                            info["cn"] = names[0]
                            info["mn"] = names[1]
                            info["sn"] = names[2]
                        else:
                            middle = len(names) / 2
                            info["cn"] = " ".join(names[:middle])
                            info["mn"] = ""
                            info["sn"] = " ".join(names[middle:])
                        info["email"] = mo.group("email")
                    #Changed-By: Anibal Monsalve Salazar <anibal@debian.org>
                    #Date: Tue, 03 Jul 2012 03:07:04 +0000
                    #BTS: http://bugs.debian.org/679157
                    #Agreement: http://lists.debian.org/debian-newmaint/2012/06/msg00057.html
                    #Advocates: 
                    #    piotr - http://lists.debian.org/debian-newmaint/2012/06/msg00058.html

        # Print out info for review
        outfd = tempfile.NamedTemporaryFile()
        try:
            print >>outfd, "# https://rt.debian.org/%d" % rt_id
            print >>outfd, "# Delete everything to abort"
            print >>outfd
            for fld in ("cn", "mn", "sn", "email", "fpr"):
                print >>outfd, "%s: %s" % (fld, info.get(fld, ""))
            outfd.flush()

            # Call up an editor for review
            editor = os.environ.get("EDITOR", "vim")
            p = subprocess.Popen([editor, outfd.name], close_fds=True)
            p.wait()

            # Read back
            info = dict()
            with open(outfd.name) as fd:
                for line in fd:
                    line = line.strip()
                    if not line: continue
                    if line[0] == "#": continue
                    k, v = line.split(":", 1)
                    info[k.strip()] = v.strip()

            if not info:
                log.error("file is empty: aborted")
        finally:
            outfd.close()

        p = bmodels.Person(
            cn=info["cn"],
            fpr=info["fpr"],
            email=info["email"],
            status=const.STATUS_DM,
            status_changed=ticket_closed,
        )
        if info.get("mn", ""): p.mn = info["mn"]
        if info.get("sn", ""): p.mn = info["sn"]
        p.save()

        log.info("Record created.")

        # TODO: add process record with begin, ticket open time, advocates

