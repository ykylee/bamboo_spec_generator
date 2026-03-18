from __future__ import annotations

import os

from .base import *  # noqa: F401,F403


DEBUG = False
os.environ["BAMBOO_DB_ENGINE"] = "sqlite"
os.environ["BAMBOO_DB_SQLITE_NAME"] = "test.sqlite3"
DATABASES = build_database_config(default_engine="sqlite")
