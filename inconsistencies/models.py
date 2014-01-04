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
from django.db import models
import backend.models as bmodels
import json

class Inconsistency(models.Model):
    info = models.TextField(default=json.dumps({"log": []}))
    created = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def merge_info(self, log=None, **kw):
        info = json.loads(self.info)
        info.update(kw)
        if log is not None:
            info["log"].append(log)
        self.info = json.dumps(info)


class InconsistentPerson(Inconsistency):
    person = models.OneToOneField(bmodels.Person)

    @classmethod
    def add_info(cls, person, **kw):
        rec, created = cls.objects.get_or_create(person=person)
        rec.merge_info(**kw)
        rec.save()


class InconsistentProcess(Inconsistency):
    process = models.OneToOneField(bmodels.Process)

    @classmethod
    def add_info(cls, process, **kw):
        rec, created = cls.objects.get_or_create(process=process)
        rec.merge_info(**kw)
        rec.save()


class InconsistentFingerprint(Inconsistency):
    fpr = bmodels.FingerprintField("OpenPGP key fingerprint", max_length=40, unique=True)

    @classmethod
    def add_info(cls, fpr, **kw):
        rec, created = cls.objects.get_or_create(fpr=fpr)
        rec.merge_info(**kw)
        rec.save()
