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
from django.shortcuts import render, get_object_or_404
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

