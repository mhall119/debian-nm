# nm.debian.org website backend
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

import backend.const as c

def const(request):
    ctx = dict()

    for s in c.ALL_STATUS:
        ctx[s.code] = s.tag

    for p in c.ALL_PROGRESS:
        ctx[p.code] = p.tag

    return ctx

def current_user(request):
    if request.user.is_anonymous():
        cur_person = None
        cur_am = None
    else:
        cur_person = request.user.get_profile()
        if cur_person.is_am:
            cur_am = cur_person.am
        else:
            cur_am = None

    return dict(
        cur_person=cur_person,
        cur_am=cur_am
    )
