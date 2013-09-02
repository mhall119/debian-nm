"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TransactionTestCase
import backend.models as bmodels
import backend.const as bconst
import datetime

class LogTest(TransactionTestCase):
    def setUp(self):
        self.person = bmodels.Person(cn="Enrico", sn="Zini", email="enrico@debian.org", uid="enrico", status=bconst.STATUS_MM)
        self.person.save()
        self.process_dm = bmodels.Process(person=self.person,
                                       applying_as=bconst.STATUS_MM,
                                       applying_for=bconst.STATUS_DM,
                                       progress=bconst.PROGRESS_DONE,
                                       is_active=False)
        self.process_dm.save()
        self.process_dd = bmodels.Process(person=self.person,
                                       applying_as=bconst.STATUS_DM,
                                       applying_for=bconst.STATUS_DD_U,
                                       progress=bconst.PROGRESS_APP_OK,
                                       is_active=True)
        self.process_dd.save()

    def test_log_previous(self):
        """
        Check if Log.previous works
        """
        log_dm1 = bmodels.Log(changed_by=self.person,
                           process=self.process_dm,
                           progress=bconst.PROGRESS_APP_NEW,
                           logdate=datetime.datetime(2013, 1, 1, 0, 0, 0),
                           logtext="process started")
        log_dm1.save()

        log_dd1 = bmodels.Log(changed_by=self.person,
                           process=self.process_dd,
                           progress=bconst.PROGRESS_APP_NEW,
                           logdate=datetime.datetime(2013, 1, 1, 12, 0, 0),
                           logtext="process started")
        log_dd1.save()

        log_dm2 = bmodels.Log(changed_by=self.person,
                           process=self.process_dm,
                           progress=bconst.PROGRESS_DONE,
                           logdate=datetime.datetime(2013, 1, 2, 0, 0, 0),
                           logtext="all ok")
        log_dm2.save()

        log_dd2 = bmodels.Log(changed_by=self.person,
                           process=self.process_dd,
                           progress=bconst.PROGRESS_ADV_RCVD,
                           logdate=datetime.datetime(2013, 1, 2, 12, 0, 0),
                           logtext="all ok")
        log_dd2.save()

        self.assertEquals(log_dm2.previous, log_dm1)
        self.assertEquals(log_dd2.previous, log_dd1)

        log_dd3 = bmodels.Log(changed_by=self.person,
                           process=self.process_dd,
                           progress=bconst.PROGRESS_APP_OK,
                           logdate=datetime.datetime(2013, 1, 3, 0, 0, 0),
                           logtext="advocacies are ok")
        log_dd3.save()

        self.assertEquals(log_dd3.previous, log_dd2)
        self.assertEquals(log_dd3.previous.previous, log_dd1)
