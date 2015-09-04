
def webapp_add_wsgi_middleware(app):
    """" Wrap WSGI application with the appstats middleware. """
    from google.appengine.ext.appstats import recording
    return recording.appstats_wsgi_middleware(app)
