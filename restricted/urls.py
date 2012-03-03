# nm.debian.org website restricted pages
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

from django.conf.urls.defaults import *
from django.core.urlresolvers import reverse
from django.views.generic.simple import direct_to_template, redirect_to

urlpatterns = patterns('restricted.views',
    url(r'^$', direct_to_template, {'template': 'restricted/index.html'}, name="restricted_index"),
    url(r'^amlist$', 'amlist', name="restricted_amlist"),
    url(r'^ammain$', 'ammain', name="restricted_ammain"),
)
