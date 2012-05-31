from __future__ import absolute_import
from django.conf import settings
from django.core.mail import send_mail
import email.utils

EMAIL_PUBLIC_ANNOUNCES = getattr(settings, "EMAIL_PUBLIC_ANNOUNCES", "debian-newmaint@lists.debian.org")
EMAIL_PRIVATE_ANNOUNCES = getattr(settings, "EMAIL_PRIVATE_ANNOUNCES", "nm@debian.org")

def announce_public(request, subject, text):
    fromaddr = email.utils.formataddr((request.person.fullname + " via nm", request.person.email))
    send_mail(subject, text, fromaddr, [EMAIL_PUBLIC_ANNOUNCES])

def announce_private(request, subject, text):
    fromaddr = email.utils.formataddr((request.person.fullname + " via nm", request.person.email))
    send_mail(subject, text, fromaddr, [EMAIL_PRIVATE_ANNOUNCES])

