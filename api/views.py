# nm.debian.org website API
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
from django.utils.translation import ugettext as _
from django.forms.models import model_to_dict
import backend.models as bmodels
from backend import const
import datetime
import json

class Serializer(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, "strftime"):
            return o.strftime("%Y-%m-%d %H:%M:%S")
        return json.JSONEncoder.default(self, o)

def json_response(val):
    res = http.HttpResponse(mimetype="application/json")
    json.dump(val, res, cls=Serializer, indent=1)
    return res

def person_to_json(p, **kw):
    return model_to_dict(p, **kw)

def people(request):
    if request.method != "GET":
        return http.HttpResponseForbidden("Only GET request is allowed here")

    # Pick what to include in the result based on auth status
    fields = ["cn", "mn", "sn", "uid", "fpr", "status", "status_changed", "created"]
    if request.person:
        fields.append("email")
        if request.person.is_admin:
            fields.append("fd_comment")

    try:
        res = []

        # Build query
        people = bmodels.Person.objects.all()

        val = request.GET.get("cn", "")
        if val: people = people.filter(cn__icontains=val)

        val = request.GET.get("mn", "")
        if val: people = people.filter(mn__icontains=val)

        val = request.GET.get("sn", "")
        if val: people = people.filter(sn__icontains=val)

        val = request.GET.get("email", "")
        if val: people = people.filter(email__icontains=val)

        val = request.GET.get("uid", "")
        if val: people = people.filter(uid__icontains=val)

        val = request.GET.get("fpr", "")
        if val: people = people.filter(fpr__icontains=val)

        val = request.GET.get("status", "")
        if val: people = people.filter(status=val)

        val = request.GET.get("fd_comment", "")
        if val: people = people.filter(fd_comment__icontains=val)

        for p in people:
            res.append(person_to_json(p, fields=fields))

        res = dict(r=res)
    except Exception, e:
        res = dict(e=str(e))

    return json_response(res)
