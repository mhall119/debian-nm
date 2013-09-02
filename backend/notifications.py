# coding: utf-8

# nm.debian.org website backend.notifications
#
# Copyright (C) 2013  Marco Bardelli <bardelli.marco@gmail.com>
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
from django.conf import settings
from django.template.loader import render_to_string
from . import const
from .email import send_notification

def maybe_notify_applicant_on_progress(log, previous_log):
    """
    Notify applicant via e-mail about progress of this process, if it is interesting.
    """
    if previous_log is None:
        ## this is strange no previous log, do nothing
        return

    from_progress = previous_log.progress
    to_progress = log.progress

    ################################################################
    # * When an AM approves the applicant, mail debian-newmaint

    # This happens only when Process.progress goes from one of (am_rcvd,
    #                                                            am, am_hold) to am_ok.

    # Use case: the AM can decide to approve an applicant whatever previous
    # progress they were in.

    # The email shouldn't however be triggered if, for example, FD just
    # unholds an application but hasn't finished with their review: that
    # would be a (fd_hold -> am_ok) change.
    ################################################################

    if from_progress in (const.PROGRESS_AM_RCVD,
                         const.PROGRESS_AM,
                         const.PROGRESS_AM_HOLD):

        if to_progress == const.PROGRESS_AM_OK:
            # mail debian-newmaint AM approved Applicant
            # with https://lists.debian.org/debian-newmaint/2009/04/msg00026.html
            send_notification("notification_mails/public_am_approved_applicant.txt",
                              log, previous_log)
            return

    ################################################################
    # * When they get in the queue to get an AM assigned

    #   This happens when Process.progress goes from [anything except app_ok]
    #   to app_ok.

    #   Use cases:
    #    - FD may skip any step from initial contact to having things ready
    #      for AM assignment
    #    - an AM may get busy and hand an applicant back to FD. That would be
    #      a transition from any of (am_rcvd, am, am_hold) to app_ok
    ################################################################

    if from_progress in (const.PROGRESS_APP_NEW,
                         const.PROGRESS_APP_RCVD,
                         const.PROGRESS_APP_HOLD,
                         const.PROGRESS_ADV_RCVD,
                         const.PROGRESS_POLL_SENT,
                         const.PROGRESS_AM_RCVD,
                         const.PROGRESS_AM,
                         const.PROGRESS_AM_HOLD):

        if to_progress == const.PROGRESS_APP_OK:
            # mail applicant in the queue to get an AM assigned
            send_notification(
                "notification_mails/am_assigned_to_applicant.txt",
                log, previous_log)
            return

    ################################################################
    # * When they get approved by FD

    #   This happens only when Process.progress goes from one of (am_ok,
    #   fd_hold) to fd_ok.
    ################################################################
    if from_progress in (const.PROGRESS_AM_OK,
                         const.PROGRESS_FD_HOLD):

        if to_progress == const.PROGRESS_FD_OK:
            # mail applicant in the queue to get an AM assigned
            send_notification("notification_mails/fd_approved_applicant.txt",
                              log, previous_log)
            return
