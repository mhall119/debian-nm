from django import template
from backend import const

register = template.Library()

@register.filter
def editable_by(value, arg):
    return value.can_be_edited(arg)
