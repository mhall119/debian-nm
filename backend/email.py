from __future__ import absolute_import
from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.utils.log import getLogger
import email
import email.utils
from . import const

log = getLogger(__name__)

EMAIL_PRIVATE_ANNOUNCES = getattr(settings, "EMAIL_PRIVATE_ANNOUNCES", "nm@debian.org")

def get_email_address(request):
    """
    If person is DD, returns his/her <login>@debian.org address. Otherwise,
    returns the personal email address.
    """

    dd_statuses = (const.STATUS_DD_U, const.STATUS_DD_NU)
    if request.person.status in dd_statuses:
        email_address = request.person.uid + "@debian.org"
    else:
        email_address = request.person.email
    return email_address

def personal_email(request, recipients, subject, text):
    # TODO: Cc EMAIL_PRIVATE_ANNOUNCES?
    # Details in https://docs.djangoproject.com/en/dev/topics/email/ but needs
    # 1.3 for the cc parameter
    fromaddr = email.utils.formataddr((request.person.fullname + " via nm", "nm@debian.org"))
    send_mail(subject, text, fromaddr, recipients)

def parse_recipient_list(s):
    """
    Parse a string like "Foo <a@b.c>, bar@example.com"
    and return a list like ["Foo <a@b.c>", "bar@example.com"]
    """
    res = []
    for name, addr in email.utils.getaddresses([s]):
        res.append(email.utils.formataddr((name, addr)))
    return res

def send_notification(template_name, log_next, log_prev=None):
    """
    Render a notification email template for a transition from log_prev to log,
    then send the resulting email.
    """
    try:
        ctx = {
            "process": log_next.process,
            "log": log_next,
            "log_prev": log_prev,
        }
        text = render_to_string(template_name, ctx).strip()
        m = email.message_from_string(text.encode('utf-8'))
        msg = EmailMessage()
        msg.from_email = m.get("From", log_next.changed_by.preferred_email)
        msg.to = parse_recipient_list(m.get("To", EMAIL_PRIVATE_ANNOUNCES))
        if "Cc" in m: msg.cc = parse_recipient_list(m.get("Cc"))
        if "Bcc" in m: msg.bcc = parse_recipient_list(m.get("Bcc"))
        msg.subject = m.get("Subject", "Notification from nm.debian.org")
        msg.body = m.get_payload()
        msg.send()
        log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
                msg.from_email,
                ", ".join(msg.to),
                ", ".join(msg.cc),
                ", ".join(msg.bcc),
                msg.subject)
    except:
        # TODO: remove raise once it works
        raise
        log.debug("mailed to sent mail for log %s", log_next)
