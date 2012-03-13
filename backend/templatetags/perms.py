from django import template
from backend import const

register = template.Library()

@register.filter
def editable_by(value, arg):
    return value.can_be_edited(arg)

@register.filter
def is_admin(value):
    # Make sure we work with an AM
    if hasattr(value, "am_or_none"):
        value = value.am_or_none
    if value is None:
        return False
    return value.is_fd or value.is_dam
