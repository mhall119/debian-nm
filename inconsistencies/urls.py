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
from django.conf.urls import *

urlpatterns = patterns('inconsistencies.views',
    url(r'^$', "inconsistencies_list", name="inconsistencies_list"),
    url(r'person/(?P<key>[^/]+)$', "fix_person", name="inconsistencies_fix_person"),
    url(r'fpr/(?P<fpr>[A-F0-9]+)$', "fix_fpr", name="inconsistencies_fix_fpr"),
    url(r'fix$', "fix", name="inconsistencies_fix"),
)

