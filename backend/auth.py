import django.contrib.auth.backends
from django.contrib.auth.models import User
from django.conf import settings
from django import http
import backend.models as bmodels

class FakeRemoteUser(object):
    def process_request(self, request):
        request.META["REMOTE_USER"] = settings.TEST_USERNAME
        #print "SET REMOTE_USER TO ", request.META["REMOTE_USER"]

class NMUserBackend(django.contrib.auth.backends.RemoteUserBackend):
    """
    RemoteUserBackend customised to create User objects from Person
    """

    # Copied from RemoteUserBackend and tweaked to validate against Person
    def authenticate(self, remote_user):
        """
        The username passed as ``remote_user`` is considered trusted.  This
        method simply returns the ``User`` object with the given username,
        creating a new ``User`` object if ``create_unknown_user`` is ``True``.

        Returns None if ``create_unknown_user`` is ``False`` and a ``User``
        object with the given username is not found in the database.
        """
        if not remote_user:
            return
        user = None
        username = self.clean_username(remote_user)

        # Get the Person for this username: Person is authoritative over User
        try:
            person = bmodels.Person.objects.get(uid=username)
        except bmodels.Person.DoesNotExist:
            return None

        # Note that this could be accomplished in one try-except clause, but
        # instead we use get_or_create when creating unknown users since it has
        # built-in safeguards for multiple threads.
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_unusable_password()
            if person.is_am():
                # FIXME: ensure this is kept in sync when is_fd is changed
                if person.am.is_fd:
                    user.is_staff = True
                    user.is_superuser = True
            user.save()
            person.user = user
            person.save()

        return user


def is_am(view_func):
    """
    Decorator for views that are restricted to Application Managers
    """

    def _wrapped_view(request, *args, **kwargs):
        person = request.user.get_profile()
        if not person.is_am():
            return http.HttpResponse("This page is restricted to AMs")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def is_fd(view_func):
    """
    Decorator for views that are restricted to FD members
    """

    def _wrapped_view(request, *args, **kwargs):
        person = request.user.get_profile()
        if not person.is_am() or not person.am.is_fd:
            return http.HttpResponse("This page is restricted to Front Desk members")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def is_dam(view_func):
    """
    Decorator for views that are restricted to DAMs
    """

    def _wrapped_view(request, *args, **kwargs):
        person = request.user.get_profile()
        if not person.is_am() or not person.am.is_dam:
            return http.HttpResponse("This page is restricted to Debian Account Managers")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
