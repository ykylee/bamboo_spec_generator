from __future__ import annotations

import os

from .base import *  # noqa: F401,F403


DEBUG = True
os.environ.setdefault("BAMBOO_DB_ENGINE", "sqlite")
DATABASES = build_database_config(default_engine="sqlite")
