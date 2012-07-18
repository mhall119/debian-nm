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
    # AM Personal page
    url(r'^ammain$', 'ammain', name="restricted_ammain"),
    # AM preferences editor
    url(r'^amprofile(?:/(?P<uid>\w+))?$', 'amprofile', name="restricted_amprofile"),
    # Edit personal info
    url(r'^person/(?P<key>[^/]+)$', 'person', name="restricted_person"),
    # Create new process for a person
    url(r'^newprocess_(?P<applying_for>[^/]+)/(?P<key>[^/]+)$', 'newprocess', name="restricted_newprocess"),
    # Show changelogs (minechangelogs)
    url(r'^minechangelogs/(?P<key>[^/]+)?$', 'minechangelogs', name="restricted_minechangelogs"),
    # Redirect after login
    url(r'^login-redirect$', 'login_redirect', name="login_redirect"),
    # Impersonate a user
    url(r'^impersonate/(?P<key>[^/]+)?$', 'impersonate', name="impersonate"),
    # Advocate a person to become DD
    url(r'^advocate-dd/(?P<key>[^/]+)$', 'advocate_as_dd', name="advocate_as_dd"),
    # Export database
    url(r'^db-export$', 'db_export', name="restricted_db_export"),
    # Help matching NMs and AMs
    url(r'^nm-am-match/$', 'nm_am_match', name="restricted_nm_am_match"),
    # Advocate a person to become DD
    url(r'^mail-archive/(?P<key>[^/]+)$', 'mail_archive', name="download_mail_archive"),
)
