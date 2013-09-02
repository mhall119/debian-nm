"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TransactionTestCase
import backend.models as bmodels
import backend.const as bconst
import datetime

class SimpleFixture(object):
    def __init__(self):
        self.fd = bmodels.Person(cn="Enrico", sn="Zini", email="enrico@debian.org", uid="enrico", status=bconst.STATUS_DD_U)
        self.fd.save()

        self.fd_am = bmodels.AM(person=self.fd, slots=1, is_am=True, is_fd=True, is_dam=True)
        self.fd_am.save()

        self.am = bmodels.Person(cn="Jade", sn="Doe", email="jane@debian.org", uid="jane", status=bconst.STATUS_DD_U)
        self.am.save()

        self.am_am = bmodels.AM(person=self.am, slots=1, is_am=True)
        self.am_am.save()

        self.nm = bmodels.Person(cn="John", sn="Smith", email="doctor@example.com", status=bconst.STATUS_MM)
        self.nm.save()

    def make_process_dm(self, progress=bconst.PROGRESS_DONE):
        self.process_dm = bmodels.Process(person=self.nm,
                                       applying_as=bconst.STATUS_MM,
                                       applying_for=bconst.STATUS_DM,
                                       progress=progress,
                                       manager=self.am_am,
                                       is_active=progress==bconst.PROGRESS_DONE)
        self.process_dm.save()

    def make_process_dd(self, progress=bconst.PROGRESS_DONE):
        self.process_dd = bmodels.Process(person=self.nm,
                                       applying_as=bconst.STATUS_DM,
                                       applying_for=bconst.STATUS_DD_U,
                                       progress=progress,
                                       manager=self.am_am,
                                       is_active=progress==bconst.PROGRESS_DONE)
        self.process_dd.save()


class LogTest(TransactionTestCase):
    def setUp(self):
        self.p = SimpleFixture()
        self.p.make_process_dm()
        self.p.make_process_dd(bconst.PROGRESS_APP_OK)

    def test_log_previous(self):
        """
        Check if Log.previous works
        """
        log_dm1 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dm,
                           progress=bconst.PROGRESS_APP_NEW,
                           logdate=datetime.datetime(2013, 1, 1, 0, 0, 0),
                           logtext="process started")
        log_dm1.save()

        log_dd1 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dd,
                           progress=bconst.PROGRESS_APP_NEW,
                           logdate=datetime.datetime(2013, 1, 1, 12, 0, 0),
                           logtext="process started")
        log_dd1.save()

        log_dm2 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dm,
                           progress=bconst.PROGRESS_DONE,
                           logdate=datetime.datetime(2013, 1, 2, 0, 0, 0),
                           logtext="all ok")
        log_dm2.save()

        log_dd2 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dd,
                           progress=bconst.PROGRESS_ADV_RCVD,
                           logdate=datetime.datetime(2013, 1, 2, 12, 0, 0),
                           logtext="all ok")
        log_dd2.save()

        self.assertEquals(log_dm2.previous, log_dm1)
        self.assertEquals(log_dd2.previous, log_dd1)

        log_dd3 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dd,
                           progress=bconst.PROGRESS_APP_OK,
                           logdate=datetime.datetime(2013, 1, 3, 0, 0, 0),
                           logtext="advocacies are ok")
        log_dd3.save()

        self.assertEquals(log_dd3.previous, log_dd2)
        self.assertEquals(log_dd3.previous.previous, log_dd1)


class NotificationTest(TransactionTestCase):
    def setUp(self):
        self.p = SimpleFixture()
        self.p.make_process_dd(bconst.PROGRESS_APP_OK)

    def test_notify_assigned(self):
        l1 = bmodels.Log.for_process(self.p.process_dd)
        l1.changed_by = self.p.fd
        l1.logtext = "ready to get an AM"
        l1.save()

        self.p.process_dd.progress = bconst.PROGRESS_AM_RCVD
        self.p.process_dd.save()

        l1 = bmodels.Log.for_process(self.p.process_dd)
        l1.changed_by = self.p.fd
        l1.logtext = "assigned_am"
        l1.save()

        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['me@example.com'])
