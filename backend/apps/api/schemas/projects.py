from __future__ import annotations

from ninja import Schema


class ProjectRepositoryIn(Schema):
    repoSlug: str
    repositoryType: str = "git"
    repositoryProvider: str = "bitbucket"
    repoType: str = "bitbucket"
    repoKey: str = ""
    cloneUrl: str = ""
    defaultBranch: str = ""
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


class BuildUnitProviderDetailsIn(Schema):
    planKey: str = ""
    buildId: str = ""
    jobPath: str = ""
    jobType: str = ""
    folderPath: str = ""
    pipelineKind: str = ""


class BuildUnitIn(Schema):
    externalKey: str
    displayName: str
    description: str = ""
    unitType: str = "build"
    repositorySlug: str = ""
    language: str = ""
    compiler: str = ""
    runtimeStack: str = ""
    lifecycleStatus: str = "active"
    isEnabled: bool = True
    providerDetails: BuildUnitProviderDetailsIn | None = None


class ProjectCreateIn(Schema):
    projectKey: str = ""
    name: str = ""
    description: str = ""
    ownerTeam: str = ""
    serviceType: str = ""
    ciProvider: str = "bamboo"
    status: str = "active"
    jiraProjectKey: str = ""
    bitbucketProjectKey: str = ""
    representativeRepoSlug: str = ""
    repositories: list[ProjectRepositoryIn] = []
    builds: list[ProjectBuildIn] = []
    buildUnits: list[BuildUnitIn] = []


class ProjectUpdateIn(Schema):
    name: str = ""
    description: str = ""
    ownerTeam: str = ""
    serviceType: str = ""
    ciProvider: str = "bamboo"
    status: str = "active"
    bitbucketProjectKey: str = ""
    representativeRepoSlug: str = ""
    repositories: list[ProjectRepositoryIn] = []
    builds: list[ProjectBuildIn] = []
    buildUnits: list[BuildUnitIn] = []
