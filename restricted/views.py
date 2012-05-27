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
import minechangelogs.models as mmodels
from backend import const
import backend.auth
import json
import datetime

@backend.auth.is_am
def ammain(request):
    from django.db.models import Min, Max
    ctx = dict()

    ctx["am_available"] = bmodels.AM.list_free()

    if request.am.is_fd or request.am.is_dam:
        DISPATCH = {
            const.PROGRESS_APP_NEW: "prog_app_new",
            const.PROGRESS_APP_RCVD: "prog_app_new",
            const.PROGRESS_ADV_RCVD: "prog_app_new",
            const.PROGRESS_APP_OK: "prog_app_ok",
            const.PROGRESS_AM_RCVD: "prog_am_rcvd",
            const.PROGRESS_AM_OK: "prog_am_ok",
            const.PROGRESS_FD_OK: "prog_fd_ok",
            const.PROGRESS_DAM_OK: "prog_dam_ok",
        }
        for p in bmodels.Process.objects.filter(is_active=True, progress__in=DISPATCH.keys()) \
                        .annotate(
                            started=Min("log__logdate"),
                            last_change=Max("log__logdate")) \
                        .order_by("started"):
            tgt = DISPATCH.get(p.progress, None)
            if tgt is not None:
                p.annotate_with_duration_stats()
                ctx.setdefault(tgt, []).append(p)

        DISPATCH = {
            const.PROGRESS_APP_HOLD: "prog_app_hold",
            const.PROGRESS_FD_HOLD: "prog_app_hold",
            const.PROGRESS_DAM_HOLD: "prog_app_hold",
        }
        for p in bmodels.Process.objects.filter(is_active=True, manager=None, progress__in=DISPATCH.keys()) \
                        .annotate(
                            started=Min("log__logdate"),
                            last_change=Max("log__logdate")) \
                        .order_by("started"):
            tgt = DISPATCH.get(p.progress, None)
            if tgt is not None:
                p.annotate_with_duration_stats()
                ctx.setdefault(tgt, []).append(p)

        DISPATCH = {
            const.PROGRESS_FD_HOLD: "prog_fd_hold",
            const.PROGRESS_DAM_HOLD: "prog_dam_hold",
        }
        for p in bmodels.Process.objects.filter(is_active=True, progress__in=DISPATCH.keys()) \
                        .exclude(manager=None) \
                        .annotate(
                            started=Min("log__logdate"),
                            last_change=Max("log__logdate")) \
                        .order_by("started"):
            tgt = DISPATCH.get(p.progress, None)
            if tgt is not None:
                p.annotate_with_duration_stats()
                ctx.setdefault(tgt, []).append(p)


    DISPATCH = {
        const.PROGRESS_AM_RCVD: "am_prog_rcvd",
        const.PROGRESS_AM: "am_prog_am",
        const.PROGRESS_AM_HOLD: "am_prog_hold",
        const.PROGRESS_AM_OK: "am_prog_done",
        const.PROGRESS_FD_HOLD: "am_prog_done",
        const.PROGRESS_FD_OK: "am_prog_done",
        const.PROGRESS_DAM_HOLD: "am_prog_done",
        const.PROGRESS_DAM_OK: "am_prog_done",
        const.PROGRESS_DONE: "am_prog_done",
        const.PROGRESS_CANCELLED: "am_prog_done",
    }
    for p in bmodels.Process.objects.filter(manager=request.am, progress__in=DISPATCH.keys()) \
                    .annotate(
                        started=Min("log__logdate"),
                        last_change=Max("log__logdate")) \
                    .order_by("started"):
        tgt = DISPATCH.get(p.progress, None)
        if tgt is not None:
            p.annotate_with_duration_stats()
            ctx.setdefault(tgt, []).append(p)

    return render_to_response("restricted/ammain.html", ctx,
                              context_instance=template.RequestContext(request))

def make_am_form(editor):
    excludes = ["person", "is_am_ctte", "created"]

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
        try:
            person = bmodels.Person.objects.get(uid=uid)
        except bmodels.Person.DoesNotExist:
            return http.HttpResponseNotFound("Person with uid %s not found" % uid)
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
                return http.HttpResponseForbidden("Editing is restricted to the am and front desk members")
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


def make_person_form(editor):
    excludes = ["user", "created", "status_changed"]

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
    if person is None:
        return http.HttpResponseNotFound("Person with uid or email %s not found" % key)
    process = person.active_processes
    # FIXME: for now, just pick the first one. To do things properly we need to
    #        be passed what process we should go back to
    if process:
        process = process[0]
    else:
        process = None

    def next_step():
        if process:
            return redirect(process.get_absolute_url())
        else:
            return redirect(person.get_absolute_url())

    if not person.can_be_edited(request.am):
        return next_step()

    PersonForm = make_person_form(request.am)

    form = None
    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            form.save()
            # TODO: message that it has been saved
            return next_step()
    else:
        form = PersonForm(instance=person)

    return render_to_response("restricted/person.html",
                              dict(
                                  person=person,
                                  process=process,
                                  form=form,
                              ),
                              context_instance=template.RequestContext(request))

def make_newprocessform(person):
    choices = [(x.tag, x.ldesc) for x in const.ALL_STATUS if x[1] != person.status]

    class NewProcessForm(forms.Form):
        applying_for = forms.ChoiceField(
            required=True,
            label=_("Applying for"),
            choices=choices
        )
        logtext = forms.CharField(
            required=True,
            label=_("Log text"),
            widget=forms.Textarea(attrs=dict(rows=5, cols=80))
        )
    return NewProcessForm

@backend.auth.is_admin
def newprocess(request, applying_for, key):
    """
    Create a new process
    """
    person = bmodels.Person.lookup(key)
    if person is None:
        return http.HttpResponseNotFound("Person %s not found" % key)

    if applying_for not in person.get_allowed_processes():
        return http.HttpResponseForbidden("Person %s cannot start a %s process" % (key, applying_for))

    process = bmodels.Process(
        person=person,
        progress=const.PROGRESS_APP_NEW,
        is_active=True,
        applying_as=person.status,
        applying_for=applying_for,
    )
    process.save()

    log = bmodels.Log(
        changed_by=request.person,
        process=process,
        progress=process.progress,
    )
    log.save()

    return redirect('public_process', key=process.lookup_key)

def db_export(request):
    # In theory, this isn't needed as it's enforced by DACS
    if request.user.is_anonymous():
        return http.HttpResponseForbidden("You need to be logged in")

    if "full" in request.GET:
        if not request.am or not request.am.is_admin:
            return http.HttpResponseForbidden("You need to be FD or DAM to get a full DB export")
        full = True
    else:
        full = False

    people = list(bmodels.export_db(full))

    class Serializer(json.JSONEncoder):
        def default(self, o):
            if hasattr(o, "strftime"):
                return o.strftime("%Y-%m-%d %H:%M:%S")
            return json.JSONEncoder.default(self, o)

    res = http.HttpResponse(mimetype="application/json")
    if full:
        res["Content-Disposition"] = "attachment; filename=nm-full.json"
    else:
        res["Content-Disposition"] = "attachment; filename=nm-mock.json"
    json.dump(people, res, cls=Serializer, indent=1)
    return res


class MinechangelogsForm(forms.Form):
    query = forms.CharField(
        required=True,
        label=_("Query"),
        help_text=_("Enter one keyword per line. Changelog entries to be shown must match at least one keyword. You often need to tweak the keywords to improve the quality of results"),
        widget=forms.Textarea(attrs=dict(rows=5, cols=40))
    )
    download = forms.BooleanField(
        required=False,
        label=_("Download"),
        help_text=_("Activate this field to download the changelog instead of displaying it"),
    )

def minechangelogs(request, key=None):
    entries = None
    info = mmodels.info()
    info["max_ts"] = datetime.datetime.fromtimestamp(info["max_ts"])
    info["last_indexed"] = datetime.datetime.fromtimestamp(info["last_indexed"])

    if key:
        person = bmodels.Person.lookup(key)
        if person is None:
            return http.HttpResponseNotFound("Person with uid or email %s not found" % key)
    else:
        person = None

    if request.method == 'POST':
        form = MinechangelogsForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["query"]
            keywords = [x.strip() for x in query.split("\n")]
            entries = mmodels.query(keywords)
            if form.cleaned_data["download"]:
                def send_entries():
                    for e in entries:
                        yield e
                        yield "\n\n"
                res = http.HttpResponse(send_entries(), content_type="text/plain")
                if person:
                    res["Content-Disposition"] = 'attachment; filename=changelogs-%s.txt' % person.lookup_key
                else:
                    res["Content-Disposition"] = 'attachment; filename=changelogs.txt'
                return res
            else:
                entries = list(entries)
    else:
        if person:
            query = [
                person.fullname,
                person.email,
            ]
            if person.uid:
                query.append(person.uid)
            form = MinechangelogsForm(initial=dict(query="\n".join(query)))
        else:
            form = MinechangelogsForm()

    return render_to_response("restricted/minechangelogs.html",
                              dict(
                                  form=form,
                                  info=info,
                                  entries=entries,
                                  person=person,
                              ),
                              context_instance=template.RequestContext(request))

def login_redirect(request):
    url = request.GET.get("url", None)
    if url is None:
        return redirect('home')
    else:
        return redirect(url)
