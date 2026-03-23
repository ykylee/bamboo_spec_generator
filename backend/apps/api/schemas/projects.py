from __future__ import annotations

from ninja import Schema


class ProjectRepositoryIn(Schema):
    repoSlug: str
    coverityProject: str = ""
    coverityStream: str = ""
    isRepresentative: bool = False


class ProjectBuildIn(Schema):
    buildName: str
    buildType: str = ""
    runtimeStack: str = ""
    buildId: str
    planKey: str
    repositorySlug: str


class ProjectCreateIn(Schema):
    jiraProjectKey: str
    bitbucketProjectKey: str
    representativeRepoSlug: str = ""
    repositories: list[ProjectRepositoryIn] = []
    builds: list[ProjectBuildIn] = []


class ProjectUpdateIn(Schema):
    bitbucketProjectKey: str
    representativeRepoSlug: str = ""
    repositories: list[ProjectRepositoryIn] = []
    builds: list[ProjectBuildIn] = []
