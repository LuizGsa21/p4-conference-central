import sys
import os
import logging

# https://cloud.google.com/appengine/docs/python/tools/localunittesting?hl=en#Python_Writing_Datastore_and_memcache_tests
# --- UPDATE PATHS
sys.path.insert(1, '/usr/local/google_appengine')
sys.path.insert(1, '/usr/local/google_appengine/lib/yaml/lib')
# --- END UPDATE PATHS

# add absolute path of parent directory so we can import conference and models
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))


# Ensure that the google.appengine.* packages are available
# in tests as well as all bundled third-party packages.
import dev_appserver
dev_appserver.fix_sys_path()

import unittest

if '__main__' == __name__:
    # suppress warnings during test
    logging.getLogger().setLevel(logging.ERROR)
    # Discover and run tests.
    suite = unittest.loader.TestLoader().discover(os.path.dirname(os.path.realpath(__file__)), pattern='test_*.py')
    unittest.TextTestRunner(verbosity=2).run(suite)