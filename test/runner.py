import sys
import os


# https://cloud.google.com/appengine/docs/python/tools/localunittesting?hl=en#Python_Writing_Datastore_and_memcache_tests
# Make sure your test runner has the appropriate libraries on the Python load path,
# including the App Engine libraries, yaml (included in the App Engine SDK),
# the application root, and any other modifications to the library path expected
# by application code (such as a local ./lib directory, if you have one)
sys.path.insert(1, '/usr/local/google_appengine')
sys.path.insert(1, '/usr/local/google_appengine/lib/yaml/lib')
# add absolute path of parent directory so we can import conference and models
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))


# Ensure that the google.appengine.* packages are available
# in tests as well as all bundled third-party packages.
import dev_appserver
dev_appserver.fix_sys_path()

import unittest

if '__main__' == __name__:
    # Discover and run tests.
    suite = unittest.loader.TestLoader().discover(os.path.dirname(os.path.realpath(__file__)), pattern='test_*.py')
    unittest.TextTestRunner(verbosity=2).run(suite)