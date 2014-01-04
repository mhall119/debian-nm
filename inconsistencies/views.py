# coding: utf-8
# nm.debian.org website inconsistency management
#
# Copyright (C) 2014  Enrico Zini <enrico@debian.org>
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
from django.shortcuts import render, redirect, get_object_or_404
from django import http
import backend.models as bmodels
from . import models as imodels
import backend.auth

@backend.auth.is_admin
def inconsistencies_list(request):
    return render(request, "inconsistencies/list.html", {
        "by_person": imodels.InconsistentPerson.objects.all().order_by("created"),
        "by_process": imodels.InconsistentProcess.objects.all().order_by("created"),
        "by_fpr": imodels.InconsistentFingerprint.objects.all().order_by("created"),
    })

@backend.auth.is_admin
def fix_person(request, key):
    person = bmodels.Person.lookup_or_404(key)
    inconsistency = get_object_or_404(imodels.InconsistentPerson, person=person)
    return render(request, "inconsistencies/fix_person.html", {
        "inconsistency": inconsistency,
        "person": person,
        "log": inconsistency.info_log,
        "items": dict(inconsistency.info_items),
    })

@backend.auth.is_admin
def fix_fpr(request, fpr):
    inconsistency = get_object_or_404(imodels.InconsistentFingerprint, fpr=fpr)
    return render(request, "inconsistencies/fix_fpr.html", {
        "inconsistency": inconsistency,
        "fpr": fpr,
        "log": inconsistency.info_log,
        "items": dict(inconsistency.info_items),
    })

@backend.auth.is_admin
def fix(request):
    if request.method != "POST":
        return http.HttpResponseBadRequest("only POST is allowed")

    itype = request.POST["itype"]
    if itype == "fpr":
        inconsistency = get_object_or_404(imodels.InconsistentFingerprint, fpr=request.POST["ikey"])
    else:
        return http.HttpResponseNotFound("cannot lookup inconsistency type")

    type = request.POST["type"]
    if type == "person":
        person = bmodels.Person.lookup_or_404(request.POST["key"])
        log = []
        set_fpr = request.POST.get("set_fpr")
        if set_fpr is not None:
            log.append("fix: fingerprint set to {}".format(set_fpr))
            person.fpr = set_fpr
        if log:
            person.save()
            imodels.InconsistentPerson.add_fix(person, log=log)
            inconsistency.delete()

    return redirect("inconsistencies_list")
