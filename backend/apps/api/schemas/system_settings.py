from __future__ import annotations

from ninja import Schema


class CoveritySystemSettingsIn(Schema):
    connectUrl: str = ""
    onNewCert: str = "trust"
    commitEnabled: bool = False
    gitCloneUrlTemplate: str = ""
    repositoryLinkageMode: str = "linked"
    bambooServerUrl: str = ""
