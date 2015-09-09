#!/usr/bin/env python

"""
main.py -- Udacity conference server-side Python App Engine
    HTTP controller handlers for memcache & task queue access

$Id$

created by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail, memcache
from google.appengine.ext import ndb
from conference import ConferenceApi, MEMCACHE_FEATURED_SPEAKER_KEY
from models import Session, Speaker


class SetAnnouncementHandler(webapp2.RequestHandler):
    def get(self):
        """Set Announcement in Memcache."""
        ConferenceApi._cacheAnnouncement()
        self.response.set_status(204)

class SetFeaturedSpeaker(webapp2.RequestHandler):
    def post(self):
        """Set featured speaker in Memcache.
        Note:
            The featured speaker is only updated if there is more than
            one session by the given speaker in the provided conference (websafeConferenceKey)
            GET params:
                - websafeConferenceKey
                    The conference to check for the given speaker
                - speaker
                    The possibly new featured speaker
        """

        # get conference key
        key = ndb.Key(urlsafe=self.request.get('websafeConferenceKey'))
        speaker = Speaker(name=self.request.get('speaker'))
        # get all sessions registered to this conference filtered by speaker
        featured_sessions = Session.query(ancestor=key).filter(Session.speaker == speaker).fetch()

        # If speaker is registered to more than one session, update featured speaker
        if len(featured_sessions) > 1:
            session_names = [session.name for session in featured_sessions]
            message = speaker.name + ': ' + ', '.join(session_names)
            memcache.set(MEMCACHE_FEATURED_SPEAKER_KEY, message)

        self.response.set_status(204)


class SendConfirmationEmailHandler(webapp2.RequestHandler):
    def post(self):
        """Send email confirming Conference creation."""
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'You created a new Conference!',            # subj
            'Hi, you have created a following '         # body
            'conference:\r\n\r\n%s' % self.request.get(
                'conferenceInfo')
        )


app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/set_featured_speaker', SetFeaturedSpeaker)
], debug=True)
