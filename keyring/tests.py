# coding: utf-8
# nm.debian.org keyring access functions
#
# Copyright (C) 2012--2013  Enrico Zini <enrico@debian.org>
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
from django.test import TestCase
from . import models as kmodels


class LookupTest(TestCase):
    def test_dd_u(self):
        fpr = next(kmodels.list_dd_u())
        self.assertTrue(kmodels.is_dd_u(fpr))
        self.assertFalse(kmodels.is_dm(fpr))
        self.assertFalse(kmodels.is_dd_nu(fpr))

    def test_dd_nu(self):
        fpr = next(kmodels.list_dd_nu())
        self.assertTrue(kmodels.is_dd_nu(fpr))
        self.assertFalse(kmodels.is_dm(fpr))
        self.assertFalse(kmodels.is_dd_u(fpr))

    def test_dm(self):
        fpr = next(kmodels.list_dm())
        self.assertTrue(kmodels.is_dm(fpr))
        self.assertFalse(kmodels.is_dd_u(fpr))
        self.assertFalse(kmodels.is_dd_nu(fpr))
