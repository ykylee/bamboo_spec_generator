from __future__ import annotations

import os

from ninja.errors import HttpError
from ninja.security import HttpBearer


class GeneratorTokenAuth(HttpBearer):
    def authenticate(self, request, token: str) -> str:
        expected = os.environ.get("BAMBOO_API_TOKEN", "")
        if not expected:
            raise HttpError(500, "BAMBOO_API_TOKEN is not configured.")
        if token != expected:
            raise HttpError(401, "Invalid API token.")
        return token
