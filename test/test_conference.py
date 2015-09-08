import datetime
import pprint
import unittest
import runner
from endpoints import UnauthorizedException, ForbiddenException, BadRequestException, get_current_user
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
    MEMCACHE_ANNOUNCEMENTS_KEY,
    MEMCACHE_FEATURED_SPEAKER_KEY,
    CONF_POST_REQUEST,
    SESSION_FIELDS

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
    SessionQueryForms,
    ConflictException
)
import main
import webapp2


class ConferenceTestCase(BaseEndpointAPITestCase):
    """ Endpoint API unit tests. """

    def setUp(self):
        super(ConferenceTestCase, self).setUp()
        self.api = ConferenceApi()

    def tearDown(self):
        super(ConferenceTestCase, self).tearDown()

    def testLogin(self):
        """TEST: User login simulation"""

        assert not users.get_current_user()
        self.login()
        assert users.get_current_user().email() == 'test1@test.com'
        self.login(is_admin=True)
        assert users.is_current_user_admin()
        self.logout()
        assert not users.get_current_user()

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

    def testQueryConferences(self):
        self.initDatabase()
        form = ConferenceQueryForms()
        # verify fixture contains conference
        assert Conference.query(Conference.city == 'London').count() == 1, \
            "This shouldn't fail. Maybe someone messed with database fixture"

        form.filters = [
            ConferenceQueryForm(field='CITY', operator='EQ', value='London')
        ]
        r = self.api.queryConferences(form)
        conferences = r.items
        assert len(conferences) == 1, 'Returned an invalid number of conferences'
        assert conferences[0].city == 'London', 'Returned an invalid conference'

        # check that all conferences are returned when no filter is given
        form.filters = []
        r = self.api.queryConferences(form)
        assert len(r.items) == Conference.query().count(), 'Returned an invalid number of conferences'

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
            'date': '2015-08-6',
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
            websafeSessionKey=swsk
        )
        self.login()  # login as default user
        r = self.api.addSessionToWishlist(container)
        profile = ndb.Key(Profile, self.getUserId()).get()
        assert r.data and session.key in profile.wishList, "Failed to add session to user's wish list"

    def testRemoveSessionFromWishlist(self):
        """ TEST: Remove session from user's wishlist """
        self.initDatabase()

        self.login()  # login as default user
        # verify database fixture
        prof = ndb.Key(Profile, self.getUserId()).get()
        session = Session.query(Session.name == 'Intro to Poker').get()
        assert session and len(prof.wishList) == 0, \
            "This shouldn't fail. Maybe someone messed with database fixture"
        # manually add a session to user's wishlist
        prof.wishList.append(session.key)
        prof.put()

        # build request
        container = SESSION_WISHLIST_POST_REQUEST.combined_message_class(
            websafeSessionKey=session.key.urlsafe()
        )
        # remove session from users wishlist
        r = self.api.removeSessionFromWishlist(container)
        # re-fetch profile then verify session was removed
        prof = prof.key.get()
        assert r.data and session.key not in prof.wishList, "Failed to remove session from user's wish list"

    def testGetSessionsInWishlist(self):
        """ TEST: Get sessions in user's wish list """
        self.initDatabase()

        self.login()  # login as default user
        profile = ndb.Key(Profile, self.getUserId()).get()
        pSessionKeys = profile.wishList

        assert len(pSessionKeys) == 0, "This shouldn't fail. Maybe someone messed with database fixture"

        r = self.api.getSessionsInWishlist(message_types.VoidMessage())
        assert len(r.items) == 0, "Returned an invalid number of sessions"

        # add a session to user's wish list
        session = Session.query().get()
        pSessionKeys.append(session.key)
        profile.put()

        # check that user's wishlist was updated
        r = self.api.getSessionsInWishlist(message_types.VoidMessage())
        assert len(r.items) == 1, "Returned an invalid number of sessions"
        assert r.items[0].websafeKey == session.key.urlsafe(), "Returned an invalid session"

    def testGetProfile(self):
        """ TEST: Get user's profile  """
        self.initDatabase()
        try:
            # only logged in users have a profile
            self.api.getProfile(message_types.VoidMessage())
            assert False, 'UnauthorizedException should of been thrown'
        except UnauthorizedException:
            pass

        # login and retrieve the profile
        self.login()
        prof = ndb.Key(Profile, self.getUserId()).get()
        # Add conferences to conferenceKeysToAttend so we can verify the returned keys are web safe
        keys = Conference.query().fetch(keys_only=True)
        prof.conferenceKeysToAttend = keys
        prof.put()

        r = self.api.getProfile(message_types.VoidMessage())
        assert r.mainEmail == 'test1@test.com', 'Returned an invalid user profile'
        assert len(r.conferenceKeysToAttend) > 0, 'Returned an invalid number of conference keys'
        # verify that all keys are urlsafe
        websafeKeys = [key.urlsafe() for key in keys]
        for websafeKey in r.conferenceKeysToAttend:
            assert websafeKey in websafeKeys, 'Returned an invalid key'

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
        # first test using an invalid conference
        conf = {
            'name': 'New Conference',
            'topics': ['misc'],
            'city': 'Baton Rouge',
            'startDate': str(now + datetime.timedelta(days=5)),
            'endDate': str(now),
            'maxAttendees': 100
        }

        # Attempt to add a conference where startDate > endDate. (this should fail)
        try:
            r = self.api.createConference(ConferenceForm(**conf))
            assert False, 'BadRequestException should of been thrown...'
        except BadRequestException:
            pass
        # make sure conference wasn't added
        assert Conference.query(Conference.name == 'New Conference').count() == 0, \
            'A conference with startDate > endDate should not be added to the database'

        # add a conference using valid startDate and endDate
        conf['startDate'] = str(now)
        conf['endDate'] = str(now + datetime.timedelta(days=5))
        r = self.api.createConference(ConferenceForm(**conf))
        assert Conference.query(Conference.name == 'New Conference').count() == 1, \
            'Failed to add conference to datastore'
        assert r.name == 'New Conference', 'Returned an invalid conference'

    def testUpdateConference(self):
        """ TEST: Update conference w/provided fields & return w/updated info """
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

    def testGetConference(self):
        """ TEST: Return requested conference (by websafeConferenceKey) """
        self.initDatabase()

        self.login()
        conf = Conference.query(ancestor=ndb.Key(Profile, self.getUserId())).get()

        container = CONF_GET_REQUEST.combined_message_class(
            websafeConferenceKey=conf.key.urlsafe(),
        )

        r = self.api.getConference(container)
        assert r.websafeKey == conf.key.urlsafe(), 'Returned an invalid conference'

    def testGetConferencesCreated(self):
        """ TEST: Return conferences created by user """
        self.initDatabase()

        self.login()
        conferences = Conference.query(ancestor=ndb.Key(Profile, self.getUserId())).fetch()
        assert len(conferences) == 3, "This shouldn't fail. Maybe someone messed with database fixture"

        r = self.api.getConferencesCreated(message_types.VoidMessage())

        assert len(r.items) == len(conferences), 'Returned an invalid number of conferences'
        # verify that every key matches the returned set
        keys = [c.key.urlsafe() for c in conferences]
        for conf in r.items:
            assert conf.websafeKey in keys, 'Returned an invalid conference key (websafe)'

    def testGetConferencesToAttend(self):
        """ TEST: Get list of conferences that user has registered for """
        self.initDatabase()

        self.login()
        prof = ndb.Key(Profile, self.getUserId()).get()
        count = len(prof.conferenceKeysToAttend)
        assert count == 0, "This shouldn't fail. Maybe someone messed with database fixture"

        r = self.api.getConferencesToAttend(message_types.VoidMessage())
        assert len(r.items) == count, 'Returned an invalid number of conferences'

        # register to a conference and test again
        key = Conference.query().get().key
        prof.conferenceKeysToAttend.append(key)
        prof.put()

        r = self.api.getConferencesToAttend(message_types.VoidMessage())
        assert len(r.items) == count + 1, 'Returned an invalid number of conferences'
        assert r.items[0].websafeKey == key.urlsafe(), 'Returned an invalid websafeKey'

    def testRegisterForConference(self):
        """ TEST: Register user for selected conference."""
        self.initDatabase()

        # verify database fixture
        self.login()
        prof = ndb.Key(Profile, self.getUserId()).get()
        conf = Conference.query(Conference.name == 'room #2').get()
        assert conf and conf.seatsAvailable == 1 and len(prof.conferenceKeysToAttend) == 0, \
            "This shouldn't fail. Maybe someone messed with database fixture"

        container = CONF_GET_REQUEST.combined_message_class(
            websafeConferenceKey=conf.key.urlsafe(),
        )

        # register to conference
        r = self.api.registerForConference(container)

        # re-fetch profile and conference, then check if user was properly registered
        prof = prof.key.get()
        conf = conf.key.get()
        assert r.data, 'Returned an invalid response'
        assert len(prof.conferenceKeysToAttend) == 1, "Failed to add conference to user's conferenceKeysToAttend"
        assert conf.seatsAvailable == 0, 'Failed to decrement available seats'

        # Verify users cant re-register to conferences that are already in user's conferenceKeysToAttend.
        container = CONF_GET_REQUEST.combined_message_class(
            websafeConferenceKey=conf.key.urlsafe(),
        )
        try:
            r = self.api.registerForConference(container)
            assert False, 'ConflictException should of been thrown...'
        except ConflictException:
            pass
        # re-fetch profile and check that the user wasn't re-registered
        prof = prof.key.get()
        assert len(prof.conferenceKeysToAttend) == 1, "User's can't registered to the same conference"

        # Login as a different user and attempt to register a conference with zero seats available
        self.login(email='test2@test.com')
        prof = ndb.Key(Profile, self.getUserId()).get()
        assert len(prof.conferenceKeysToAttend) == 0, "This shouldn't fail. Maybe someone messed with database fixture"
        try:
            r = self.api.registerForConference(container)
            assert False, 'ConflictException should of been thrown...'
        except ConflictException:
            pass
        # re-fetch profile and conference
        prof = prof.key.get()
        conf = conf.key.get()
        assert len(prof.conferenceKeysToAttend) == 0, "User's can't register to a conference with zero seats available."
        assert conf.seatsAvailable == 0, "seatsAvailable shouldn't have changed since user never registered..."

    def testUnregisterFromConference(self):
        """ TEST: Unregister user for selected conference."""
        self.initDatabase()

        # verify database fixture
        self.login()
        prof = ndb.Key(Profile, self.getUserId()).get()
        conf = Conference.query(Conference.name == 'room #2').get()
        assert conf and conf.seatsAvailable == 1 and len(prof.conferenceKeysToAttend) == 0, \
            "This shouldn't fail. Maybe someone messed with database fixture"

        prof.conferenceKeysToAttend.append(conf.key)
        prof.put()

        container = CONF_GET_REQUEST.combined_message_class(
            websafeConferenceKey=conf.key.urlsafe(),
        )

        # unregister conference
        r = self.api.unregisterFromConference(container)

        # re-fetch profile and conference, then check if user was properly unregistered
        prof = prof.key.get()
        conf = conf.key.get()
        assert r.data, 'Returned an invalid response'
        assert len(prof.conferenceKeysToAttend) == 0, "Failed to remove conference from user's conferenceKeysToAttend"
        assert conf.seatsAvailable == 2, 'Failed to increment available seats'

    def testSaveProfile(self):
        self.initDatabase()
        self.login()

        prof = ndb.Key(Profile, self.getUserId()).get()
        assert TeeShirtSize(prof.teeShirtSize) == TeeShirtSize.NOT_SPECIFIED, \
            "This shouldn't fail. Maybe someone messed with database fixture"

        form = ProfileMiniForm(
            displayName='testSaveProfile',
            teeShirtSize=TeeShirtSize.XL_M
        )
        r = self.api.saveProfile(form)

        # validate response
        assert r.displayName == 'testSaveProfile' and \
               TeeShirtSize(r.teeShirtSize) == TeeShirtSize.XL_M, 'Returned invalid response'

        # re-fetch profile and validate values in datastore
        prof = prof.key.get()
        assert prof.displayName == 'testSaveProfile' and \
               TeeShirtSize(prof.teeShirtSize) == TeeShirtSize.XL_M, 'Failed to save profile in datastore'

    def testGetAnnouncement(self):
        """ TEST: Return Announcement from memcache."""
        self.initDatabase()

        # Verify database fixture
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch()
        assert len(confs) == 1 and confs[0].name == 'room #2' and None == memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY), \
            "This shouldn't fail. Maybe someone messed with database fixture"

        # Since an announcement was never set `getAnnouncement()` should return an empty StringMessage
        response = self.api.getAnnouncement(message_types.VoidMessage())
        assert response.data == '', 'Expected an empty string since no announcement was set'

        # set announcement
        request = webapp2.Request.blank('/crons/set_announcement')
        response = request.get_response(main.app)
        # validate http status
        assert response.status_int == 204, 'Invalid response expected 204 but got %d' % response.status_int

        # Verify room #2 is listed in the announcement
        response = self.api.getAnnouncement(message_types.VoidMessage())
        assert 'room #2' in response.data, 'Announcement is missing a conference'

    def testConferenceEmailConfirmation(self):
        """ TEST: Send email to organizer confirming creation of Conference """
        self.mail_stub = self.testbed.get_stub(testbed.MAIL_SERVICE_NAME)
        self.initDatabase()
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
        tasks = self.taskqueue_stub.get_filtered_tasks()
        assert len(tasks) != 0, 'No tasks were added to queue'

        # Run the task
        request = webapp2.Request.blank(tasks[0].url + '?' + tasks[0].payload)
        request.method = tasks[0].method
        response = request.get_response(main.app)
        assert response.status_int == 200, 'Invalid response expected 200 but got %d' % response.status_int
        # verify email was sent
        prof = ndb.Key(Profile, self.getUserId()).get()
        messages = self.mail_stub.get_sent_messages(to=prof.mainEmail)
        assert len(messages) == 1, 'Failed to send confirmation email'

    def testGetFeaturedSpeaker(self):
        """ TEST: Returns the featured speakers and their registered sessions from memcache. """
        self.initDatabase()
        # Verify database fixture
        speakers = {}
        for session in Session.query():
            assert speakers.get(session.speaker, None) is None, \
                "This shouldn't fail. Maybe someone messed with database fixture"
            speakers[session.name] = session.key
        assert None == memcache.get(MEMCACHE_FEATURED_SPEAKER_KEY), \
            "This shouldn't fail. Maybe someone messed with database fixture"

        # Since a featured speaker was never set `getFeaturedSpeaker()` should return an empty StringMessage
        response = self.api.getFeaturedSpeaker(message_types.VoidMessage())
        assert response.data == '', 'Expected an empty string since no announcement was set'

        # Login and grab a conference owned by the current user
        self.login()
        conf = Conference.query(ancestor=ndb.Key(Profile, self.getUserId())).get()

        # Add 2 sessions with the same speaker using `createSession` endpoint
        sessions = [
            {'name': 'PHP', 'speaker': 'hitler', 'typeOfSession': 'educational',
             'date': str(conf.startDate), 'startTime': '08:00', 'duration': 60},
            {'name': 'Python', 'speaker': 'hitler', 'typeOfSession': 'educational',
             'date': str(conf.startDate), 'startTime': '12:30', 'duration': 60},
        ]
        initial_count = Session.query().count()
        for session in sessions:
            container = SESSION_POST_REQUEST.combined_message_class(
                websafeConferenceKey=conf.key.urlsafe(),
                **session
            )
            self.api.createSession(container)
        count = Session.query().count()
        assert count == initial_count + 2, 'Failed to add sessions to conference...'

        tasks = self.taskqueue_stub.get_filtered_tasks()
        assert len(tasks) == 2, 'No tasks were added to queue'
        for task in tasks:
            request = webapp2.Request.blank(task.url + '?' + task.payload)
            request.method = task.method
            response = request.get_response(main.app)
            # validate http status
            assert response.status_int == 204, 'Invalid response expected 204 but got %d' % response.status_int

        # Verify featured speaker has been updated
        response = self.api.getFeaturedSpeaker(message_types.VoidMessage())
        data = response.data
        memData = memcache.get(MEMCACHE_FEATURED_SPEAKER_KEY)
        assert 'hitler' in memData and \
               'PHP' in memData and \
               'Python' in memData, 'Failed to add featured speaker to memcache'
        assert 'hitler' in data and \
               'PHP' in data and \
               'Python' in data, 'Returned an invalid featured speaker'

    def testTask3QueryProblem(self):
        """ TEST: Solve task 3 "the query related problem"  """
        # Solve the following query related problem:
        #   Let's say that you don't like workshops and you don't like sessions after 7 pm.
        #   How would you handle a query for all non-workshop sessions before 7 pm?
        #   What is the problem for implementing this query?
        #       - A query can have no more than one not-equal filter, and a query
        #         that has one cannot have any other inequality filters
        #   What ways to solve it did you think of?
        #       - One way to solve this problem is to let datastore handle the first inequality.
        #         Any additional inequalities should be implemented in python.
        #         As a solution to this problem both `queryConferences()` and `querySessions()` endpoints
        #         support multi inequality queries

        # init and verify database fixture
        self.initDatabase()
        workshopSessions = Session.query(Session.typeOfSession == 'workshop').fetch()
        assert len(workshopSessions) == 2, "This shouldn't fail. Maybe someone messed with database fixture"
        # manually get the solution so we can compare it against the response
        validSessions = []
        for session in Session.query(Session.startTime < datetime.datetime.strptime('19:00', '%H:%M').time()):
            if session not in workshopSessions:
                validSessions.append(session)
        assert len(validSessions) > 0, "This shouldn't fail. Maybe someone messed with database fixture"

        # create a query using `sessionQueryForms()` and add 2 inequalities
        form = SessionQueryForms()
        form.filters = [
            SessionQueryForm(field='TYPE_OF_SESSION', operator='NE', value='workshop'),
            SessionQueryForm(field='START_TIME', operator='LT', value='19:00')
        ]
        response = self.api.querySessions(form)
        # evaluate the response
        sessions = response.items
        assert len(sessions) == len(validSessions), 'Returned an invalid number of sessions'
        validKeys = [v.key.urlsafe() for v in validSessions]
        for s in sessions:
            assert s.websafeKey in validKeys, 'Returned an invalid session'

        # ----- Attempt a 9 inequality query -----------
        # Create a unique session
        uniqueSession = {'name': 'BONUS ROUND', 'speaker': 'BONUS ROUND', 'typeOfSession': 'BONUS ROUND',
                         'date': datetime.datetime.strptime('2015-12-12', '%Y-%m-%d'),
                         'startTime': datetime.time(hour=3), 'duration': 200}
        # verify this session is unique
        for key, value in uniqueSession.iteritems():
            count = Session.query(Session._properties[key] == value).count()
            assert count == 0, 'Ahhh failed to setup bonus round, maybe someone messed with the database fixture'

        # add unique session to database
        conf = Conference.query().get()
        c_id = Session.allocate_ids(size=1, parent=conf.key)[0]
        uniqueSession['key'] = ndb.Key(Session, c_id, parent=conf.key)
        Session(**uniqueSession).put()

        # create a form with multiple inequalities
        inequalities = [
            {'field': 'START_TIME', 'operator': 'GTEQ', 'value': '02:30'},
            {'field': 'DATE', 'operator': 'LTEQ', 'value': '2015-12-12'},
            {'field': 'DURATION', 'operator': 'GT', 'value': '30'}
        ]
        form = SessionQueryForms()
        for inequality in inequalities:
            form.filters.append(SessionQueryForm(**inequality))

        # grab all sessions (EXCLUDING unique session)
        sessions = Session.query(Session.key != uniqueSession['key']).fetch()
        assert len(sessions) == 6
        # add additional inequalities using the session names
        for session in sessions:
            form.filters.append(SessionQueryForm(
                field='NAME',
                operator='NE',
                value=session.name
            ))
        # 9 inequality filters
        assert len(form.filters) == 9, 'Ahhh failed to setup bonus round, expected 9 inequality filters'
        # From the way the test was setup, `START_TIME` will be the only
        # property filtered by datastore. Everything else will be filtered using python.

        # make the query using the 9 inequality filters to retrieve the `uniqueSession`
        response = self.api.querySessions(form)
        assert len(response.items) == 1
        assert response.items[0].name == 'BONUS ROUND'




if __name__ == '__main__':
    unittest.main()
