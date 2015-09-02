from base import BaseEndpointAPITestCase
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed


from conference import (
    ConferenceApi,
    CONF_GET_REQUEST,
    SESSION_BY_TYPE_GET_REQUEST,
    SESSION_BY_SPEAKER_GET_REQUEST

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

        print 'Successfully returned all sessions for a given conference'

    def testQuerySession(self):
        self.initDatabase()
        form = SessionQueryForms()
        form.filters = [
            SessionQueryForm(field='NAME', operator='EQ', value='Google App Engine')
        ]
        response = self.api.querySessions(form)
        r_sessions = response.items
        assert len(r_sessions) == 1, 'returned an invalid number of sessions'
        assert r_sessions[0].name == 'Google App Engine', 'returned an invalid session'

        print 'Successfully returned sessions for a given query'

    def testGetConferenceSessionsByType(self):
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

        print 'Successfully return all sessions of a specified type for a given conference'

    def testGetSessionsBySpeaker(self):
        self.initDatabase()

        container = SESSION_BY_SPEAKER_GET_REQUEST.combined_message_class(
            speaker='superman'
        )
        r = self.api.getSessionsBySpeaker(container)
        r_sessions = r.items
        assert len(r_sessions) == 1, 'returned an invalid number of sessions'
        assert r_sessions[0].speaker == 'superman', 'returned an invalid session'

        print 'Successfully return all sessions of a specified type for a given conference'
