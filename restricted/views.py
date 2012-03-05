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
from django.utils.translation import ugettext as _
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
    from django.db.models import Min
    person = request.user.get_profile()

    am_available = bmodels.AM.list_free()

    prog_app_ok = bmodels.Process.objects.filter(progress=const.PROGRESS_APP_OK) \
                  .annotate(started=Min("log__logdate")).order_by("started")

    prog_app_hold = bmodels.Process.objects.filter(manager=None, progress__in=(
        const.PROGRESS_APP_HOLD,
        const.PROGRESS_FD_HOLD,
        const.PROGRESS_DAM_HOLD)) \
                    .annotate(started=Min("log__logdate")).order_by("started")

    prog_am_rcvd = bmodels.Process.objects.filter(progress=const.PROGRESS_AM_RCVD) \
                   .annotate(started=Min("log__logdate")).order_by("started")

    prog_am_ok = bmodels.Process.objects.filter(progress=const.PROGRESS_AM_OK) \
                 .annotate(started=Min("log__logdate")).order_by("started")

    prog_fd_hold = bmodels.Process.objects.filter(progress=const.PROGRESS_FD_HOLD) \
                   .exclude(manager=None) \
                   .annotate(started=Min("log__logdate")).order_by("started")

    prog_fd_ok = bmodels.Process.objects.filter(progress=const.PROGRESS_FD_OK) \
                 .annotate(started=Min("log__logdate")).order_by("started")

    prog_dam_ok = bmodels.Process.objects.filter(progress=const.PROGRESS_DAM_OK) \
                 .annotate(started=Min("log__logdate")).order_by("started")

    prog_dam_hold = bmodels.Process.objects.filter(progress=const.PROGRESS_DAM_HOLD) \
                   .exclude(manager=None) \
                   .annotate(started=Min("log__logdate")).order_by("started")

    am_prog_rcvd = bmodels.Process.objects.filter(progress=const.PROGRESS_AM_RCVD) \
                   .filter(manager=person.am) \
                   .annotate(started=Min("log__logdate")).order_by("started")

    am_prog_am = bmodels.Process.objects.filter(progress=const.PROGRESS_AM) \
                   .filter(manager=person.am) \
                   .annotate(started=Min("log__logdate")).order_by("started")

    am_prog_hold = bmodels.Process.objects.filter(progress=const.PROGRESS_AM_HOLD) \
                   .filter(manager=person.am) \
                   .annotate(started=Min("log__logdate")).order_by("started")

    am_prog_done = bmodels.Process.objects.filter(manager=person.am, progress__in=(
        const.PROGRESS_AM_OK,
        const.PROGRESS_FD_HOLD,
        const.PROGRESS_FD_OK,
        const.PROGRESS_DAM_HOLD,
        const.PROGRESS_DAM_OK,
        const.PROGRESS_DONE,
        const.PROGRESS_CANCELLED)) \
                    .annotate(started=Min("log__logdate")).order_by("started")

    return render_to_response("restricted/ammain.html",
                              dict(
                                  person=person,
                                  am=person.am,
                                  am_available=am_available,
                                  prog_app_ok=prog_app_ok,
                                  prog_app_hold=prog_app_hold,
                                  prog_am_rcvd=prog_am_rcvd,
                                  prog_am_ok=prog_am_ok,
                                  prog_fd_hold=prog_fd_hold,
                                  prog_fd_ok=prog_fd_ok,
                                  prog_dam_ok=prog_dam_ok,
                                  prog_dam_hold=prog_dam_hold,
                                  am_prog_rcvd=am_prog_rcvd,
                                  am_prog_am=am_prog_am,
                                  am_prog_hold=am_prog_hold,
                                  am_prog_done=am_prog_done,
                              ),
                              context_instance=template.RequestContext(request))

def make_am_form(editor):
    excludes = ["person", "is_am_ctte"]

    if editor.is_dam:
        pass
    elif editor.is_fd:
        excludes.append("is_dam")
    else:
        excludes.append("is_fd")
        excludes.append("is_dam")

    class AMForm(forms.ModelForm):
        class Meta:
            model = bmodels.AM
            exclude = excludes
    return AMForm


@backend.auth.is_am
def amprofile(request, uid=None):
    from django.db.models import Min

    if uid is None:
        person = request.user.get_profile()
    else:
        person = bmodels.Person.objects.get(uid=uid)
    am = person.am

    AMForm = make_am_form(am)

    form = None
    if request.method == 'POST':
        form = AMForm(request.POST, instance=am)
        if form.is_valid():
            cur_am = request.user.get_profile().am
            if cur_am == am or cur_am.is_fd or cur_am.is_dam:
                form.save()
            else:
                return http.HttpResponse("Editing is restricted to the am and front desk members")
            # TODO: message that it has been saved
    else:
        form = AMForm(instance=am)

    processes = bmodels.Process.objects.filter(manager=am).annotate(started=Min("log__logdate")).order_by("-started")

    am_available = bmodels.AM.list_free()

    return render_to_response("restricted/amprofile.html",
                              dict(
                                  person=person,
                                  am=am,
                                  processes=processes,
                                  form=form,
                              ),
                              context_instance=template.RequestContext(request))


def make_statusupdateform(editor):
    if editor.is_fd:
        choices = [(x[1], "%s - %s" % (x[1], x[2])) for x in const.ALL_PROGRESS]
    else:
        choices = [x[1:3] for x in const.ALL_PROGRESS if x[0] in ("PROGRESS_AM", "PROGRESS_AM_HOLD", "PROGRESS_AM_OK")]

    class StatusUpdateForm(forms.Form):
        progress = forms.ChoiceField(
            required=True,
            label=_("Progress"),
            choices=choices
        )
        logtext = forms.CharField(
            required=True,
            label=_("Log text"),
            widget=forms.Textarea(attrs=dict(rows=5, cols=80))
        )
    return StatusUpdateForm


@backend.auth.is_am
def amstatus(request, procid):
    process = bmodels.Process.objects.get(id=procid)

    person = process.person

    cur_person = request.user.get_profile()
    am = cur_person.am

    can_edit = am.is_fd or am.is_dam or am == process.manager

    if can_edit:
        StatusUpdateForm = make_statusupdateform(am)
        if request.method == 'POST':
            form = StatusUpdateForm(request.POST)
            if form.is_valid():
                process.progress = form.cleaned_data["progress"]
                process.save()
                log = bmodels.Log(
                    changed_by=cur_person,
                    process=process,
                    progress=process.progress,
                    logtext=form.cleaned_data["logtext"]
                )
                log.save()
                form = StatusUpdateForm(initial=dict(progress=process.progress))
        else:
            form = StatusUpdateForm(initial=dict(progress=process.progress))
    else:
        form = None

    log = process.log.order_by("-logdate")

    return render_to_response("restricted/amstatus.html",
                              dict(
                                  process=process,
                                  person=person,
                                  cur_person=cur_person,
                                  am=am,
                                  log=log,
                                  form=form,
                                  can_edit=can_edit,
                              ),
                              context_instance=template.RequestContext(request))

def make_person_form(editor):
    excludes = ["user"]

    if editor.is_dam:
        pass
    elif editor.is_fd:
        excludes.append("status")
    else:
        excludes.append("status")
        excludes.append("fd_comment")

    class PersonForm(forms.ModelForm):
        class Meta:
            model = bmodels.Person
            exclude = excludes
    return PersonForm

@backend.auth.is_am
def person(request, key):
    person = bmodels.Person.lookup(key)

    cur_person = request.user.get_profile()
    am = cur_person.am

    if not person.can_be_edited(am):
        # TODO
        return redirect('TODO', uid=person.uid)

    PersonForm = make_person_form(am)

    form = None
    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            form.save()
            # TODO: message that it has been saved
    else:
        form = PersonForm(instance=person)

    return render_to_response("restricted/person.html",
                              dict(
                                  person=person,
                                  am=am,
                                  cur_person=cur_person,
                                  active_process=person.active_process,
                                  form=form,
                              ),
                              context_instance=template.RequestContext(request))

@backend.auth.is_am
def nmelist(request):
    from django.db.models import Min

    procs = bmodels.Process.objects.filter(is_active=True) \
             .annotate(started=Min("log__logdate")).order_by("started")

    return render_to_response("restricted/nmelist.html",
                              dict(
                                  procs=procs,
                              ),
                              context_instance=template.RequestContext(request))

