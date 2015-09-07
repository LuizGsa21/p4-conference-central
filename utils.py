import json
import os
import time
import uuid

from google.appengine.api import urlfetch
from models import Profile

def getUserId(user, id_type="email"):
    if id_type == "email":
        return user.email()

    if id_type == "oauth":
        """A workaround implementation for getting userid."""
        auth = os.getenv('HTTP_AUTHORIZATION')
        bearer, token = auth.split()
        token_type = 'id_token'
        if 'OAUTH_USER_ID' in os.environ:
            token_type = 'access_token'
        url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?%s=%s'
               % (token_type, token))
        user = {}
        wait = 1
        for i in range(3):
            resp = urlfetch.fetch(url)
            if resp.status_code == 200:
                user = json.loads(resp.content)
                break
            elif resp.status_code == 400 and 'invalid_token' in resp.content:
                url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?%s=%s'
                       % ('access_token', token))
            else:
                time.sleep(wait)
                wait = wait + i
        return user.get('user_id', '')

    if id_type == "custom":
        # implement your own user_id creation and getting algorythm
        # this is just a sample that queries datastore for an existing profile
        # and generates an id if profile does not exist for an email
        profile = Conference.query(Conference.mainEmail == user.email())
        if profile:
            return profile.id()
        else:
            return str(uuid.uuid1().get_hex())

def formToDict(form, exclude=()):
    """ Returns a dictionary from the given form/ProtoRPC Message """
    return {field.name: getattr(form, field.name) for field in form.all_fields() if field.name not in exclude}

def expression_closure(field, operator, value):
    """ Creates and returns a function expression.
        Operator supports: < <= > >= !=

        Example:
            >>> class Obj:
            >>>     number = 5
            >>> obj = Obj()
            >>> func_expression = expression_closure('number', '<', 10)
            >>> func_expression(obj)
            True
            >>> obj.number = 11
            >>> func_expression(obj)
            False
    """
    if operator == '>':
        return lambda obj: getattr(obj, field) > value
    elif operator == '<':
        return lambda obj: getattr(obj, field) < value
    elif operator == '>=':
        return lambda obj: getattr(obj, field) >= value
    elif operator == '<=':
        return lambda obj: getattr(obj, field) <= value
    elif operator == '!=':
        return lambda obj: getattr(obj, field) != value
    else:
        raise ValueError("Unknown operator %s" % operator)
