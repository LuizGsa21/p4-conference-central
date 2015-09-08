#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

from datetime import datetime, time, date

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import TeeShirtSize
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionQueryForms

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId, formToDict, expression_closure

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
MEMCACHE_FEATURED_SPEAKER_KEY = 'FEATURED_SPEAKERS'
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"]
}

OPERATORS = {
    'EQ': '=',
    'GT': '>',
    'GTEQ': '>=',
    'LT': '<',
    'LTEQ': '<=',
    'NE': '!='
}

CONFERENCE_FIELDS = {
    'CITY': 'city',
    'TOPIC': 'topics',
    'MONTH': 'month',
    'MAX_ATTENDEES': 'maxAttendees'
}

SESSION_FIELDS = {
    'NAME': 'name',
    'DURATION': 'duration',
    'TYPE_OF_SESSION': 'typeOfSession',
    'DATE': 'date',
    'START_TIME': 'startTime',
    'SPEAKER': 'speaker'
}

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1, required=True)
)

SESSION_BY_TYPE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1, required=True),
    typeOfSession=messages.StringField(2, required=True)
)

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1, required=True)
)

SESSION_BY_SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker=messages.StringField(1, required=True),
)

SESSION_WISHLIST_POST_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1, required=True)
)
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference',
               version='v1',
               audiences=[ANDROID_AUDIENCE],
               allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID],
               scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

    # - - - Conference objects - - - - - - - - - - - - - - - - -
    def _createConferenceObject(self, conferenceForm):
        """Create conference object, returns ConferenceForm."""

        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        data = formToDict(conferenceForm, exclude=('websafeKey', 'organizerDisplayName'))
        # add default values for those missing
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]

        # add organizerUserId before checking the required fields
        data['organizerUserId'] = user_id = getUserId(user)

        # check required fields
        for key in Conference.required_fields_schema:
            if not data[key]:
                raise endpoints.BadRequestException("Conference '%s' field required" % key)

        # convert dates from strings to Date objects; set month based on start_date
        try:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise endpoints.BadRequestException("Invalid date format. Please use 'YYYY-MM-DD'")

        if data['startDate'] > data['endDate']:
            raise endpoints.BadRequestException("start date must be before end date")
        data['month'] = data['startDate'].month

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]

        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        conf = Conference(**data)
        conf.put()
        taskqueue.add(
            params={'email': user.email(), 'conferenceInfo': repr(conferenceForm)},
            url='/tasks/send_confirmation_email'
        )
        return conf.toForm()

    @endpoints.method(ConferenceForm,
                      ConferenceForm,
                      path='conference',
                      http_method='POST',
                      name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException('No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return conf.toForm(prof.displayName)

    @endpoints.method(CONF_POST_REQUEST,
                      ConferenceForm,
                      path='conference/{websafeConferenceKey}',
                      http_method='PUT',
                      name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)

    @endpoints.method(CONF_GET_REQUEST,
                      ConferenceForm,
                      path='conference/{websafeConferenceKey}',
                      http_method='GET',
                      name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException('No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        return conf.toForm(prof.displayName)

    @endpoints.method(message_types.VoidMessage,
                      ConferenceForms,
                      path='getConferencesCreated',
                      http_method='POST',
                      name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[conf.toForm(prof.displayName) for conf in confs])

    def _buildQuery(self, model_class, filters, field_mapping, order_by=None):
        """Returns a formatted query from the submitted filters.
           If the query contains multiple inequalities, returns the filtered set.
            Note:
                Only the first inequality is handled by the datastore,
                any additional inequalities will be filtered using python.

        :param model_class: The model class used when building the query. `Model.query()`
        :type model_class: ndb.Model

        :param filters: a list of QueryForms
        :type filters: list

        :param field_mapping:
            A dictionary mapping `filter.field` to `model.property`.
            Look at `CONFERENCE_FIELDS` or `SESSION_FIELDS` for example.
        :type field_mapping: dict

        :param order_by:
            A list of names representing the model property to order by.
            If an inequality exists, the first inequality will have priority
            against other fields.
        :type order_by: list
        """
        q = model_class.query()
        inequality_filters, filters = self._formatFilters(filters, field_mapping)

        if order_by:
            # If an inequality exists, we must sort it first.
            if inequality_filters:
                # get the first inequality. (The inequality that is handled by datastore)
                inequality_in_query = inequality_filters[0]['field']

                q = q.order(ndb.GenericProperty(inequality_in_query))

                # If the same property is in `order_by`, remove it so we don't reapply it
                if inequality_in_query in order_by:
                    order_by.remove(inequality_in_query)

            # add any additional orders
            for key in order_by:
                q = q.order(getattr(model_class, key))

        for filtr in filters:
            # when building a query using filterNode, `modelProperty._to_base_type` is not called on the value argument.
            # This leads to problems when dealing with DateProperty and TimeProperty.
            # So when parsing the filter tell it to convert to base type
            self._parseFilter(model_class, filtr, to_base_type=True)
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr['value'])
            q = q.filter(formatted_query)

        # return the query if there are no additional inequalities
        if len(inequality_filters) <= 1:
            return q
        # Any additional inequalities must be implemented with Python.

        # Make a asynchronous query so we can create our closures while waiting for the request.
        rows = q.fetch_async()
        # remove the inequality handled by datastore
        inequality_filters.pop(0)
        # For each inequality we will create a closure so we can quickly
        # test the condition when looping through the returned result.
        filters = []
        for filtr in inequality_filters:
            # parse the filter. we don't need to convert to base type.
            self._parseFilter(model_class, filtr)
            # add the returned function to `filters`
            filters.append(expression_closure(**filtr))
        filtered_rows = []
        for row in rows.get_result():
            is_valid = True  # assume this row passes all filters
            for filtr in filters:
                # If one filter returns false, mark this row as invalid and break out of the loop
                if not filtr(row):
                    is_valid = False
                    break
            if is_valid:
                filtered_rows.append(row)
        # return the filtered set
        return filtered_rows

    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key=p_key,
                displayName=user.nickname(),
                mainEmail=user.email(),
                teeShirtSize=str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile  # return Profile

    # - - - Profile objects - - - - - - - - - - - - - - - - - - -

    @endpoints.method(ConferenceQueryForms,
                      ConferenceForms,
                      path='queryConferences',
                      http_method='POST',
                      name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""

        # use `CONFERENCE_FIELDS` to construct query.
        conferences = self._buildQuery(Conference, request.filters, CONFERENCE_FIELDS, order_by=['name'])

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            if profile:
                names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(items=[conf.toForm(names.get(conf.organizerUserId, '')) for conf in conferences])

    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        # if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        # else:
                        #    setattr(prof, field, val)
                        prof.put()

        # return ProfileForm
        return prof.toForm()

    @endpoints.method(message_types.VoidMessage,
                      ProfileForm,
                      path='profile',
                      http_method='GET',
                      name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()

    @endpoints.method(ProfileMiniForm,
                      ProfileForm,
                      path='profile',
                      http_method='POST',
                      name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)

    # - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement

    @endpoints.method(message_types.VoidMessage,
                      StringMessage,
                      path='conference/announcement/get',
                      http_method='GET',
                      name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")

    # - - - Registration - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(message_types.VoidMessage,
                      ConferenceForms,
                      path='conferences/attending',
                      http_method='GET',
                      name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser()  # get user Profile
        conferences = ndb.get_multi(prof.conferenceKeysToAttend)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences if conf]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[conf.toForm(names.get(conf.organizerUserId, '')) for conf in conferences])

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        prof = self._getProfileFromUser()  # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        key = ndb.Key(urlsafe=request.websafeConferenceKey)
        conf = key.get()
        if not conf:
            raise endpoints.NotFoundException('No conference found with key: %s' % request.websafeConferenceKey)

        # register
        if reg:
            # check if user already registered otherwise add
            if conf.key in prof.conferenceKeysToAttend:
                raise ConflictException("You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException("There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(key)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if key in prof.conferenceKeysToAttend:
                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(key)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)

    @endpoints.method(CONF_GET_REQUEST,
                      BooleanMessage,
                      path='conference/{websafeConferenceKey}',
                      http_method='POST',
                      name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)

    @endpoints.method(CONF_GET_REQUEST,
                      BooleanMessage,
                      path='conference/{websafeConferenceKey}',
                      http_method='DELETE',
                      name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)

        # - - - Conference Session - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(CONF_GET_REQUEST, SessionForms,
                      path='conference/{websafeConferenceKey}/sessions',
                      http_method='GET',
                      name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Given a conference, return all sessions"""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException('No conference found with key: %s' % request.websafeConferenceKey)

        # Return a set of SessionForm objects per session
        return SessionForms(items=[session.toForm() for session in conf.sessions])

    @endpoints.method(SESSION_BY_TYPE_GET_REQUEST,
                      SessionForms,
                      path='conference/{websafeConferenceKey}/sessions/type/{typeOfSession}',
                      http_method='GET',
                      name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Given a conference, return all sessions of a specified type (eg lecture, keynote, workshop)"""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException('No conference found with key: %s' % request.websafeConferenceKey)

        # filter sessions by typeOfSession
        sessions = conf.sessions.filter(Session.typeOfSession == request.typeOfSession)

        # Return a set of SessionForm objects per session
        return SessionForms(items=[session.toForm() for session in sessions])

    @endpoints.method(SESSION_BY_SPEAKER_GET_REQUEST,
                      SessionForms,
                      path='sessions/speaker/{speaker}',
                      http_method='GET',
                      name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Given a speaker, return all sessions given by this particular speaker, across all conferences"""

        sessions = Session.query(Session.speaker == request.speaker)

        # Return a set of SessionForm objects per session
        return SessionForms(items=[session.toForm() for session in sessions])

    def _createSessionObject(self, sessionForm):
        """Create Session object, returning SessionForm."""
        # make sure user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get the conference
        conf = ndb.Key(urlsafe=sessionForm.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException('No conference found with key: %s' % sessionForm.conferenceKey)

        # check ownership
        if getUserId(user) != conf.organizerUserId:
            raise endpoints.ForbiddenException('Only the organizer of this conference can add sessions.')

        # copy SessionForm/ProtoRPC Message into dict
        data = formToDict(sessionForm, exclude=('websafeKey', 'websafeConferenceKey'))
        # check required fields
        for key in Session.required_fields_schema:
            if not data[key]:
                raise endpoints.BadRequestException("'%s' field is required to create a session." % key)

        # convert date string to a datetime object.
        try:
            data['date'] = datetime.strptime(data['date'][:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise endpoints.BadRequestException("Invalid date format. Please use 'YYYY-MM-DD'")

        # convert date string to a time object. HH:MM
        try:
            data['startTime'] = datetime.strptime(data['startTime'][:5], "%H:%M").time()
        except (TypeError, ValueError):
            raise endpoints.BadRequestException("Invalid date format. Please use 'HH:MM'")

        if data['duration'] <= 0:
            raise endpoints.BadRequestException("Duration must be greater than zero")

        if data['date'] < conf.startDate or data['date'] > conf.endDate:
            raise endpoints.BadRequestException("Session must be within range of conference start and end date")

        # ask Datastore to allocate an ID.
        s_id = Session.allocate_ids(size=1, parent=conf.key)[0]
        # Datastore returns an integer ID that we can use to create a session key
        data['key'] = ndb.Key(Session, s_id, parent=conf.key)
        # Add session to datastore
        session = Session(**data)
        session.put()

        # Add a task to check and update new featured speaker
        taskqueue.add(
            params={'websafeConferenceKey': conf.key.urlsafe(), 'speaker': session.speaker},
            url='/tasks/set_featured_speaker'
        )

        return session.toForm()

    @endpoints.method(SESSION_POST_REQUEST,
                      SessionForm,
                      path='conference/sessions/{websafeConferenceKey}',
                      http_method='POST',
                      name='createSession')
    def createSession(self, request):
        """Creates a session, open to the organizer of the conference"""
        return self._createSessionObject(request)

    @endpoints.method(SESSION_WISHLIST_POST_REQUEST,
                      BooleanMessage,
                      path='profile/wishlist/{websafeSessionKey}',
                      http_method='POST',
                      name='addSessionToWishlist')
    @ndb.transactional(xg=True)
    def addSessionToWishlist(self, request):
        """Adds the given session to the user's wishlist"""
        # get user Profile
        prof = self._getProfileFromUser()
        # get session and check if it exists
        key = ndb.Key(urlsafe=request.websafeSessionKey)
        session = key.get()

        if not session:
            raise endpoints.BadRequestException("Session with key %s doesn't exist" % request.websafeSessionKey)
        # Check if session is already in user's wishlist
        if key in prof.wishList:
            raise ConflictException("This session is already in user's wishlist")
        # add session to user's wishlist
        prof.wishList.append(key)
        prof.put()
        return BooleanMessage(data=True)

    @endpoints.method(SESSION_WISHLIST_POST_REQUEST,
                      BooleanMessage,
                      path='profile/wishlist/{websafeSessionKey}',
                      http_method='DELETE',
                      name='removeSessionFromWishlist')
    @ndb.transactional()
    def removeSessionFromWishlist(self, request):
        """Deletes the given session from user's wish list"""
        # get user Profile
        prof = self._getProfileFromUser()
        key = ndb.Key(urlsafe=request.websafeSessionKey)
        # get session the session key and check if it exists in user's wish list
        if key not in prof.wishList:
            raise endpoints.BadRequestException("Failed to find session in user's wishlist")
        # remove session from user's wishlist
        prof.wishList.remove(key)
        prof.put()
        return BooleanMessage(data=True)

    @endpoints.method(message_types.VoidMessage,
                      SessionForms,
                      path='profile/wishlist/all',
                      http_method='GET',
                      name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """Returns sessions in user's wish list"""
        # get user Profile
        prof = self._getProfileFromUser()
        # get all sessions in user's wishlist
        sessions = ndb.get_multi(prof.wishList)
        # return a set of `SessionForm` objects
        return SessionForms(items=[session.toForm() for session in sessions])

    def _formatFilters(self, filters, fields):
        """Parse, check validity and format user supplied filters."""
        # formatted_filters:
        #   All filters to be used in query. (including a single inequality)
        formatted_filters = []
        # inequality_fields:
        #   All inequality filters.
        inequality_fields = []

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}
            try:
                filtr["field"] = fields[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                if not inequality_fields:
                    # only the first inequality is added to `formatted_filters`
                    formatted_filters.append(filtr)
                inequality_fields.append(filtr)
            else:
                formatted_filters.append(filtr)
        return inequality_fields, formatted_filters

    def _parseFilter(self, model, filtr, to_base_type=False):
        """ Parses a filter value according to the model property

            Example:
                Assuming `Conference` has a DateProperty named `date`.

                model = Conference
                filtr = {'field': 'date', 'value': '2015-01-01'}
                _parseFilter(model, filtr, to_base_type=True)

                print filtr
                output: {'field': 'date', 'value': datetime.datetime(2015, 1, 1, 0, 0)}

                # Note that filtr['value'] is a `datetime` object and not `date`.
                # This is because we set `to_base_type=True`

        :param model: The model to retrieve the field type
        :type model: ndb.Model

        :param filtr: a dictionary containing the field and value keys.
        :type filtr: dict

        :param to_base_type: when true, sets filtr['value'] to its base type. (default: False)
        :type to_base_type: bool
        """
        modelProperty = getattr(model, filtr["field"])
        if isinstance(modelProperty, ndb.DateProperty):
            try:
                # convert date string to a datetime object. (Convert to base type)
                filtr['value'] = datetime.strptime(filtr['value'][:10], "%Y-%m-%d")
                if not to_base_type:
                    # Convert to date object
                    filtr['value'] = filtr['value'].date()
            except ValueError:
                raise endpoints.BadRequestException("Invalid date format. Please use 'YYYY-MM-DD'")
        elif isinstance(modelProperty, ndb.TimeProperty):
            try:
                # Convert to base type
                filtr['value'] = datetime.strptime('1970-01-01T' + filtr['value'][:5], "%Y-%m-%dT%H:%M")
                if not to_base_type:
                    # Convert to time object
                    filtr['value'] = filtr['value'].time()
            except ValueError:
                raise endpoints.BadRequestException("Invalid time format. Please use 'HH:MM'")
        elif isinstance(modelProperty, ndb.IntegerProperty):
            filtr["value"] = int(filtr["value"])

    @endpoints.method(SessionQueryForms,
                      SessionForms,
                      path='querySessions',
                      http_method='POST',
                      name='querySessions')
    def querySessions(self, request):
        """Query for sessions."""
        # use `SESSION_FIELDS` to construct query.
        sessions = self._buildQuery(Session, request.filters, SESSION_FIELDS, order_by=['typeOfSession'])
        return SessionForms(items=[session.toForm() for session in sessions])

    @endpoints.method(message_types.VoidMessage,
                      StringMessage,
                      path='conference/featured_speakers/get',
                      http_method='GET',
                      name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Returns the featured speakers and their registered sessions from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_FEATURED_SPEAKER_KEY) or "")



api = endpoints.api_server([ConferenceApi])  # register API
