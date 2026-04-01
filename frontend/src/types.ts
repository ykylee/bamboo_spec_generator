export type ProjectSummary = {
  projectKey: string;
  name: string;
  description: string;
  ownerTeam: string;
  serviceType: string;
  ciProvider: string;
  status: string;
  representativeRepoSlug: string;
  repositoryCount: number;
  repositorySlugs: string[];
  buildUnitCount: number;
  buildCount: number;
  generationReady: boolean;
  generationReadinessIssues: string[];
  readyBuildCount: number;
  activeDefinitionCount: number;
  missingCoverityCount: number;
  failedBuildCount: number;
  warningTags: string[];
  metadataWarningTags: string[];
  needsAttention: boolean;
  jiraProjectKey: string;
  bitbucketProjectKey: string;
};

export type ProjectDetail = {
  projectKey: string;
  name: string;
  description: string;
  ownerTeam: string;
  serviceType: string;
  ciProvider: string;
  status: string;
  representativeRepoSlug: string;
  jiraProjectKey: string;
  bitbucketProjectKey: string;
  generation: {
    generationReady: boolean;
    generationReadinessIssues: string[];
    readyBuildCount: number;
    totalBuildCount: number;
    activeDefinitionCount: number;
  };
  repositories: Array<{
    repoSlug: string;
    repositoryType: string;
    repositoryProvider: string;
    repoType: string;
    repoKey: string;
    cloneUrl: string;
    defaultBranch: string;
    coverityProject: string;
    coverityStream: string;
    isRepresentative: boolean;
  }>;
  buildUnits: Array<{
    ciProvider: string;
    externalKey: string;
    displayName: string;
    description: string;
    unitType: string;
    repositorySlug: string;
    language: string;
    compiler: string;
    runtimeStack: string;
    lifecycleStatus: string;
    isEnabled: boolean;
    latestVersion: string;
    latestSuccess: boolean | null;
    planKey: string;
    buildId: string;
    bambooProjectKey: string;
    repositoryLinkageMode: string;
    staticAnalysisToolVersion: string;
    coverityProject: string;
    buildInfoCount: number;
    jobPath: string;
    jobType: string;
    folderPath: string;
    pipelineKind: string;
    activeDefinitionCount: number;
  }>;
  builds: Array<{
    buildName: string;
    repositorySlug: string;
    planKey: string;
    buildId: string;
    language: string;
    compiler: string;
    runtimeStack: string;
  }>;
};

export type BuildPlanSummary = {
  projectKey: string;
  ciProvider: string;
  buildName: string;
  language: string;
  compiler: string;
  runtimeStack: string;
  planKey: string;
  buildId: string;
  staticAnalysisToolVersion: string;
  coverityProject: string;
  repositorySlug: string;
  latestVersion: string;
  latestSuccess: boolean | null;
  resultStatus: string;
  summaryMessage: string;
  buildInfoCount: number;
  detailUrl: string;
  buildInfoUrl: string;
};

export type BambooPlanStatus = {
  projectKey: string;
  planKey: string;
  buildId: string;
  fullPlanKey: string;
  year: string;
  configured: boolean;
  exists: boolean;
  message: string;
  detail?: string;
  planUrl: string;
  enabled?: boolean;
  suspended?: boolean;
  building?: boolean;
  description?: string;
  shortName?: string;
  latestResultState?: string;
  latestBuildNumber?: string;
  latestResultKey?: string;
  latestResultUrl?: string;
};

export type BambooPlanDetail = {
  projectKey: string;
  planKey: string;
  buildId: string;
  fullPlanKey: string;
  year: string;
  planUrl: string;
  summary: {
    shortName: string;
    description: string;
    enabled: boolean;
    suspended: boolean;
    building: boolean;
  };
  stages: Array<{
    name: string;
    description: string;
    jobs: Array<{
      key: string;
      name: string;
    }>;
  }>;
  branches: Array<{
    name: string;
    key?: string;
  }>;
  actions: Array<{
    name: string;
    key?: string;
  }>;
  variables: Array<{
    key: string;
    value: string;
  }>;
  recentPublishExecutions: Array<{
    publishExecutionId: string;
    status: string;
    message: string;
    output: string;
    returnCode: number | null;
    triggerSource: string;
    requestedBy: string;
    createdAt: string;
  }>;
  raw: unknown;
};

export type BuildPlanActiveDefinition = {
  planKey: string;
  buildId: string;
  year: string;
  definitionVersion: string;
  definition: {
    name: string;
    description: string;
    language: string;
    compiler: string;
    buildId: string;
    planKey: string;
    repository: {
      provider: string;
      projectKey: string;
      repoSlug: string;
      linkageMode: string;
      branches: string[];
    };
    requirements: {
      os: string;
      extraCapabilities: string[];
    };
    build: {
      prepareCommand: string;
      buildCommand: string;
      subPath: string;
      runtimeRequirements: {
        commands: string[];
        envVars: string[];
      };
      staticAnalysis: {
        customTool: {
          commands: string[];
        };
      };
      postBuildTrigger?: {
        type: string;
        targetPlanKey: string;
      };
    };
  };
};

export type BuildPlanPrepareContext = {
  planKey: string;
  project: {
    jiraProjectKey: string;
    bitbucketProjectKey: string;
    representativeRepoSlug: string;
  };
  projectBuild: {
    buildName: string;
    language: string;
    compiler: string;
  };
  currentRepository: {
    applicationLink: string;
    cloneUrl: string;
    coverityProject: string;
    coverityStream: string;
    linkageMode: string;
    repoSlug: string;
  };
  repositories: Array<{
    repoSlug: string;
    isRepresentative: boolean;
  }>;
  variables: Record<string, string>;
};

export type BuildPlanExecution = {
  buildExecutionId: string;
  buildVersionId: string;
  buildKey: string;
  version: string;
  buildNumber: number | string;
  commitHash: string;
  success: boolean;
  resultStatus: string;
  summaryMessage: string;
  stageName: string;
  jobName: string;
  taskName: string;
  startedAt: string;
  finishedAt: string;
  createdAt: string;
  staticAnalysisResults: Array<{
    toolName: string;
    status: string;
    summary: string;
    metricsJson: Record<string, unknown>;
  }>;
};

export type ModuleSummary = {
  assetId: string;
  assetKind: string;
  providerScope: string;
  moduleId: string;
  displayName: string;
  status: string;
  activeVersionId: string;
  latestVersionId: string;
  detailPath: string;
};

export type ModuleDetail = {
  assetId: string;
  assetKind: string;
  providerScope: string;
  moduleId: string;
  displayName: string;
  status: string;
  selectedVersionId: string;
  compareVersionId: string;
  previewContent: string;
  previewLanguage: string;
  diffContent: string;
  diffLanguage: string;
  recentIssues: Array<{
    status: string;
    errorCode: string;
    errorMessage: string;
    sourcePath: string;
    recordedAt: string;
  }>;
  versions: Array<{
    versionId: string;
    versionNumber: number;
    sourceFilename: string;
    validationStatus: string;
    validationMessage: string;
    uploadedAt: string;
    isActive: boolean;
    isLatest: boolean;
  }>;
};

export type ModuleLoadStatus = {
  activeAssetCount: number;
  lastSnapshot: {
    snapshotId: string;
    status: string;
    loadedCount: number;
    invalidCount: number;
    skippedCount: number;
    startedAt: string;
    finishedAt: string;
    summaryMessage: string;
  } | null;
  recentFailures: Array<{
    moduleId: string;
    status: string;
    errorCode: string;
    errorMessage: string;
  }>;
};

export type CoveritySettings = {
  connectUrl: string;
  onNewCert: string;
  commitEnabled: boolean;
  gitCloneUrlTemplate: string;
  repositoryLinkageMode: string;
};

export type BambooSettings = {
  serverUrl: string;
  tokenConfigured: boolean;
  tokenMasked: string;
};

export type JenkinsSettings = {
  serverUrl: string;
  username: string;
  tokenConfigured: boolean;
  tokenSource: string;
  tokenMasked: string;
};

export type GithubSettings = {
  serverUrl: string;
  tokenConfigured: boolean;
  tokenMasked: string;
};

export type BitbucketSettings = {
  serverUrl: string;
  tokenConfigured: boolean;
  tokenMasked: string;
};

export type GiteaSettings = {
  serverUrl: string;
  tokenConfigured: boolean;
  tokenMasked: string;
};
