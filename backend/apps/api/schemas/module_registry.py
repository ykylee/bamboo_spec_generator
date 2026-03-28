from __future__ import annotations

from ninja import Schema


class ModuleActivateIn(Schema):
    versionId: str


class ModuleReloadIn(Schema):
    providerScope: str = ""
    assetKind: str = ""
