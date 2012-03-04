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

g = globals()

# Status of a person in Debian
ALL_STATUS = (
    ("STATUS_MM",          "mm",         "None"),
    ("STATUS_MM_GA",       "mm_ga",      "None, with guest account"),
    ("STATUS_DM",          "dm",         "Debian Maintainer"),
    ("STATUS_DM_GA",       "dm_ga",      "Debian Maintainer, with guest account"),
    ("STATUS_DD_U",        "dd_u",       "Debian Developer, uploading"),
    ("STATUS_DD_NU",       "dd_nu",      "Debian Developer, non-uploading"),
    ("STATUS_EMERITUS_DD", "dd_e",       "Debian Developer, emeritus"),
    ("STATUS_EMERITUS_DM", "dm_e",       "Debian Maintainer, emeritus"),
    ("STATUS_REMOVED_DD",  "dd_r",       "Debian Developer, removed"),
    ("STATUS_REMOVED_DM",  "dm_r",       "Debian Maintainer, removed"),
)
ALL_STATUS_DESCS = dict(x[1:3] for x in ALL_STATUS)
for key, val, desc in ALL_STATUS:
    g[key] = val

## Application targets
#APPLY_FOR_DM = STATUS_DM
#APPLY_FOR_DD_U = STATUS_DD_U
#APPLY_FOR_DD_NU = STATUS_DD_NU

# Progress of a person in a process
ALL_PROGRESS = (
    ("PROGRESS_APP_NEW",   "app_new",   "Applicant asked to enter the process"),
    ("PROGRESS_APP_RCVD",  "app_rcvd",  "Applicant replied to initial mail"),
    ("PROGRESS_APP_HOLD",  "app_hold",  "On hold before entering the queue"),
    ("PROGRESS_ADV_RCVD",  "adv_rcvd",  "Received enough advocacies"),
    ("PROGRESS_APP_OK",    "app_ok",    "Advocacies have been approved"),
    ("PROGRESS_AM_RCVD",   "am_rcvd",   "Waiting for AM to confirm"),
    ("PROGRESS_AM",        "am",        "Got an AM"),
    ("PROGRESS_AM_HOLD",   "am_hold",   "AM put application on hold"),
    ("PROGRESS_AM_OK",     "am_ok",     "AM recommends the applicant"),
    ("PROGRESS_FD_HOLD",   "fd_hold",   "FD puts application on hold"),
    ("PROGRESS_FD_OK",     "fd_ok",     "FD recommends the applicant"),
    ("PROGRESS_DAM_HOLD",  "dam_hold",  "DAM puts application on hold"),
    ("PROGRESS_DAM_OK",    "dam_ok",    "DAM accepts the applicant"),
    ("PROGRESS_DONE",      "done",      "Process has completed successfully (account was created)"),
    ("PROGRESS_CANCELLED", "cancelled", "Process has been canceled"),
)
ALL_PROGRESS_DESCS = dict(x[1:3] for x in ALL_PROGRESS)
for key, val, desc in ALL_PROGRESS:
    g[key] = val

#ALLOWED_PROGRESS_AM = [ PROGRESS_AM_RCVD, PROGRESS_AM_ACKED, PROGRESS_AM_HOLD, PROGRESS_AM_OK ]
#ALLOWED_PROGRESS_FD = [ PROGRESS_APP_NEW, PROGRESS_APP_RCVD, PROGRESS_APP_HOLD, PROGRESS_ADV_RCVD, PROGRESS_APP_OK] \
#                        + ALLOWED_PROGRESS_AM + \
#                      [ PROGRESS_FD_HOLD, PROGRESS_FD_OK, PROGRESS_CANCELLED ]
#ALLOWED_PROGRESS_DAM = ALLOWED_PROGRESS_FD + [PROGRESS_DAM_HOLD, PROGRESS_DAM_OK, PROGRESS_DONE ]


