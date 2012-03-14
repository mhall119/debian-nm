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
from django.core.urlresolvers import reverse
import backend.models as bmodels
from backend import const
import datetime

def managers(request):
    from django.db import connection

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

    # Read the list of AMs, with default sorting, and annotate with the
    # statistics
    ams = []
    for a in bmodels.AM.objects.all().order_by("-is_am", "person__uid"):
        total, active, held = stats.get(a.id, (0, 0, 0))
        a.stats_total = total
        a.stats_active = active
        a.stats_done = total-active
        a.stats_held = held
        ams.append(a)

    return render_to_response("public/managers.html",
                              dict(
                                  ams=ams,
                              ),
                              context_instance=template.RequestContext(request))

def processes(request):
    from django.db.models import Min, Max, Q

    context=dict()

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=180)

    context["open"] = bmodels.Process.objects.filter(is_active=True) \
                                             .annotate(
                                                 started=Min("log__logdate"),
                                                 last_change=Max("log__logdate")) \
                                             .order_by("-last_change")

    context["done"] = bmodels.Process.objects.filter(progress=const.PROGRESS_DONE) \
                                             .annotate(
                                                 started=Min("log__logdate"),
                                                 last_change=Max("log__logdate")) \
                                             .order_by("-last_change") \
                                             .filter(last_change__gt=cutoff)

    return render_to_response("public/processes.html",
                              context,
                              context_instance=template.RequestContext(request))

def process(request, key):
    process = bmodels.Process.lookup(key)
    if process is None:
        return redirect(reverse('root_faq') + "#process-lookup")

    log = list(process.log.order_by("logdate", "progress"))
    started = log[0].logdate
    last_change = log[-1].logdate

    distilled_log = []
    last_progress = None
    for l in log:
        if last_progress != l.progress:
            distilled_log.append((l.progress, l.changed_by, l.logdate))
            last_progress = l.progress

    # Map unusual steps to their previous usual ones
    unusual_step_map = {
        const.PROGRESS_APP_HOLD: const.PROGRESS_APP_RCVD,
        const.PROGRESS_AM_HOLD: const.PROGRESS_AM,
        const.PROGRESS_FD_HOLD: const.PROGRESS_AM_OK,
        const.PROGRESS_DAM_HOLD: const.PROGRESS_FD_OK,
        const.PROGRESS_CANCELLED: const.PROGRESS_DONE,
    }

    # Get the 'simplified' current step
    curstep = unusual_step_map.get(process.progress, process.progress)

    # List of usual steps in order
    steps = (
        const.PROGRESS_APP_NEW,
        const.PROGRESS_APP_RCVD,
        const.PROGRESS_ADV_RCVD,
        const.PROGRESS_APP_OK,
        const.PROGRESS_AM_RCVD,
        const.PROGRESS_AM,
        const.PROGRESS_AM_OK,
        const.PROGRESS_FD_OK,
        const.PROGRESS_DAM_OK,
        const.PROGRESS_DONE,
    )

    # Index of current step
    curstep_idx = steps.index(curstep)

    return render_to_response("public/nmstatus.html",
                              dict(
                                  process=process,
                                  started=started,
                                  last_change=last_change,
                                  distilled_log=distilled_log,
                                  steps=steps,
                                  curstep_idx=curstep_idx,
                              ),
                              context_instance=template.RequestContext(request))

def people(request):
    by_tag = dict()
    for p in bmodels.Person.objects.all().order_by("uid", "sn", "cn"):
        by_tag.setdefault(p.status, []).append(p)

    by_status = dict()
    for key, tag, desc in const.ALL_STATUS:
        by_status[key[7:]] = by_tag.get(tag, [])

    return render_to_response("public/people.html",
                              dict(
                                  people=by_status,
                              ),
                              context_instance=template.RequestContext(request))

def person(request, key):
    from django.db.models import Min, Max
    person = bmodels.Person.lookup(key)
    if person is None:
        return http.HttpResponseNotFound("Person with uid or email %s not found" % key)

    processes = person.processes \
            .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
            .order_by("is_active", "ended")

    active_process = None
    for p in processes:
        if p.is_active:
            active_process = p
            break

    can_be_am = False
    if person.is_am:
        am = person.am
        am_processes = am.processed \
                .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                .order_by("is_active", "ended")
    else:
        am = None
        am_processes = []
        if person.status in (const.STATUS_DD_U, const.STATUS_DD_NU) and person.status_changed and (datetime.datetime.utcnow() - person.status_changed > datetime.timedelta(days=6*30)):
            can_be_am = True

    adv_processes = person.advocated \
                .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                .order_by("is_active", "ended")

    return render_to_response("public/person.html",
                              dict(
                                  person=person,
                                  am=am,
                                  active_process=active_process,
                                  processes=processes,
                                  am_processes=am_processes,
                                  adv_processes=adv_processes,
                                  can_be_am=can_be_am,
                              ),
                              context_instance=template.RequestContext(request))

def progress(request, progress):
    from django.db.models import Min, Max

    processes = bmodels.Process.objects.filter(progress=progress, is_active=True) \
            .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
            .order_by("started")

    return render_to_response("public/progress.html",
                              dict(
                                  progress=progress,
                                  processes=processes,
                              ),
                              context_instance=template.RequestContext(request))
