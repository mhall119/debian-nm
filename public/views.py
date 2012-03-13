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

def whoisam(request):
    # Below is the list of Debian developers who are currently active as Application Managers:
    ams_active = bmodels.AM.objects.filter(is_am=True).order_by("person__uid")

    # The New Member Committee is formed of all active application managers who
    # have approved an applicant in the last six months. Front-Desk is also
    # member.
    ams_ctte = bmodels.AM.objects.filter(is_am_ctte=True).order_by("person__uid")

    # Below is the list of Debian developers who used to help as Application Managers in the past:
    ams_inactive = bmodels.AM.objects.filter(is_am=False).order_by("person__uid")

    return render_to_response("public/whoisam.html",
                              dict(
                                  ams_active=ams_active,
                                  ams_ctte=ams_ctte,
                                  ams_inactive=ams_inactive,
                              ),
                              context_instance=template.RequestContext(request))

def nmlist(request):
    from django.db.models import Max

    context=dict()

    # Where do we show processes, based on their progress
    dispatch_map = {
        const.PROGRESS_APP_NEW: "nm_no_adv",
        const.PROGRESS_APP_RCVD: "nm_no_adv",
        const.PROGRESS_APP_HOLD: "nm_no_adv",
        const.PROGRESS_ADV_RCVD: "nm_no_adv",
        const.PROGRESS_APP_OK: "nm_unassigned",
        const.PROGRESS_AM_RCVD: "nm_unassigned",
        const.PROGRESS_APP_HOLD: "nm_app_hold",
        const.PROGRESS_AM: "nm_assigned",
        const.PROGRESS_AM_OK: "nm_fd",
        const.PROGRESS_FD_HOLD: "nm_fd_hold",
        const.PROGRESS_FD_OK: "nm_dam",
        const.PROGRESS_DAM_OK: "nm_dam_ok",
        const.PROGRESS_DAM_HOLD: "nm_dam_hold",
        const.PROGRESS_AM_HOLD: "nm_hold",
    }

    # Create the arrays
    for v in dispatch_map.itervalues():
        context.setdefault(v, [])

    # Populate the arrays
    for p in bmodels.Process.objects.filter(is_active=True) \
             .annotate(last_change=Max("log__logdate")).order_by("-last_change"):
        dest = dispatch_map.get(p.progress, None)
        if dest is None: continue
        context[dest].append(p)

    # Create the list of new maintainers using a different strategy
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=180)
    context["nm_done"] = bmodels.Process.objects.filter(progress=const.PROGRESS_DONE) \
            .annotate(last_change=Max("log__logdate")).order_by("-last_change").filter(last_change__gt=cutoff)

    return render_to_response("public/nmlist.html",
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

    if person.is_am:
        am = person.am
        am_processes = am.processed \
                .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                .order_by("is_active", "ended")
    else:
        am = None
        am_processes = []

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
                              ),
                              context_instance=template.RequestContext(request))

def progress(request, progress):
    from django.db.models import Min, Max

    processes = bmodels.Process.objects.filter(progress=progress, is_active=True) \
            .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
            .order_by("started")

    cur_am = None
    cur_person = None
    if not request.user.is_anonymous():
        cur_person = request.user.get_profile()
        if cur_person.is_am:
            cur_am = cur_person.am

    return render_to_response("public/progress.html",
                              dict(
                                  progress=progress,
                                  cur_person=cur_person,
                                  cur_am=cur_am,
                                  processes=processes,
                              ),
                              context_instance=template.RequestContext(request))
