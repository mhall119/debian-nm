from django import template
import datetime

register = template.Library()

@register.filter
def none_if_epoch(value):
    epoch = datetime.datetime(1970, 1, 1)    
    if value == epoch:
        return None
    else:
        return value
