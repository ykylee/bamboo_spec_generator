from __future__ import annotations

import os

from .base import *  # noqa: F401,F403


DEBUG = False
os.environ.setdefault("BAMBOO_DB_ENGINE", "postgresql")
DATABASES = build_database_config(default_engine="postgresql")
