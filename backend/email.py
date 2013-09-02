from __future__ import absolute_import
from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.utils.log import getLogger
import email
import email.utils
from . import const

log = getLogger(__name__)

EMAIL_PUBLIC_ANNOUNCES = getattr(settings, "EMAIL_PUBLIC_ANNOUNCES", "debian-newmaint@lists.debian.org")
EMAIL_PRIVATE_ANNOUNCES = getattr(settings, "EMAIL_PRIVATE_ANNOUNCES", "nm@debian.org")
EMAIL_PERSONAL_DIVERT = getattr(settings, "EMAIL_PERSONAL_DIVERT", None)

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

def announce_public(request, subject, text):
    sender_addr = get_email_address(request)
    fromaddr = email.utils.formataddr((request.person.fullname + " via nm", sender_addr))
    send_mail(subject, text, fromaddr, [EMAIL_PUBLIC_ANNOUNCES])

def announce_private(request, subject, text):
    sender_addr = get_email_address(request)
    fromaddr = email.utils.formataddr((request.person.fullname + " via nm", sender_addr))
    send_mail(subject, text, fromaddr, [EMAIL_PRIVATE_ANNOUNCES])

def personal_email(request, recipients, subject, text):
    # TODO: Cc EMAIL_PRIVATE_ANNOUNCES?
    # Details in https://docs.djangoproject.com/en/dev/topics/email/ but needs
    # 1.3 for the cc parameter
    fromaddr = email.utils.formataddr((request.person.fullname + " via nm", "nm@debian.org"))
    # Divert to other recipients when testing, to avoid spamming people with
    # test messages
    if EMAIL_PERSONAL_DIVERT: recipients = EMAIL_PERSONAL_DIVERT
    send_mail(subject, text, fromaddr, recipients)

def parse_recipient_list(s):
    """
    Parse a string like "Foo <a@b.c>, bar@example.com"
    and return a list like ["Foo <a@b.c>", "bar@example.com"]
    """
    res = []
    for name, email in email.utils.getaddresses([s]):
        res.append(email.utils.formataddr(name, email))
    return res

def send_notification(template_name, log, log_prev=None):
    """
    Render a notification email template for a transition from log_prev to log,
    then send the resulting email.
    """
    try:
        ctx = {
            "process": log.process,
            "log": log,
            "log_prev": log_prev,
        }
        text = render_to_string("notification_mails/%s.txt" % template_name, ctx).strip()
        m = email.message_from_string(text)
        msg = EmailMessage()
        msg.from_email = m.get("From", log.changed_by.preferred_email)
        msg.to = m.get("To", EMAIL_PRIVATE_ANNOUNCES)
        if "Cc" in m: msg.cc = parse_recipient_list(m.get("Cc"))
        if "Bcc" in m: msg.bcc = parse_recipient_list(m.get("Bcc"))
        msg.subject = m.get("Subject", "Notification from nm.debian.org")
        msg.body = m.get_payload()
        msg.send()
        log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
                msg.from_email,
                msg.to.join(", "),
                msg.cc.join(", "),
                msg.bcc.join(", "),
                msg.subject)
    except:
        # TODO: remove raise once it works
        raise
        log.debug("mailed to sent mail for log %s", log)

