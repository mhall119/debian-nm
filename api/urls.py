# nm.debian.org website API
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

from django.conf.urls import *
from django.views.generic import TemplateView

urlpatterns = patterns('api.views',
    url(r'^$', TemplateView.as_view(template_name="api/doc.html"), name="api_doc"),
    url(r'^people$', 'people', name="api_people"),
    url(r'^contributors$', 'contributors', name="api_contributors"),
)

