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

from collections import namedtuple

Status = namedtuple("Status", ("code", "tag", "sdesc", "ldesc"))
Progress = namedtuple("Progress", ("code", "tag", "ldesc"))

g = globals()

# Status of a person in Debian
ALL_STATUS = (
    Status("STATUS_MM",          "mm",         "None",              "None"),
    Status("STATUS_MM_GA",       "mm_ga",      "None, account",     "None, with guest account"),
    Status("STATUS_DM",          "dm",         "DM",                "Debian Maintainer"),
    Status("STATUS_DM_GA",       "dm_ga",      "DM, account",       "Debian Maintainer, with guest account"),
    Status("STATUS_DD_U",        "dd_u",       "DD, uploading",     "Debian Developer, uploading"),
    Status("STATUS_DD_NU",       "dd_nu",      "DD, non-uploading", "Debian Developer, non-uploading"),
    Status("STATUS_EMERITUS_DD", "dd_e",       "DD, emeritus",      "Debian Developer, emeritus"),
    Status("STATUS_EMERITUS_DM", "dm_e",       "DM, emeritus",      "Debian Maintainer, emeritus"),
    Status("STATUS_REMOVED_DD",  "dd_r",       "DD, removed",       "Debian Developer, removed"),
    Status("STATUS_REMOVED_DM",  "dm_r",       "DM, removed",       "Debian Maintainer, removed"),
)
ALL_STATUS_DESCS = dict((x.tag, x.ldesc) for x in ALL_STATUS)
for s in ALL_STATUS:
    g[s.code] = s.tag

SEQ_STATUS = dict(((y.tag, x) for x, y in enumerate(ALL_STATUS)))

# Progress of a person in a process
ALL_PROGRESS = (
    Progress("PROGRESS_APP_NEW",   "app_new",   "Applicant asked to enter the process"),
    Progress("PROGRESS_APP_RCVD",  "app_rcvd",  "Applicant replied to initial mail"),
    Progress("PROGRESS_APP_HOLD",  "app_hold",  "On hold before entering the queue"),
    Progress("PROGRESS_ADV_RCVD",  "adv_rcvd",  "Received enough advocacies"),
    Progress("PROGRESS_APP_OK",    "app_ok",    "Advocacies have been approved"),
    Progress("PROGRESS_AM_RCVD",   "am_rcvd",   "Waiting for AM to confirm"),
    Progress("PROGRESS_AM",        "am",        "Interacting with an AM"),
    Progress("PROGRESS_AM_HOLD",   "am_hold",   "AM hold"),
    Progress("PROGRESS_AM_OK",     "am_ok",     "AM approved"),
    Progress("PROGRESS_FD_HOLD",   "fd_hold",   "FD hold"),
    Progress("PROGRESS_FD_OK",     "fd_ok",     "FD approved"),
    Progress("PROGRESS_DAM_HOLD",  "dam_hold",  "DAM hold"),
    Progress("PROGRESS_DAM_OK",    "dam_ok",    "DAM approved"),
    Progress("PROGRESS_DONE",      "done",      "Completed"),
    Progress("PROGRESS_CANCELLED", "cancelled", "Canceled"),
)
ALL_PROGRESS_DESCS = dict((x.tag, x.ldesc) for x in ALL_PROGRESS)
for p in ALL_PROGRESS:
    g[p.code] = p.tag

SEQ_PROGRESS = dict(((y.tag, x) for x, y in enumerate(ALL_PROGRESS)))
