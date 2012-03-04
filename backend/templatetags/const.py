from django import template
from backend import const

register = template.Library()

@register.filter
def desc_progress(value):
    return const.ALL_PROGRESS_DESCS.get(value, value)

@register.filter
def desc_status(value):
    return const.ALL_STATUS_DESCS.get(value, value)
