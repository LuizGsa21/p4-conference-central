import unittest
import datetime
import os

from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from google.appengine.datastore import datastore_stub_util

from models import (
    Profile,
    Conference,
    Session,
)

from utils import getUserId


class BaseEndpointAPITestCase(unittest.TestCase):
    """ Base endpoint API unit tests. """

    def setUp(self):
        # create an instance of the Testbed class.
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()

        # Create a consistency policy that will simulate the High Replication consistency model.
        self.policy = datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1)
        self.testbed.init_datastore_v3_stub(
            consistency_policy=self.policy,
            # Set require_indexes to false to automatically add indexes to index.yaml
            # NOTE: root_path must also be set
            require_indexes=False,
            root_path=os.path.pardir,
        )
        # declare other service stubs
        self.testbed.init_memcache_stub()
        self.testbed.init_user_stub()
        self.testbed.init_taskqueue_stub()
        self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        # Clear ndb's in-context cache between tests.
        # This prevents data from leaking between tests.
        # Alternatively, you could disable caching by
        # using ndb.get_context().set_cache_policy(False)
        ndb.get_context().clear_cache()

    def tearDown(self):
        self.testbed.deactivate()

    def initDatabase(self):
        """ Adds database fixtures """
        _profiles = [
            {'displayName': 'Luiz', 'mainEmail': 'test1@test.com', 'teeShirtSize': 'NOT_SPECIFIED', 'conferenceKeysToAttend': []},
            {'displayName': 'Batman', 'mainEmail': 'test2@test.com', 'teeShirtSize': 'NOT_SPECIFIED', 'conferenceKeysToAttend': []},
            {'displayName': 'Goku', 'mainEmail': 'test3@test.com', 'teeShirtSize': 'NOT_SPECIFIED', 'conferenceKeysToAttend': []}
        ]
        # add profiles to database
        ndb.put_multi([Profile(key=ndb.Key(Profile, p['mainEmail']),**p) for p in _profiles])

        now = datetime.datetime.now()
        # 3 conferences with `test1@test.com`
        # 1 conference with `test2@test.com`
        _conferences = [
            {
                'name': 'room #1',
                'organizerUserId': 'test1@test.com',
                'topics': ['programming', 'web design', 'web performance'],
                'city': 'London',
                'startDate': now,
                'endDate': now + datetime.timedelta(days=5),
                'seatsAvailable': 100,
                'maxAttendees': 100,
                'sessions': [
                    {'name': 'PHP', 'speaker': 'superman', 'typeOfSession': 'educational',
                     'date': (now + datetime.timedelta(days=10)).date(),
                     'startTime': (now + datetime.timedelta(days=1)).time(), 'duration': 60},
                    {'name': 'Python', 'speaker': 'flash', 'typeOfSession': 'educational',
                     'date': (now + datetime.timedelta(days=10)).date(),
                     'startTime': (now + datetime.timedelta(days=1, hours=1)).time(), 'duration': 60}
                ]
            },
            {
                'name': 'room #2',
                'organizerUserId': 'test1@test.com',
                'topics': ['web performance'],
                'city': 'Baton Rouge',
                'startDate': now + datetime.timedelta(days=10),
                'endDate': now + datetime.timedelta(days=20),
                'seatsAvailable': 1,
                'maxAttendees': 1,
                'sessions': []
            },
            {
                'name': 'room #3',
                'organizerUserId': 'test1@test.com',
                'topics': ['programming', 'misc'],
                'startDate': now + datetime.timedelta(days=8),
                'endDate': now + datetime.timedelta(days=10),
                'seatsAvailable': 6,
                'maxAttendees': 6,
                'sessions': []
            },
            {
                'name': 'room #4',
                'organizerUserId': 'test2@test.com',
                'topics': ['misc'],
                'startDate': now + datetime.timedelta(days=10),
                'endDate': now + datetime.timedelta(days=20),
                'seatsAvailable': 6,
                'maxAttendees': 6,
                'sessions': [
                    {'name': 'Intro to Poker', 'speaker': 'joker', 'typeOfSession': 'fun',
                     'date': (now + datetime.timedelta(days=10)).date(),
                     'startTime': (now + datetime.timedelta(days=10)).time(), 'duration': 60},
                    {'name': 'Google App Engine', 'speaker': 'Bill Gates', 'typeOfSession': 'informative',
                     'date': (now + datetime.timedelta(days=10)).date(),
                     'startTime': (now + datetime.timedelta(days=10, hours=1)).time(), 'duration': 60}
                ]

            }
        ]
        # add conferences to database
        for data in _conferences:
            p_key = ndb.Key(Profile, data['organizerUserId'])
            c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
            data['key'] = ndb.Key(Conference, c_id, parent=p_key)
            # pop the sessions from `data` and add the conference to the database
            sessions = data.pop('sessions')
            conf = Conference(**data)
            conf.put()
            # Now that the conference has been added to the database, we can add the sessions that
            # were previously removed using `pop()`
            for session in sessions:
                c_id = Session.allocate_ids(size=1, parent=conf.key)[0]
                session['key'] = ndb.Key(Session, c_id, parent=conf.key)
                Session(**session).put()

    def login(self, email='test1@test.com', is_admin=False):
        """ Logs in user (using simulation). If no arguments are given, logs in using default user `test1@test.com` """
        self.testbed.setup_env(
            user_email=email,
            user_is_admin='1' if is_admin else '0',
            overwrite=True,
            # support oauth login using `endpoints.get_current_user()`
            ENDPOINTS_AUTH_EMAIL=email,
            ENDPOINTS_AUTH_DOMAIN='testing.com'
        )

    def logout(self):
        """ Logs out user (using simulation) """
        self.login('')

    def getUserId(self):
        """ Returns current user's id """
        user = users.get_current_user()
        if not user:
            raise ValueError("User must be logged in to retrieve user id")
        return getUserId(user)
