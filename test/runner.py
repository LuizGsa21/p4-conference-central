import sys
import os
import logging

# --- UPDATE PATHS
sys.path.insert(1, '/usr/local/google_appengine')  # App Engine libraries
sys.path.insert(1, '/usr/local/google_appengine/lib/yaml/lib')  # App Engine yaml
# If you are having trouble setting up the paths, checkout this guide.
# https://cloud.google.com/appengine/docs/python/tools/localunittesting?hl=en#Python_Writing_Datastore_and_memcache_tests
# --- END UPDATE PATHS

# add absolute path of parent directory so we can import from conference.py and models.py
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))


# Ensure that the google.appengine.* packages are available
# in tests as well as all bundled third-party packages.
import dev_appserver
dev_appserver.fix_sys_path()

if '__main__' == __name__:
    import unittest
    # suppress warnings during test
    logging.getLogger().setLevel(logging.ERROR)
    # Discover and run tests.
    suite = unittest.loader.TestLoader().discover(os.path.dirname(os.path.realpath(__file__)), pattern='test_*.py')
    unittest.TextTestRunner(verbosity=2).run(suite)