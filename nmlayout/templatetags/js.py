# nm.debian.org website layout
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

from django import template
from django.conf import settings
from backend import const

MEDIA_URL = getattr(settings, "MEDIA_URL", "/static/")

register = template.Library()

JS_MODULES = dict(
    core=dict(
        files=["jquery-1.7.1.min.js"]
    ),
    tables=dict(
        deps=["core"],
        files=["jquery.tablesorter.min.js"],
    ),
    nm=dict(
        deps=["core"],
        files=["nm.js"],
    ),
)

@register.simple_tag
def jsinclude(modlist):
    seen = set()
    modules = []

    def add_module(name):
        info = JS_MODULES[name]

        # Add dependencies
        for dep in info.get("deps", []):
            add_module(dep)

        # Add files
        for fn in info.get("files", []):
            if fn in seen: continue
            modules.append('<script src="%sjs/%s"></script>' % (MEDIA_URL, fn))
            seen.add(fn)

    # Fill in the module list
    for name in modlist.split(","):
        add_module(name)

    return "\n".join(modules)


