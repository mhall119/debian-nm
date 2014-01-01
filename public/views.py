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
from django.shortcuts import render_to_response, redirect, render, get_object_or_404
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.timezone import now
import backend.models as bmodels
import backend.email as bemail
from backend import const
import markdown
import datetime
import json

def managers(request):
    from django.db import connection

    # Compute statistics indexed by AM id
    cursor = connection.cursor()
    cursor.execute("""
    SELECT am.id,
           count(*) as total,
           sum(case when process.is_active then 1 else 0 end) as active,
           sum(case when process.progress=%s then 1 else 0 end) as held
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

    cutoff = now() - datetime.timedelta(days=180)

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

def make_statusupdateform(editor):
    if editor.is_fd:
        choices = [(x.tag, "%s - %s" % (x.tag, x.ldesc)) for x in const.ALL_PROGRESS]
    else:
        choices = [(x.tag, x.ldesc) for x in const.ALL_PROGRESS if x[0] in ("PROGRESS_APP_OK", "PROGRESS_AM", "PROGRESS_AM_HOLD", "PROGRESS_AM_OK")]

    class StatusUpdateForm(forms.Form):
        progress = forms.ChoiceField(
            required=True,
            label=_("Progress"),
            choices=choices
        )
        logtext = forms.CharField(
            required=False,
            label=_("Log text"),
            widget=forms.Textarea(attrs=dict(rows=5, cols=80))
        )
        log_is_public = forms.BooleanField(
            required=False,
            label=_("Log is public")
        )
    return StatusUpdateForm

def process(request, key):
    process = bmodels.Process.lookup_or_404(key)
    perms = process.permissions_of(request.person)

    ctx = dict(
        process=process,
        person=process.person,
        perms=perms,
    )

    # Process form ASAP, so we compute the rest with updated values
    am = request.am
    if am and (process.manager == am or am.is_admin) and perms.can_edit_anything:
        StatusUpdateForm = make_statusupdateform(am)
        if request.method == 'POST':
            form = StatusUpdateForm(request.POST)
            if form.is_valid():
                if form.cleaned_data["progress"] == const.PROGRESS_APP_OK \
                    and process.progress in [const.PROGRESS_AM_HOLD, const.PROGRESS_AM, const.PROGRESS_AM_RCVD]:
                    # Unassign from AM
                    process.manager = None
                process.progress = form.cleaned_data["progress"]
                process.save()
                text = form.cleaned_data["logtext"]
                if 'impersonate' in request.session:
                    text = "[%s as %s] %s" % (request.user,
                                                request.person.lookup_key,
                                                text)
                log = bmodels.Log(
                    changed_by=request.person,
                    process=process,
                    progress=process.progress,
                    logtext=text,
                    is_public=form.cleaned_data["log_is_public"]
                )
                log.save()
                form = StatusUpdateForm(initial=dict(progress=process.progress))
        else:
            form = StatusUpdateForm(initial=dict(progress=process.progress))
    else:
        form = None

    ctx["form"] = form

    log = list(process.log.order_by("logdate", "progress"))
    if log:
        ctx["started"] = log[0].logdate
        ctx["last_change"] = log[-1].logdate
    else:
        ctx["started"] = datetime.datetime(1970, 1, 1, 0, 0, 0)
        ctx["last_change"] = datetime.datetime(1970, 1, 1, 0, 0, 0)

    if am:
        ctx["log"] = log
    else:
        # Summarise log for privacy
        distilled_log = []
        last_progress = None
        for l in log:
            if last_progress != l.progress:
                distilled_log.append(dict(
                    progress=l.progress,
                    changed_by=l.changed_by,
                    logdate=l.logdate,
                ))
                last_progress = l.progress
        ctx["log"] = distilled_log

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
        const.PROGRESS_POLL_SENT,
        const.PROGRESS_APP_OK,
        const.PROGRESS_AM_RCVD,
        const.PROGRESS_AM,
        const.PROGRESS_AM_OK,
        const.PROGRESS_FD_OK,
        const.PROGRESS_DAM_OK,
        const.PROGRESS_DONE,
    )

    # Add past/current/future timeline
    curstep_idx = steps.index(curstep)
    ctx["steps"] = steps
    ctx["curstep_idx"] = curstep_idx

    return render_to_response("public/process.html", ctx,
                              context_instance=template.RequestContext(request))

SIMPLIFY_STATUS = {
    const.STATUS_MM: "new",
    const.STATUS_MM_GA: "new",
    const.STATUS_DM: "dm",
    const.STATUS_DM_GA: "dm",
    const.STATUS_DD_U: "dd",
    const.STATUS_DD_NU: "dd",
    const.STATUS_EMERITUS_DD: "emeritus",
    const.STATUS_EMERITUS_DM: "emeritus",
    const.STATUS_REMOVED_DD: "removed",
    const.STATUS_REMOVED_DM: "removed",
}

def people(request, status=None):
    objects = bmodels.Person.objects.all().order_by("uid", "sn", "cn")
    show_status = True
    status_sdesc = None
    status_ldesc = None
    if status:
        if status == "dm_all":
            objects = objects.filter(status__in=(const.STATUS_DM, const.STATUS_DM_GA))
            status_sdesc = _("Debian Maintainer")
            status_ldesc = _("Debian Maintainer (with or without guest account)")
        elif status == "dd_all":
            objects = objects.filter(status__in=(const.STATUS_DD_U, const.STATUS_DD_NU))
            status_sdesc = _("Debian Developer")
            status_ldesc = _("Debian Developer (uploading or not)")
        else:
            objects = objects.filter(status=status)
            show_status = False
            status_sdesc = const.ALL_STATUS_BYTAG[status].sdesc
            status_ldesc = const.ALL_STATUS_BYTAG[status].sdesc

    people = []
    for p in objects:
        p.simple_status = SIMPLIFY_STATUS.get(p.status, None)
        people.append(p)

    return render(request, "public/people.html",
                              dict(
                                  people=people,
                                  status=status,
                                  show_status=show_status,
                                  status_sdesc=status_sdesc,
                                  status_ldesc=status_ldesc,
                              ))

def person(request, key):
    from django.db.models import Min, Max
    person = bmodels.Person.lookup_or_404(key)

    processes = person.processes \
            .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
            .order_by("is_active", "ended")

    can_be_am = False
    if person.is_am:
        am = person.am
        am_processes = am.processed \
                .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                .order_by("is_active", "ended")
    else:
        am = None
        am_processes = []
        if person.status in (const.STATUS_DD_U, const.STATUS_DD_NU) and person.status_changed and (now() - person.status_changed > datetime.timedelta(days=6*30)):
            can_be_am = True

    ctx = dict(
        person=person,
        am=am,
        processes=processes,
        am_processes=am_processes,
        can_be_am=can_be_am,
        can_advocate_as_dd=(request.person and request.person.can_advocate_as_dd(person)),
    )


    # List of statuses the person is already applying for
    for st in person.get_allowed_processes():
        ctx["can_start_%s_process" % st] = True

    ctx["adv_processes"] = person.advocated \
                .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                .order_by("is_active", "ended")

    if person.bio is not None:
        ctx["bio_html"] = markdown.markdown(person.bio, safe_mode="escape")
    else:
        ctx["bio_html"] = ""

    return render_to_response("public/person.html", ctx,
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

def stats(request):
    from django.db.models import Count, Min, Max

    dtnow = now()
    stats = dict()

    # Count of people by status
    by_status = dict()
    for row in bmodels.Person.objects.values("status").annotate(Count("status")):
        by_status[row["status"]] = row["status__count"]
    stats["by_status"] = by_status

    # Count of applicants by progress
    by_progress = dict()
    for row in bmodels.Process.objects.filter(is_active=True).values("progress").annotate(Count("progress")):
        by_progress[row["progress"]] = row["progress__count"]
    stats["by_progress"] = by_progress

    # If JSON is requested, dump them right away
    if 'json' in request.GET:
        res = http.HttpResponse(mimetype="application/json")
        res["Content-Disposition"] = "attachment; filename=stats.json"
        json.dump(stats, res, indent=1)
        return res

    # Cook up more useful bits for the templates

    ctx = dict(stats=stats)

    status_table = []
    for status in (s.tag for s in const.ALL_STATUS):
        status_table.append((status, by_status.get(status, 0)))
    ctx["status_table"] = status_table
    ctx["status_table_json"] = json.dumps([(s.sdesc, by_status.get(s.tag, 0)) for s in const.ALL_STATUS])

    progress_table = []
    for progress in (s.tag for s in const.ALL_PROGRESS):
        progress_table.append((progress, by_progress.get(progress, 0)))
    ctx["progress_table"] = progress_table
    ctx["progress_table_json"] = json.dumps([(p.sdesc, by_progress.get(p.tag, 0)) for p in const.ALL_PROGRESS])

    # List of active processes with statistics
    active_processes = []
    for p in bmodels.Process.objects.filter(is_active=True):
        p.annotate_with_duration_stats()
        mbox_mtime = p.mailbox_mtime
        if mbox_mtime is None:
            p.mbox_age = None
        else:
            p.mbox_age = (dtnow - mbox_mtime).days
        active_processes.append(p)
    active_processes.sort(key=lambda x:x.log_first.logdate)
    ctx["active_processes"] = active_processes

    return render_to_response("public/stats.html", ctx,
                              context_instance=template.RequestContext(request))

def make_findperson_form(request):
    excludes = ["user", "created", "status_changed", "expires", "pending"]

    if not request.am or not request.am.is_admin:
        excludes.append("fd_comment")

    class FindpersonForm(forms.ModelForm):
        class Meta:
            model = bmodels.Person
            exclude = excludes
    return FindpersonForm

def findperson(request):
    FindpersonForm = make_findperson_form(request)

    if request.method == 'POST':
        if not request.am or not request.am.is_admin:
            return http.HttpResponseForbidden("Only FD members can create new people in the site")

        form = FindpersonForm(request.POST)
        if form.is_valid():
            person = form.save()
            return redirect(person.get_absolute_url())
    else:
        form = FindpersonForm()

    return render_to_response("public/findperson.html", dict(
                                  form=form,
                              ),
                              context_instance=template.RequestContext(request))

def stats_latest(request):
    from django.db.models import Count, Min, Max

    days = int(request.GET.get("days", "7"))
    threshold = datetime.date.today() - datetime.timedelta(days=days)

    raw_counts = dict((x.tag, 0) for x in const.ALL_PROGRESS)
    for p in bmodels.Process.objects.values("progress").annotate(count=Count("id")).filter(is_active=True):
        raw_counts[p["progress"]] = p["count"]

    counts = dict(
        new=raw_counts[const.PROGRESS_APP_NEW] + raw_counts[const.PROGRESS_APP_RCVD] + raw_counts[const.PROGRESS_ADV_RCVD],
        new_hold=raw_counts[const.PROGRESS_APP_HOLD],
        new_ok=raw_counts[const.PROGRESS_APP_OK],
        am=raw_counts[const.PROGRESS_AM_RCVD] + raw_counts[const.PROGRESS_AM],
        am_hold=raw_counts[const.PROGRESS_AM_HOLD],
        fd=raw_counts[const.PROGRESS_AM_OK],
        fd_hold=raw_counts[const.PROGRESS_FD_HOLD],
        dam=raw_counts[const.PROGRESS_FD_OK],
        dam_hold=raw_counts[const.PROGRESS_DAM_HOLD],
        dam_ok=raw_counts[const.PROGRESS_DAM_OK],
    )

    irc_topic = "New %(new)d+%(new_hold)d ok %(new_ok)d | AM: %(am)d+%(am_hold)d | FD: %(fd)d+%(fd_hold)d | DAM: %(dam)d+%(dam_hold)d ok %(dam_ok)d" % counts

    events = []

    # Collect status change events
    for p in bmodels.Person.objects.filter(status_changed__gte=threshold).order_by("-status_changed"):
        events.append(dict(
            type="status",
            time=p.status_changed,
            person=p,
        ))

    # Collect progress change events
    for pr in bmodels.Process.objects.filter(is_active=True):
        old_progress = None
        for l in pr.log.order_by("logdate"):
            if l.progress != old_progress:
                if l.logdate.date() >= threshold:
                    events.append(dict(
                        type="progress",
                        time=l.logdate,
                        person=pr.person,
                        log=l,
                    ))
                old_progress = l.progress

    events.sort(key=lambda x:x["time"])

    ctx = dict(
        counts=counts,
        raw_counts=raw_counts,
        irc_topic=irc_topic,
        events=events,
    )

    # If JSON is requested, dump them right away
    if 'json' in request.GET:
        json_evs = []
        for e in ctx["events"]:
            ne = dict(
                status_changed_dt=e["time"].strftime("%Y-%m-%d %H:%M:%S"),
                status_changed_ts=e["time"].strftime("%s"),
                uid=e["person"].uid,
                fn=e["person"].fullname,
                key=e["person"].lookup_key,
                type=e["type"],
            )
            if e["type"] == "status":
                ne.update(
                    status=e["person"].status,
                )
            elif e["type"] == "progress":
                ne.update(
                    process_key=e["log"].process.lookup_key,
                    progress=e["log"].progress,
                )
            json_evs.append(ne)
        ctx["events"] = json_evs
        res = http.HttpResponse(mimetype="application/json")
        res["Content-Disposition"] = "attachment; filename=stats.json"
        json.dump(ctx, res, indent=1)
        return res

    return render(request, "public/stats_latest.html", ctx)


class NewPersonForm(forms.ModelForm):
    class Meta:
        model = bmodels.Person
        fields = ["cn", "mn", "sn", "email", "bio", "uid", "fpr"]

def newnm(request):
    """
    Display the new Person form
    """
    DAYS_VALID = 3

    if request.method == 'POST':
        form = NewPersonForm(request.POST)
        if form.is_valid():
            person = form.save(commit=False)
            person.status = const.STATUS_MM
            person.status_changed = now()
            person.make_pending(days_valid=DAYS_VALID)
            person.save()
            # Redirect to the send challenge page
            return redirect("public_newnm_resend_challenge", key=person.lookup_key)
    else:
        form = NewPersonForm()
    return render(request, "public/newnm.html", {
        "form": form,
        "DAYS_VALID": DAYS_VALID,
    })

def newnm_resend_challenge(request, key):
    """
    Send/resend the encrypted email nonce for people who just requested a new
    Person record
    """
    from keyring.models import UserKey
    person = bmodels.Person.lookup_or_404(key)
    confirm_url = request.build_absolute_uri(reverse("public_newnm_confirm", kwargs=dict(nonce=person.pending)))
    plaintext = "Please visit {} to confirm your application at {}\n".format(
            confirm_url,
            request.build_absolute_uri(person.get_absolute_url()))
    key = UserKey(person.fpr)
    encrypted = key.encrypt(plaintext.encode("utf8"))
    bemail.send_nonce("notification_mails/newperson.txt", person, encrypted_nonce=encrypted)
    return redirect(person.get_absolute_url())

def newnm_confirm(request, nonce):
    """
    Confirm a pending Person object, given its nonce
    """
    person = get_object_or_404(bmodels.Person, pending=nonce)
    person.pending = ""
    person.expires = now() + datetime.timedelta(days=30)
    person.save()
    return redirect(person.get_absolute_url())

