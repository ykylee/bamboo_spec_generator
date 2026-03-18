from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.api.router import api


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("", include("apps.ui.urls")),
]
