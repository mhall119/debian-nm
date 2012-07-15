from __future__ import absolute_import
from django.conf import settings
from django.core.mail import send_mail
import email.utils

EMAIL_PUBLIC_ANNOUNCES = getattr(settings, "EMAIL_PUBLIC_ANNOUNCES", "debian-newmaint@lists.debian.org")
EMAIL_PRIVATE_ANNOUNCES = getattr(settings, "EMAIL_PRIVATE_ANNOUNCES", "nm@debian.org")
EMAIL_PERSONAL_DIVERT = getattr(settings, "EMAIL_PERSONAL_DIVERT", None)

def announce_public(request, subject, text):
    fromaddr = email.utils.formataddr((request.person.fullname + " via nm", request.person.email))
    send_mail(subject, text, fromaddr, [EMAIL_PUBLIC_ANNOUNCES])

def announce_private(request, subject, text):
    fromaddr = email.utils.formataddr((request.person.fullname + " via nm", request.person.email))
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

