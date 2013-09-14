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
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
import backend.models as bmodels
import minechangelogs.models as mmodels
from backend import const
import backend.auth
import backend.email
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
            const.PROGRESS_POLL_SENT: "prog_app_new",
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
        person = request.person
        am = person.am
    else:
        am = bmodels.AM.lookup_or_404(uid)
        person = am.person

    AMForm = make_am_form(am)

    form = None
    if request.method == 'POST':
        form = AMForm(request.POST, instance=am)
        if form.is_valid():
            cur_am = request.am
            if cur_am == am or cur_am.is_fd or cur_am.is_dam:
                form.save()
            else:
                return PermissionDenied
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


@login_required
def person(request, key):
    """
    Edit a person's information
    """
    person = bmodels.Person.lookup_or_404(key)

    # Check permissions
    edit_bio = person.bio_editable_by(request.person)
    edit_ldap = person.ldap_fields_editable_by(request.person)
    if not edit_bio and not edit_ldap:
        raise PermissionDenied

    # Build the form to edit the person
    excludes = ["user", "created", "status_changed"]
    if not edit_bio:
        excludes.append("bio")
    if not edit_ldap:
        excludes.extend(("cn", "mn", "sn", "email", "uid", "fpr"))
    if not request.person.is_admin:
        excludes.extend(("status", "fd_comment"))

    class PersonForm(forms.ModelForm):
        class Meta:
            model = bmodels.Person
            exclude = excludes

    form = None
    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            form.save()

            # TODO: message that it has been saved

            # Redirect to the person view
            return redirect(person.get_absolute_url())

    else:
        form = PersonForm(instance=person)

    return render_to_response("restricted/person.html",
                              dict(
                                  person=person,
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
    person = bmodels.Person.lookup_or_404(key)

    if applying_for not in person.get_allowed_processes():
        raise PermissionDenied

    process = bmodels.Process(
        person=person,
        progress=const.PROGRESS_APP_NEW,
        is_active=True,
        applying_as=person.status,
        applying_for=applying_for,
    )
    process.save()

    text=""
    if 'impersonate' in request.session:
        text = "[%s as %s]" % (request.user, request.person.lookup_key)
    log = bmodels.Log(
        changed_by=request.person,
        process=process,
        progress=process.progress,
        logtext=text,
    )
    log.save()

    return redirect('public_process', key=process.lookup_key)

def db_export(request):
    # In theory, this isn't needed as it's enforced by DACS
    if request.user.is_anonymous():
        return PermissionDenied

    if "full" in request.GET:
        if not request.am or not request.am.is_admin:
            return PermissionDenied
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
        help_text=_("Enter one keyword per line. Changelog entries to be shown must match at least one keyword. You often need to tweak the keywords to improve the quality of results. Note that keyword matching is case-sensitive."),
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
        person = bmodels.Person.lookup_or_404(key)
    else:
        person = None

    keywords=None
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
                                  keywords=keywords,
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

def impersonate(request, key=None):
    if key is None:
        del request.session["impersonate"]
    elif request.person.is_admin:
        person = bmodels.Person.lookup_or_404(key)
        request.session["impersonate"] = person.lookup_key

    url = request.GET.get("url", None)
    if url is None:
        return redirect('home')
    else:
        return redirect(url)


class AdvocateDDForm(forms.Form):
    uploading = forms.BooleanField(required=False, label=_("Upload rights"))
    logtext = forms.CharField(required=True, label=_("Advocacy message"), widget=forms.Textarea(attrs={'cols': 80, 'rows': 30}))

def advocate_as_dd(request, key):
    from django.db.models import Min, Max

    person = bmodels.Person.lookup_or_404(key)

    if not request.person.can_advocate_as_dd(person):
        return PermissionDenied

    dd_statuses = (const.STATUS_DD_U, const.STATUS_DD_NU)
    dm_statuses = (const.STATUS_DM, const.STATUS_DM_GA)

    # Get the existing process, if any
    procs = list(person.processes.filter(is_active=True, applying_for__in=dd_statuses))
    if len(procs) > 1:
        return http.HttpResponseServerError("There is more than one active process applying for DD. Please ask Front Desk people to fix that before proceeding")
    if not procs:
        proc = None
    else:
        proc = procs[0]

    if person.status in dm_statuses:
        is_dm = True
        # Have they been DM for more than 6 months?
        now = datetime.datetime.utcnow()

        if now - person.status_changed >= datetime.timedelta(days=6*30):
            # Yes
            is_early = False
        else:
            # Maybe: one can have become a DM a year ago and DM_GA just
            # yesterday
            last_change = None
            for p in person.processes.filter(is_active=False, applying_for__in=dm_statuses) \
                                     .annotate(last_change=Max("log__logdate")) \
                                     .order_by("-last_change"):
                last_change = p.last_change
            if last_change:
                is_early = now - last_change < datetime.timedelta(days=6*30)
            else:
                is_early = True
    else:
        is_dm = False
        is_early = True

    if request.method == "POST":
        form = AdvocateDDForm(request.POST)
        if form.is_valid():
            # Create process if missing
            if proc is None:
                proc = bmodels.Process(
                    person=person,
                    applying_as=person.status,
                    applying_for=const.STATUS_DD_U if form.cleaned_data["uploading"] else const.STATUS_DD_NU,
                    progress=const.PROGRESS_ADV_RCVD,
                    is_active=True)
                proc.save()
                # Log the change
                text = "Process created by %s advocating %s" % (request.person.lookup_key, person.fullname)
                if 'impersonate' in request.session:
                    text = "[%s as %s] %s" % (request.user, request.person.lookup_key, text)
                lt = bmodels.Log(
                    changed_by=request.person,
                    process=proc,
                    progress=const.PROGRESS_APP_NEW,
                    logtext=text,
                )
                lt.save()
            # Add advocate
            proc.advocates.add(request.person)
            # Log the change
            text = form.cleaned_data["logtext"]
            if 'impersonate' in request.session:
                text = "[%s as %s] %s" % (request.user, request.person.lookup_key, text)
            lt = bmodels.Log(
                changed_by=request.person,
                process=proc,
                progress=proc.progress,
                is_public=True,
                logtext=text,
            )
            lt.save()
            # Send mail
            backend.email.send_notification("notification_mails/advocacy_as_dd.txt", lt)
            return redirect('public_process', key=proc.lookup_key)
    else:
        initial = dict(uploading=is_dm)
        if proc:
            uploading=(proc.applying_for == const.STATUS_DD_U)
        form = AdvocateDDForm(initial=initial)

    return render_to_response("restricted/advocate-dd.html",
                              dict(
                                  form=form,
                                  person=person,
                                  process=proc,
                                  is_dm=is_dm,
                                  is_early=is_early,
                              ),
                              context_instance=template.RequestContext(request))

@backend.auth.is_admin
def nm_am_match(request):
    if request.method == "POST":
        import textwrap
        # Perform assignment if requested
        am_key = request.POST.get("am", None)
        am = bmodels.AM.lookup_or_404(am_key)
        nm_key = request.POST.get("nm", None)
        nm = bmodels.Process.lookup_or_404(nm_key)
        nm.manager = am
        nm.progress = const.PROGRESS_AM_RCVD
        nm.save()
        # Parameters for the following templates
        parms = dict(
            fduid=request.person.uid,
            fdname=request.person.fullname,
            amuid=am.person.uid,
            amname=am.person.fullname,
            nmname=nm.person.fullname,
            nmcurstatus=const.ALL_STATUS_DESCS[nm.person.status],
            nmnewstatus=const.ALL_STATUS_DESCS[nm.applying_for],
            procurl=request.build_absolute_uri(reverse("public_process", kwargs=dict(key=nm.lookup_key))),
        )
        l = bmodels.Log.for_process(nm, changed_by=request.person)
        l.logtext = "Assigned to %(amuid)s" % parms
        if 'impersonate' in request.session:
            l.logtext = "[%s as %s] %s" % (request.user, request.person.lookup_key, l.logtext)
        l.save()
        # Send mail
        lines = [
            "Hello," % parms,
            "",
        ]
        lines.extend(textwrap.wrap(
            "I have just assigned you a new NM applicant: %(nmname)s, who is"
            " %(nmcurstatus)s and is applying for %(nmnewstatus)s." % parms, 72))
        lines.append("")
        if nm.mailbox_file:
            lines.append("The mailbox with everything so far can be downloaded at:")
            lines.append(request.build_absolute_uri(reverse("download_mail_archive", kwargs=dict(key=nm.lookup_key))))
            lines.append("")
        lines.extend(textwrap.wrap(
            "Note that you have not acknowledged the assignment yet, and"
            " could still refuse it, for example if you do not"
            " have time at the moment." % parms, 72))
        lines.append("")
        lines.extend(textwrap.wrap(
            "Please visit [1] to acknowledge the assignment and, later,"
            " to track the progress of the application. Please email"
            " nm@debian.org if you wish to decline the assignment." % parms, 72))
        lines.append("")
        lines.append("[1] %(procurl)s" % parms)
        lines.append("")
        lines.extend(textwrap.wrap(
            "Have a good AMing, and if you need anything please mail nm@debian.org.", 72))
        lines.append("")
        lines.append("%(fdname)s (for Front Desk)" % parms)
        backend.email.personal_email(request,
                                     [am.person.uid + "@debian.org", nm.person.email],
                                     "New NM applicant %s <%s>" % (nm.person.fullname, nm.person.email),
                                     "\n".join(lines))

    from django.db.models import Min, Max
    procs = []
    for p in bmodels.Process.objects.filter(is_active=True, progress=const.PROGRESS_APP_OK) \
                    .annotate(
                        started=Min("log__logdate"),
                        last_change=Max("log__logdate")) \
                    .order_by("started"):
        p.annotate_with_duration_stats()
        procs.append(p)
    ams = bmodels.AM.list_free()

    json_ams = dict()
    for a in ams:
        json_ams[a.person.lookup_key] = dict(
            name=a.person.fullname,
            uid=a.person.uid,
            email=a.person.email,
            key=a.person.lookup_key,
        )
    json_nms = dict()
    for p in procs:
        json_nms[p.lookup_key] = dict(
            name=p.person.fullname,
            uid=p.person.uid,
            email=p.person.email,
            key=p.lookup_key,
        )

    ctx = dict(
        procs=procs,
        ams=ams,
        json_ams=json.dumps(json_ams),
        json_nms=json.dumps(json_nms),
    )
    return render_to_response("restricted/nm-am-match.html", ctx,
                              context_instance=template.RequestContext(request))

def mail_archive(request, key):
    process = bmodels.Process.lookup_or_404(key)

    if not process.can_be_edited(request.am):
        return PermissionDenied

    fname = process.mailbox_file
    if fname is None:
        from django.http import Http404
        return Http404

    user_fname = "%s.mbox" % (process.person.uid or process.person.email)

    res = http.HttpResponse(mimetype="application/octet-stream")
    res["Content-Disposition"] = "attachment; filename=%s.gz" % user_fname

    # Compress the mailbox and pass it to the request
    from gzip import GzipFile
    import os.path
    import shutil
    # The last mtime argument seems to only be supported in python 2.7
    outfd = GzipFile(user_fname, "wb", 9, res) #, os.path.getmtime(fname))
    try:
        with open(fname) as infd:
            shutil.copyfileobj(infd, outfd)
    finally:
        outfd.close()
    return res
