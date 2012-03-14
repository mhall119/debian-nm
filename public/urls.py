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

from django.conf.urls.defaults import *
from django.core.urlresolvers import reverse
from django.views.generic.simple import direct_to_template, redirect_to

urlpatterns = patterns('public.views',
    url(r'^$', redirect_to, {'url': "/"}, name="public_index"),
    url(r'^newnm$', direct_to_template, {'template': 'public/newnm.html'}, name="public_newnm"),
    url(r'^processes$', 'processes', name="processes"),
    url(r'^managers$', 'managers', name="managers"),
    url(r'^people(?:/(?P<status>\w+))?$', 'people', name="people"),
    url(r'^person/(?P<key>[^/]+)$', 'person', name="person"),
    url(r'^process/(?P<key>[^/]+)$', 'process', name="public_process"),
    url(r'^progress/(?P<progress>\w+)$', 'progress', name="public_progress"),

    # Compatibility
    url(r'^whoisam$', 'managers', name="public_whoisam"),
    url(r'^nmstatus/(?P<key>[^/]+)$', 'process', name="public_nmstatus"),
    url(r'^nmlist$', 'processes', name="public_nmlist"),
)
