"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from model_mommy import mommy as factory

from backend.models import Person, Process
from backend import const

class PersonPageTestCase(TestCase):
    
    def setUp(self):
        pass

    def tearDown(self):
        pass
        
    def test_person_listing(self):
        """
        Tests that a person is listed on the public persons page
        """
        
        # Create a test person and process
        person = factory.make_one(Person, cn='Test', sn='User', email='testuser@debian.org')
        process = factory.make_one(Process, person=person, applying_as=const.ALL_STATUS_BYTAG['mm'], applying_for=const.ALL_STATUS_BYTAG['dm'])
        
        # Check that the new person is listed on the page
        response = self.client.get('/public/people')
        self.assertContains(response, 'Test User', 1)
        
        self.assertContains(response, 'testuser@debian.org', 2)
