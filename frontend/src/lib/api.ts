import type {
  BambooSettings,
  BuildPlanActiveDefinition,
  BuildPlanExecution,
  BuildPlanPrepareContext,
  BambooPlanDetail,
  BambooPlanStatus,
  BitbucketSettings,
  BuildPlanSummary,
  CoveritySettings,
  GiteaSettings,
  GithubSettings,
  JenkinsSettings,
  ModuleDetail,
  ModuleLoadStatus,
  ModuleSummary,
  ProjectDetail,
  ProjectSummary,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:18080";

const API_TOKEN = import.meta.env.VITE_BAMBOO_API_TOKEN ?? "";

type ApiErrorPayload = {
  error?: string;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: init?.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
      ...(init?.headers ?? {}),
    },
    body: init?.body,
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      if (payload.error) {
        message = payload.error;
      }
    } catch {
      return Promise.reject(new Error(message));
    }
    return Promise.reject(new Error(message));
  }

  return (await response.json()) as T;
}

export async function fetchProjects(): Promise<ProjectSummary[]> {
  return requestJson<ProjectSummary[]>("/api/v1/projects");
}

export async function fetchProjectDetail(projectKey: string): Promise<ProjectDetail> {
  return requestJson<ProjectDetail>(`/api/v1/projects/${encodeURIComponent(projectKey)}`);
}

export async function fetchBuildPlans(): Promise<BuildPlanSummary[]> {
  return requestJson<BuildPlanSummary[]>("/api/v1/build-plans");
}

export async function fetchBuildPlanActiveDefinition(planKey: string): Promise<BuildPlanActiveDefinition> {
  return requestJson<BuildPlanActiveDefinition>(
    `/api/v1/build-plans/${encodeURIComponent(planKey)}/active-definition`,
  );
}

export async function fetchBuildPlanPrepareContext(planKey: string): Promise<BuildPlanPrepareContext> {
  return requestJson<BuildPlanPrepareContext>(
    `/api/v1/build-plans/${encodeURIComponent(planKey)}/prepare-context`,
  );
}

export async function fetchBuildPlanExecutions(planKey: string): Promise<BuildPlanExecution[]> {
  return requestJson<BuildPlanExecution[]>(
    `/api/v1/build-plans/${encodeURIComponent(planKey)}/executions`,
  );
}

export async function fetchBambooPlanStatus(planKey: string): Promise<BambooPlanStatus> {
  return requestJson<BambooPlanStatus>(`/api/v1/build-plans/${encodeURIComponent(planKey)}/bamboo/status`);
}

export async function fetchBambooPlanDetail(planKey: string): Promise<BambooPlanDetail> {
  return requestJson<BambooPlanDetail>(`/api/v1/build-plans/${encodeURIComponent(planKey)}/bamboo/details`);
}

export async function queueBambooPlan(payload: {
  planKey: string;
  stage?: string;
  executeAllStages: boolean;
  customRevision?: string;
  variables?: Record<string, string>;
}): Promise<{
  queued: boolean;
  message: string;
  detail: string;
  raw: unknown;
}> {
  return requestJson(`/api/v1/build-plans/${encodeURIComponent(payload.planKey)}/bamboo/queue`, {
    method: "POST",
    body: JSON.stringify({
      stage: payload.stage ?? "",
      executeAllStages: payload.executeAllStages,
      customRevision: payload.customRevision ?? "",
      variables: payload.variables ?? {},
    }),
  });
}

export async function publishBambooSpecs(planKey: string): Promise<{
  success: boolean;
  returnCode: number | null;
  message: string;
  output: string;
  detail: string;
}> {
  return requestJson(`/api/v1/build-plans/${encodeURIComponent(planKey)}/bamboo/publish`, {
    method: "POST",
  });
}

export async function fetchModules(): Promise<ModuleSummary[]> {
  return requestJson<ModuleSummary[]>("/api/v1/admin/modules");
}

export async function fetchModuleDetail(assetId: string): Promise<ModuleDetail> {
  return requestJson<ModuleDetail>(`/api/v1/admin/modules/${encodeURIComponent(assetId)}`);
}

export async function fetchModuleLoadStatus(): Promise<ModuleLoadStatus> {
  return requestJson<ModuleLoadStatus>("/api/v1/admin/modules/load-status");
}

export async function reloadModules(): Promise<{
  snapshotId: string;
  status: string;
  loadedCount: number;
  invalidCount: number;
  skippedCount: number;
  summaryMessage: string;
}> {
  return requestJson("/api/v1/admin/modules/reload", { method: "POST" });
}

export async function activateModule(assetId: string, versionId: string): Promise<{
  assetId: string;
  versionId: string;
  activePath: string;
}> {
  return requestJson(`/api/v1/admin/modules/${encodeURIComponent(assetId)}/activate`, {
    method: "POST",
    body: JSON.stringify({ versionId }),
  });
}

export async function deactivateModule(assetId: string): Promise<{
  assetId: string;
  status: string;
}> {
  return requestJson(`/api/v1/admin/modules/${encodeURIComponent(assetId)}/deactivate`, {
    method: "POST",
  });
}

export async function uploadModuleAsset(payload: {
  assetKind: string;
  providerScope: string;
  moduleId: string;
  activateAfterUpload: boolean;
  file: File;
}): Promise<{
  assetId: string;
  versionId: string;
  validationStatus: string;
  message: string;
  activated: boolean;
}> {
  const formData = new FormData();
  formData.set("assetKind", payload.assetKind);
  formData.set("providerScope", payload.providerScope);
  formData.set("moduleId", payload.moduleId);
  formData.set("activateAfterUpload", String(payload.activateAfterUpload));
  formData.set("file", payload.file);

  const response = await fetch(`${API_BASE_URL}/api/v1/admin/modules/uploads`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
    },
    body: formData,
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const errorPayload = (await response.json()) as ApiErrorPayload;
      if (errorPayload.error) {
        message = errorPayload.error;
      }
    } catch {
      return Promise.reject(new Error(message));
    }
    return Promise.reject(new Error(message));
  }

  return response.json();
}

export async function fetchCoveritySettings(): Promise<CoveritySettings> {
  return requestJson<CoveritySettings>("/api/v1/system-settings/coverity");
}

export async function fetchBambooSettings(): Promise<BambooSettings> {
  return requestJson<BambooSettings>("/api/v1/system-settings/bamboo");
}

export async function updateBambooSettings(payload: {
  serverUrl: string;
  token: string;
}): Promise<BambooSettings> {
  return requestJson<BambooSettings>("/api/v1/system-settings/bamboo", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function updateCoveritySettings(payload: CoveritySettings): Promise<CoveritySettings> {
  return requestJson<CoveritySettings>("/api/v1/system-settings/coverity", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function initializeSpecsDrafts(resetExisting = true): Promise<{
  initializedCount: number;
  updatedCount: number;
  removedCount: number;
  skippedCount: number;
}> {
  return requestJson("/api/v1/system-settings/specs-drafts/initialize?resetExisting=" + String(resetExisting), {
    method: "POST",
  });
}

export async function fetchJenkinsSettings(): Promise<JenkinsSettings> {
  return requestJson<JenkinsSettings>("/api/v1/system-settings/jenkins");
}

export async function updateJenkinsSettings(payload: {
  serverUrl: string;
  username: string;
  token: string;
}): Promise<JenkinsSettings> {
  return requestJson<JenkinsSettings>("/api/v1/system-settings/jenkins", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function fetchGithubSettings(): Promise<GithubSettings> {
  return requestJson<GithubSettings>("/api/v1/system-settings/github");
}

export async function updateGithubSettings(payload: {
  serverUrl: string;
  token: string;
}): Promise<GithubSettings> {
  return requestJson<GithubSettings>("/api/v1/system-settings/github", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function fetchBitbucketSettings(): Promise<BitbucketSettings> {
  return requestJson<BitbucketSettings>("/api/v1/system-settings/bitbucket");
}

export async function updateBitbucketSettings(payload: {
  serverUrl: string;
  token: string;
}): Promise<BitbucketSettings> {
  return requestJson<BitbucketSettings>("/api/v1/system-settings/bitbucket", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function fetchGiteaSettings(): Promise<GiteaSettings> {
  return requestJson<GiteaSettings>("/api/v1/system-settings/gitea");
}

export async function updateGiteaSettings(payload: {
  serverUrl: string;
  token: string;
}): Promise<GiteaSettings> {
  return requestJson<GiteaSettings>("/api/v1/system-settings/gitea", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

type ProjectWritePayload = {
  projectKey?: string;
  jiraProjectKey?: string;
  name: string;
  ciProvider: string;
  bitbucketProjectKey: string;
  representativeRepoSlug: string;
  repositories: Array<{
    repoSlug: string;
    coverityProject: string;
    coverityStream: string;
    isRepresentative: boolean;
  }>;
  builds: Array<{
    buildName: string;
    language: string;
    compiler: string;
    runtimeStack: string;
    buildId: string;
    planKey: string;
    repositorySlug: string;
  }>;
};

export async function createProject(payload: ProjectWritePayload): Promise<ProjectDetail> {
  return requestJson<ProjectDetail>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateProject(projectKey: string, payload: ProjectWritePayload): Promise<ProjectDetail> {
  return requestJson<ProjectDetail>(`/api/v1/projects/${encodeURIComponent(projectKey)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
