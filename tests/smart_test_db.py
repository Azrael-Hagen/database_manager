"""
Shared test-DB infrastructure for smart import/export tests.

Re-exports the SAME TestingSessionLocal and override_get_db that test_api.py
uses so all test modules share one in-memory SQLite database.  Importing this
module triggers test_api to be loaded first (which creates the schema and sets
the initial app.dependency_overrides), then we re-export those objects.

Because Python's import system caches modules, importing test_api here and
having pytest also collect test_api.py as a test module both refer to the same
module instance – no schemas are created twice, no data is duplicated.
"""
from __future__ import annotations

import test_api as _test_api  # tests/ is on sys.path via pytest prepend mode

# Re-export the SAME objects that test_api.py uses.
TestingSessionLocal = _test_api.TestingSessionLocal
override_get_db = _test_api.override_get_db
