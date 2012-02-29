# nm.debian.org website reports
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

from django import http, template, forms
from django.shortcuts import render_to_response, redirect
import backend.models as bmodels

def whoisam(request):
    # Below is the list of Debian developers who are currently active as Application Managers:
    ams_active = bmodels.AM.objects.filter(is_am=True)

    # The New Member Committee is formed of all active application managers who have approved an applicant in the last six months. Front-Desk is also member.
    # TODO: check old query

    # Below is the list of Debian developers who used to help as Application Managers in the past:
    ams_inactive = bmodels.AM.objects.filter(is_am=False)

    return render_to_response("reports/whoisam.html",
                              dict(
                                  ams_active=ams_active,
                                  ams_inactive=ams_inactive,
                              ),
                              context_instance=template.RequestContext(request))




