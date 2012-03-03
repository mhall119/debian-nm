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
from django.contrib.auth.decorators import login_required
import backend.models as bmodels
from backend import const
import backend.auth

@backend.auth.is_am
def amlist(request):
    from django.db import connection
    # Here is a list of active Application Managers:
    #     Login   Name    cur max hold    done    Role

    # Compute statistics indexed by AM id
    cursor = connection.cursor()
    cursor.execute("""
    SELECT am.id,
           count(*) as total,
           count(process.is_active) as active,
           count(process.progress=%s) as held
      FROM am
      JOIN process ON process.manager_id=am.id
     GROUP BY am.id
    """, (const.PROGRESS_AM_HOLD,))
    stats = dict()
    for amid, total, active, held in cursor:
        stats[amid] = (total, active, held)

    ams_active = []
    ams_inactive = []
    for a in bmodels.AM.objects.all().order_by("person__uid"):
        total, active, held = stats.get(a.id, (0, 0, 0))
        a.stats_total = total
        a.stats_active = active
        a.stats_done = total-active
        a.stats_held = held
        if a.is_am:
            ams_active.append(a)
        else:
            ams_inactive.append(a)

    return render_to_response("restricted/amlist.html",
                              dict(
                                  ams_active=ams_active,
                                  ams_inactive=ams_inactive,
                              ),
                              context_instance=template.RequestContext(request))

@backend.auth.is_am
def ammain(request):
    person = request.user.get_profile()

    return render_to_response("restricted/ammain.html",
                              dict(
                                  person=person,
                                  am=person.am,
                              ),
                              context_instance=template.RequestContext(request))
