#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb
import datetime

class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT

class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)
    sessionKeysInWishList = ndb.StringProperty(repeated=True)

class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName = messages.StringField(1)
    teeShirtSize = messages.EnumField('TeeShirtSize', 2)

class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    teeShirtSize = messages.EnumField('TeeShirtSize', 3)
    conferenceKeysToAttend = messages.StringField(4, repeated=True)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)

class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class Conference(ndb.Model):
    """Conference -- Conference object"""
    name            = ndb.StringProperty(required=True)
    description     = ndb.StringProperty()
    organizerUserId = ndb.StringProperty(required=True)
    topics          = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    startDate       = ndb.DateProperty(required=True)
    month           = ndb.IntegerProperty() # TODO: do we need for indexing like Java?
    endDate         = ndb.DateProperty()
    maxAttendees    = ndb.IntegerProperty()
    seatsAvailable  = ndb.IntegerProperty()

    @property
    def sessions(self):
        return Session.query(ancestor=self.key)

    @classmethod
    def formatInput(cls, *args, **kwargs):
        for key in ('startDate', 'endDate'):
            value = kwargs.get(key, None)
            if isinstance(value, datetime.datetime):
                # format datetime to only account for year, month, and day
                kwargs[key] = value.replace(hour=0, minute=0, second=0, microsecond=0)
            elif isinstance(value, basestring):
                # turn string into a datatime object. only account for year, month, day
                kwargs[key] = datetime.datetime.strptime(value, "%Y-%m-%d").date()
        return cls(*args, **kwargs)


class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics          = messages.StringField(4, repeated=True)
    city            = messages.StringField(5)
    startDate       = messages.StringField(6) #DateTimeField()
    month           = messages.IntegerField(7)
    maxAttendees    = messages.IntegerField(8)
    seatsAvailable  = messages.IntegerField(9)
    endDate         = messages.StringField(10) #DateTimeField()
    websafeKey      = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)

class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)

class TeeShirtSize(messages.Enum):
    """TeeShirtSize -- t-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15

class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)

class ConferenceQueryForms(messages.Message):
    """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form message"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)

class Session(ndb.Model):
    """Session -- Session object"""
    name          = ndb.StringProperty(required=True)
    highlights    = ndb.StringProperty()
    speaker       = ndb.StringProperty(required=True)
    duration      = ndb.IntegerProperty(required=True)
    typeOfSession = ndb.StringProperty(required=True)
    date          = ndb.DateProperty(required=True)
    startTime     = ndb.TimeProperty(required=True)

    def toForm(self):
        return SessionForm(
            websafeKey=self.key.urlsafe(),
            name=self.name,
            highlights=self.highlights,
            speaker=self.speaker,
            duration=self.duration,
            typeOfSession=self.typeOfSession,
            date=self.date.strftime('%Y-%m-%d'),
            startTime=self.startTime.strftime('%H:%M')
        )

    @classmethod
    def formatInput(cls, *args, **kwargs):
        date = kwargs.get('date', None)
        if isinstance(date, datetime.datetime):
            # format datetime to only account for year, month, and day
            kwargs['date'] = date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif isinstance(date, basestring):
            # turn string into a datatime object. only account for year, month, day
            kwargs['date'] = datetime.datetime.strptime(date, "%Y-%m-%d").date()

        startTime = kwargs.get('startTime', None)
        if isinstance(startTime, datetime.time):
            # format startTime to only account for hours and minutes
            kwargs['startTime'] = startTime.replace(second=0, microsecond=0).time()
        elif isinstance(startTime, basestring):
            # turn string into a time object. only account for hours and minutes
            kwargs['startTime'] = datetime.datetime.strptime(startTime, "%H:%M").time()

        return cls(*args, **kwargs)

class SessionForm(messages.Message):
    """SessionForm -- Session outbound form message"""
    websafeKey           = messages.StringField(1)
    name                 = messages.StringField(2)
    highlights           = messages.StringField(3)
    speaker              = messages.StringField(4)
    duration             = messages.IntegerField(5)
    typeOfSession        = messages.StringField(6)
    date                 = messages.StringField(7)
    startTime            = messages.StringField(8)

class SessionForms(messages.Message):
    """SessionForm -- multiple SessionForm outbound form message"""
    items = messages.MessageField(SessionForm, 1, repeated=True)

class SessionQueryForm(messages.Message):
    """SessionQueryForm -- Session query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)

class SessionQueryForms(messages.Message):
    """SessionQueryForms -- multiple SessionQueryForm inbound form message"""
    filters = messages.MessageField(SessionQueryForm, 1, repeated=True)


