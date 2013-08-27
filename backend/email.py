from __future__ import absolute_import
from django.conf import settings
from django.core.mail import send_mail
import email.utils
from . import const

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

