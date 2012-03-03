import django.contrib.auth.backends
from django.contrib.auth.models import User
from django.conf import settings
import backend.models as bmodels

class FakeRemoteUser(object):
    def process_request(self, request):
        request.META["REMOTE_USER"] = settings.TEST_USERNAME
        print "SET REMOTE_USER TO ", request.META["REMOTE_USER"]

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
            if person.am:
                # FIXME: ensure this is kept in sync when is_fd is changed
                if person.am.is_fd:
                    user.is_staff = True
                    user.is_superuser = True
            user.save()

        return user
