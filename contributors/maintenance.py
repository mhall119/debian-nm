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
from backend.maintenance import MakeLink
from django_maintenance import MaintenanceTask
import backend.models as bmodels
import debiancontributors as dc
import logging

log = logging.getLogger(__name__)

DC_AUTH_TOKEN = getattr(settings, "DC_AUTH_TOKEN", None)
DC_SUBMIT_URL = getattr(settings, "DC_SUBMIT_URL", None)

class SubmitContributors(MaintenanceTask):
    """
    Compute contributions and submit them to contributors.debian.org
    """
    DEPENDS = [MakeLink]
    def run(self):
        from django.db.models import Min, Max

        if DC_AUTH_TOKEN is None:
            raise Exception("DC_AUTH_TOKEN is not configured, we cannot submit to contributors.debian.org")

        submission = dc.Submission("nm.debian.org")

        for am in bmodels.AM.objects.all():
            res = bmodels.Log.objects.filter(changed_by=am.person, process__manager=am).aggregate(
                since=Min("logdate"),
                until=Max("logdate"))
            if res["since"] is None or res["until"] is None:
                continue
            submission.add_contribution_data(
                dc.Identifier(type="uid", id=am.person.uid, desc=am.person.fullname),
                type="am", begin=res["since"].date(), end=res["until"].date(),
                url=self.maint.link(am))

        for am in bmodels.AM.objects.filter(is_fd=True):
            res = bmodels.Log.objects.filter(changed_by=am.person).exclude(process__manager=am).aggregate(
                since=Min("logdate"),
                until=Max("logdate"))
            if res["since"] is None or res["until"] is None:
                continue
            submission.add_contribution_data(
                dc.Identifier(type="uid", id=am.person.uid, desc=am.person.fullname),
                type="fd", begin=res["since"].date(), end=res["until"].date(),
                url=self.maint.link(am))

        if DC_SUBMIT_URL:
            submission.post(DC_AUTH_TOKEN, baseurl=DC_SUBMIT_URL)
        else:
            submission.post(DC_AUTH_TOKEN)
