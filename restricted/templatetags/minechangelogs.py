from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter(name='mc_format_entry', needs_autoescape=True)
def mc_format_entry(value, keywords, autoescape=None):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    re_bts = re.compile("^#(\d+)$")

    # Build a regular expression matching anything we'd like to markup
    tokenizer = [re.escape(k) for k in keywords]
    tokenizer.append(r"#\d+")
    tokenizer = "(%s)" % "|".join(tokenizer)
    tokenizer = re.compile(tokenizer)

    keywords = frozenset(keywords)
    tokenized = tokenizer.split(value)
    for i in xrange(len(tokenized)):
        if tokenized[i] in keywords:
            # highlight keywords
            tokenized[i] = "<b>%s</b>" % esc(tokenized[i])
        elif tokenized[i].startswith("#"):
            mo = re_bts.match(tokenized[i])
            if mo:
                # link bugs to BTS
                tokenized[i] = "<a href='http://bugs.debian.org/%s'>#%s</a>" % (mo.group(1), mo.group(1))
            else:
                tokenized[i] = esc(tokenized[i])
        else:
            tokenized[i] = esc(tokenized[i])

    return mark_safe("".join(tokenized))
