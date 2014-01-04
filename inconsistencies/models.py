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
import keyring.models as kmodels
import json

class Inconsistency(models.Model):
    info = models.TextField(default=json.dumps({"log": []}))
    created = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def info_log(self):
        return json.loads(self.info)["log"]

    @property
    def info_items(self):
        for k, v in json.loads(self.info).iteritems():
            if k == "log": continue
            yield k, v

    def merge_info(self, log=None, **kw):
        info = json.loads(self.info)
        info.update(kw)
        if log is not None:
            if isinstance(log, basestring):
                info["log"].append(log)
            else:
                info["log"].extend(log)
        self.info = json.dumps(info)


class InconsistentPerson(Inconsistency):
    person = models.OneToOneField(bmodels.Person)

    @models.permalink
    def get_absolute_url(self):
        return ("inconsistencies_fix_person", (), dict(key=self.person.lookup_key))

    @classmethod
    def add_info(cls, person, **kw):
        rec, created = cls.objects.get_or_create(person=person)
        rec.merge_info(**kw)
        rec.save()

    @classmethod
    def add_fix(cls, person, **kw):
        """
        Log that a fix has been performed for a person, if an inconsistency
        record exists
        """
        try:
            rec = cls.objects.get(person=person)
        except cls.DoesNotExist:
            return
        rec.merge_info(**kw)
        rec.save()

    def compute_guesses(self):
        info = json.loads(self.info)
        if "keyring_status" in info and info["keyring_status"] is None:
            yield "{} may have changed key. Try to resolve all fingerprint issues first".format(self.person.fullname), []


class InconsistentProcess(Inconsistency):
    process = models.OneToOneField(bmodels.Process)

    @classmethod
    def add_info(cls, process, **kw):
        rec, created = cls.objects.get_or_create(process=process)
        rec.merge_info(**kw)
        rec.save()


class InconsistentFingerprint(Inconsistency):
    fpr = bmodels.FingerprintField("OpenPGP key fingerprint", max_length=40, unique=True)

    @models.permalink
    def get_absolute_url(self):
        return ("inconsistencies_fix_fpr", (), dict(fpr=self.fpr))

    @classmethod
    def add_info(cls, fpr, **kw):
        rec, created = cls.objects.get_or_create(fpr=fpr)
        rec.merge_info(**kw)
        rec.save()

    def compute_guesses(self):
        key = kmodels.UserKey(self.fpr)
        key.want_key()
        for kc in key.keycheck():
            for ku in kc.uids:
                if "skip" in ku.errors: continue
                if len(ku.sigs_ok) == 0: continue
                info = ku.uid.split()
                if info is None: continue
                email = info["email"]
                if not email: continue
                if email.endswith("@debian.org"):
                    uid = email.split("@", 1)[0]
                    try:
                        person = bmodels.Person.objects.get(uid=uid)
                        yield "this seems to be the new key of {} <{}>".format(person.fullname, person.uid), [
                            self._make_set_fpr_action(person)
                        ]
                    except bmodels.Person.DoesNotExist:
                        pass
                try:
                    person = bmodels.Person.objects.get(email=email)
                    yield "this seems to be the new key of {} <{}>".format(person.fullname, person.email), [
                        self._make_set_fpr_action(person)
                    ]
                except bmodels.Person.DoesNotExist:
                    pass

    def _make_set_fpr_action(self, person):
        return {
            "itype": "fpr",
            "ikey": self.fpr,
            "type": "person",
            "key": person.lookup_key,
            "set_fpr": self.fpr,
            "label": "update fingerprint in Person entry",
        }
