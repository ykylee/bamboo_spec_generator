from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SystemSetting(TimestampedModel):
    KEY_COVERITY_CONNECT_URL = "coverity.connect.url"
    KEY_COVERITY_ON_NEW_CERT = "coverity.connect.on_new_cert"
    KEY_COVERITY_COMMIT_ENABLED = "coverity.commit.enabled"
    KEY_GIT_CLONE_URL_TEMPLATE = "repository.git.clone_url_template"
    KEY_REPOSITORY_LINKAGE_MODE = "repository.linkage_mode"
    KEY_BAMBOO_SERVER_URL = "bamboo.server.url"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=128, unique=True)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["key"], name="ix_system_setting_key"),
        ]

    def __str__(self) -> str:
        return self.key
