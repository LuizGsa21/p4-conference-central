import datetime
from endpoints import UnauthorizedException, ForbiddenException, get_current_user
from base import BaseEndpointAPITestCase
from utils import formToDict
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from protorpc import message_types

from conference import (
    ConferenceApi,
    CONF_GET_REQUEST,
    SESSION_POST_REQUEST,
    SESSION_BY_TYPE_GET_REQUEST,
    SESSION_BY_SPEAKER_GET_REQUEST,
    SESSION_WISHLIST_POST_REQUEST,
    CONF_POST_REQUEST

)

from models import (
    Profile,
    ProfileMiniForm,
    ProfileForm,
    StringMessage,
    BooleanMessage,
    Conference,
    ConferenceForm,
    ConferenceForms,
    ConferenceQueryForm,
    ConferenceQueryForms,
    TeeShirtSize,
    Session,
    SessionForm,
    SessionForms,
    SessionQueryForm,
    SessionQueryForms
)

class ConferenceTestCase(BaseEndpointAPITestCase):
    """ Endpoint API unit tests. """

    def setUp(self):
        super(ConferenceTestCase, self).setUp()
        self.api = ConferenceApi()

    def tearDown(self):
        super(ConferenceTestCase, self).tearDown()

    def testGetConferenceSessions(self):
        """ TEST: Return all sessions for a given conference"""
        self.initDatabase()

        conf = Conference.query(Conference.name == 'room #1').fetch(1)[0]
        container = CONF_GET_REQUEST.combined_message_class(websafeConferenceKey=conf.key.urlsafe())
        # manually fetch conference sessions and compare it against response
        sessions = {str(s.key.urlsafe()): s for s in conf.sessions.fetch()}

        r = self.api.getConferenceSessions(container)
        r_sessions = r.items

        assert len(r_sessions) == len(sessions), 'returned an invalid number of sessions'
        for r_session in r_sessions:
            assert sessions[r_session.websafeKey], 'returned an invalid session websafeKey'

    def testQuerySession(self):
        """ TEST: Return sessions for a given query"""
        self.initDatabase()
        form = SessionQueryForms()
        form.filters = [
            SessionQueryForm(field='NAME', operator='EQ', value='Google App Engine')
        ]
        response = self.api.querySessions(form)
        r_sessions = response.items
        assert len(r_sessions) == 1, 'returned an invalid number of sessions'
        assert r_sessions[0].name == 'Google App Engine', 'returned an invalid session'

    def testGetConferenceSessionsByType(self):
        """ TEST: Return all sessions of a specified type for a given conference"""
        self.initDatabase()

        conf = Conference.query(Conference.name == 'room #4').fetch(1)[0]
        container = SESSION_BY_TYPE_GET_REQUEST.combined_message_class(
            typeOfSession='fun',
            websafeConferenceKey=conf.key.urlsafe()
        )
        r = self.api.getConferenceSessionsByType(container)
        r_sessions = r.items
        assert len(r_sessions) == 1, 'returned an invalid number of sessions'
        assert r_sessions[0].typeOfSession == 'fun', 'returned an invalid session'

    def testGetSessionsBySpeaker(self):
        """ TEST: Return all sessions by a particular speaker"""
        self.initDatabase()

        container = SESSION_BY_SPEAKER_GET_REQUEST.combined_message_class(
            speaker='superman'
        )
        r = self.api.getSessionsBySpeaker(container)
        r_sessions = r.items
        assert len(r_sessions) == 1, 'returned an invalid number of sessions'
        assert r_sessions[0].speaker == 'superman', 'returned an invalid session'

    def testCreateSession(self):
        """ TEST: Create a session open to the organizer of the conference"""
        self.initDatabase()
        conf = Conference.query(Conference.name == 'room #1').fetch(1)[0]

        # fill out session form fields in SESSION_POST_REQUEST
        sessionFields = {
            'name': 'Computer programming',
            'speaker': 'Donald Knuth',
            'typeOfSession': 'educational',
            'date': '2015-09-10',
            'startTime': '11:00',
            'duration': 100
        }
        container = SESSION_POST_REQUEST.combined_message_class(
            websafeConferenceKey=conf.key.urlsafe(),
            **sessionFields
        )

        # get current session count
        initialCount = conf.sessions.count()

        # Attempt to add a session without being logged in
        try:
            r = self.api.createSession(container)
            assert False, 'UnauthorizedException should of been thrown...'
        except UnauthorizedException:
            pass
        # make sure a session wasn't added
        count = conf.sessions.count()
        assert count == initialCount, 'Only the organizer of the conference may create sessions'

        # Attempt to add a session with a logged in but unauthorized user.
        self.login(email='test2@test.com')
        try:
            r = self.api.createSession(container)
            assert False, 'ForbiddenException should of been thrown...'
        except ForbiddenException:
            pass
        # make sure a session wasn't added
        count = conf.sessions.count()
        assert count == initialCount, 'Only the organizer of the conference may create sessions'

        # Finally, add session using the authorized user
        self.login(email=conf.organizerUserId)
        r = self.api.createSession(container)
        count = conf.sessions.count()
        assert count == initialCount + 1, 'Failed to add session to conference'

    def testAddSessionToWishlist(self):
        """ TEST: Add session to the user's wishlist """
        self.initDatabase()

        session = Session.query(Session.name == 'Intro to Poker').get()
        swsk = session.key.urlsafe()
        container = SESSION_WISHLIST_POST_REQUEST.combined_message_class(
            sessionKey=swsk
        )
        self.login()  # login as default user
        r = self.api.addSessionToWishlist(container)
        profile = ndb.Key(Profile, self.getUserId()).get()
        assert r.data and swsk in profile.sessionKeysInWishList, "Failed to session to user's wish list"

    def testGetSessionsInWishlist(self):
        """ TEST: Get sessions in user's wish list """
        self.initDatabase()

        self.login()  # login as default user
        profile = ndb.Key(Profile, self.getUserId()).get()
        pSessionKeys = profile.sessionKeysInWishList

        assert len(pSessionKeys) == 0, "This shouldn't fail. Maybe someone messed with database fixture"

        r = self.api.getSessionsInWishlist(message_types.VoidMessage())
        assert len(r.items) == 0, "Returned an invalid number of sessions"

        # add a session to user's wish list
        websafeKey = Session.query().get().key.urlsafe()
        pSessionKeys.append(websafeKey)
        profile.put()

        # check that user's wishlist was updated
        r = self.api.getSessionsInWishlist(message_types.VoidMessage())
        assert len(r.items) == 1, "Returned an invalid number of sessions"
        assert r.items[0].websafeKey == websafeKey, "Returned an invalid session"

    def testGetProfile(self):
        """ TEST: Get user's profile  """
        try:
            # only logged in users have a profile
            self.api.getProfile(message_types.VoidMessage())
            assert False, 'UnauthorizedException should of been thrown'
        except UnauthorizedException:
            pass

        # login and retrieve the profile
        self.login()
        r = self.api.getProfile(message_types.VoidMessage())
        assert r.mainEmail == 'test1@test.com', 'Returned an invalid user profile'

    def testCreateConference(self):
        """ TEST: Create new conference."""
        self.initDatabase()
        try:
            # only logged in users may create conferences
            self.api.createConference(ConferenceForm())
            assert False, 'UnauthorizedException should of been thrown'
        except UnauthorizedException:
            pass

        # login and create a conference
        self.login()

        now = datetime.datetime.now()
        r = self.api.createConference(ConferenceForm(
            name='New Conference',
            organizerUserId=self.getUserId(),
            topics=['misc'],
            city='Baton Rouge',
            startDate=str(now),
            endDate=str(now + datetime.timedelta(days=5)),
            maxAttendees=100
        ))
        assert Conference.query(Conference.name == 'New Conference').count() == 1, \
            'Failed to add conference to datastore'
        assert r.name == 'New Conference', 'Returned an invalid conference'

    def testUpdateConference(self):
        self.initDatabase()

        self.login()
        conf = Conference.query(ancestor=ndb.Key(Profile, self.getUserId())).get()
        key = conf.key
        assert conf.name != 'testUpdateConference', "This shouldn't fail. Maybe someone messed with database fixture"

        # converting `conf` to a dictionary doesn't format the values properly to send request.
        # so first convert it to a form, then to a dictionary
        data = formToDict(conf.toForm())
        data['name'] = 'testUpdateConference'
        container = CONF_POST_REQUEST.combined_message_class(
            websafeConferenceKey=conf.key.urlsafe(),
            **data
        )

        r = self.api.updateConference(container)
        assert r.name == 'testUpdateConference', 'Returned an invalid conference'
        assert r.name == key.get().name, 'Failed to update datastore'
