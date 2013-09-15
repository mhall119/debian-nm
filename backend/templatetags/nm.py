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

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from backend import const

register = template.Library()

@register.filter
def sdesc_progress(value):
    info = const.ALL_PROGRESS_BYTAG.get(value, None)
    if info is None: return None
    return info.sdesc

@register.filter
def sdesc_status(value):
    info = const.ALL_STATUS_BYTAG.get(value, None)
    if info is None: return None
    return info.sdesc

@register.filter
def desc_progress(value):
    return const.ALL_PROGRESS_DESCS.get(value, value)

@register.filter
def desc_status(value):
    return const.ALL_STATUS_DESCS.get(value, value)

@register.filter
def seq_progress(value):
    return const.SEQ_PROGRESS.get(value, -1)

@register.filter
def seq_status(value):
    return const.SEQ_STATUS.get(value, -1)

@register.filter
def editable_by(value, arg):
    return value.permissions_of(arg).can_edit_anything

def _splitfp(val):
    for i in range(10):
        yield val[i*4:(i+1)*4]

@register.filter
def fingerprint(value, autoescape=None):
    if value is None:
        return "None"

    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    if len(value) == 40:
        formatted = "%s %s %s %s %s  %s %s %s %s %s" % tuple(_splitfp(value))
    else:
        formatted = value
    return mark_safe("<span class='fpr'>%s</span>" % esc(formatted))
fingerprint.needs_autoescape = True

@register.filter
def formataddr(person):
    """
    Return a formatted address like "Foo <foo@example.org>" for a Person
    """
    import email.utils
    name = person.fullname.encode('unicode_escape') + " via nm"
    addr = person.preferred_email
    return email.utils.formataddr((name, addr))

@register.simple_tag
def nm_js_support():
    res = []

    res.append("// Person status infrastructure")

    # Status info
    res.append("var ALL_STATUS = {")
    for idx, s in enumerate(const.ALL_STATUS):
        res.append('  %s: { seq: %d, sdesc: "%s", ldesc: "%s" },' % (
            s.tag, idx, s.sdesc, s.ldesc))
    res.append("};")

    # Status constants
    for s in const.ALL_STATUS:
        res.append('var %s = "%s";' % (s.code, s.tag))

    res.append("// Process progress infrastructure")

    # Progress info
    res.append("var ALL_PROGRESS = {")
    for idx, s in enumerate(const.ALL_PROGRESS):
        res.append('  %s: { seq: %d, sdesc: "%s", ldesc: "%s" },' % (
            s.tag, idx, s.sdesc, s.ldesc))
    res.append("};")

    # Progress constants
    for s in const.ALL_PROGRESS:
        res.append('var %s = "%s";' % (s.code, s.tag))

    return "\n".join(res)
