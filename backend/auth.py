from django.contrib.auth.models import User
from django import http
from django.shortcuts import redirect
import backend.models as bmodels
from django_dacs.auth import DACSUserBackend

class NMUserBackend(DACSUserBackend):
    """
    RemoteUserBackend customised to create User objects from Person
    """

    def clean_username(self, username):
        """
        Map usernames from DACS to usernames in our auth database
        """
        uid = super(NMUserBackend, self).clean_username(username)
        # TODO: pick domain according to DACS info
        return "%s@debian.org" % uid

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
        if username.endswith("@debian.org"):
            debname = username[:-11]
            try:
                person = bmodels.Person.objects.get(uid=debname)
            except bmodels.Person.DoesNotExist:
                return None
        else:
            return None

        # Note that this could be accomplished in one try-except clause, but
        # instead we use get_or_create when creating unknown users since it has
        # built-in safeguards for multiple threads.
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_unusable_password()
            if person.is_am:
                # FIXME: ensure this is kept in sync when is_fd is changed
                if person.am.is_fd:
                    user.is_staff = True
                    user.is_superuser = True
            user.save()
            person.user = user
            person.save()

        return user

class NMInfoMiddleware(object):
    def process_request(self, request):
        if request.user.is_authenticated():
            request.person = request.user.get_profile()

            # Implement impersonation if requested in session
            if request.person.is_admin:
                key = request.session.get("impersonate", None)
                if key is not None:
                    person = bmodels.Person.lookup(key)
                    if person is not None:
                        request.person = person

            request.am = request.person.am_or_none
        else:
            request.person = None
            request.am = None

def is_am(view_func):
    """
    Decorator for views that are restricted to Application Managers
    """

    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_anonymous():
            return redirect("https://sso.debian.org/sso/login")
        if not request.am:
            return http.HttpResponseForbidden("This page is restricted to AMs")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def is_fd(view_func):
    """
    Decorator for views that are restricted to FD members
    """

    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_anonymous():
            return redirect("https://sso.debian.org/sso/login")
        if not request.am or not request.am.is_fd:
            return http.HttpResponseForbidden("This page is restricted to Front Desk members")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def is_dam(view_func):
    """
    Decorator for views that are restricted to DAMs
    """

    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_anonymous():
            return redirect("https://sso.debian.org/sso/login")
        if not request.am or not request.am.is_dam:
            return http.HttpResponseForbidden("This page is restricted to Debian Account Managers")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def is_admin(view_func):
    """
    Decorator for views that are restricted to FD and DAMs
    """

    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_anonymous():
            return redirect("https://sso.debian.org/sso/login")
        if not request.am or not request.am.is_admin:
            return http.HttpResponseForbidden("This page is restricted to Front Desk members and Debian Account Managers")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
