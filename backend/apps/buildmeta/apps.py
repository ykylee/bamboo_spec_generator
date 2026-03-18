from __future__ import annotations

from django.apps import AppConfig


class BuildmetaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.buildmeta"
    label = "buildmeta"
    verbose_name = "Build Metadata"
