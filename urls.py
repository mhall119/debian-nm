# NM website
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

from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django_dacs.views import login_redirect

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^robots.txt$', TemplateView.as_view(template_name='robots.txt', content_type="text/plain"), name="root_robots_txt"),
    url(r'^$', TemplateView.as_view(template_name='index.html'), name="home"),
    url(r'^license/$', TemplateView.as_view(template_name='license.html'), name="root_license"),
    url(r'^faq/$', TemplateView.as_view(template_name='faq.html'), name="root_faq"),
    # DACS login
    url(r'^am/login-dacs$', login_redirect, name="login_redirect"),
    url(r'^public/', include("public.urls")),
    url(r'^am/', include("restricted.urls")),
    url(r'^api/', include("api.urls")),

    # Uncomment the admin/doc line below to enable admin documentation:
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)
