import { useEffect, useState } from "react";
import {
  activateModule,
  fetchBitbucketSettings,
  createProject,
  deactivateModule,
  fetchBambooSettings,
  fetchBuildPlanActiveDefinition,
  fetchBuildPlanExecutions,
  fetchBuildPlanPrepareContext,
  fetchBambooPlanDetail,
  fetchBambooPlanStatus,
  fetchBuildPlans,
  fetchCoveritySettings,
  fetchGiteaSettings,
  fetchGithubSettings,
  fetchJenkinsSettings,
  fetchModuleDetail,
  fetchModuleLoadStatus,
  fetchModules,
  fetchProjectDetail,
  fetchProjects,
  initializeSpecsDrafts,
  publishBambooSpecs,
  queueBambooPlan,
  reloadModules,
  updateBitbucketSettings,
  updateBambooSettings,
  updateCoveritySettings,
  updateGiteaSettings,
  updateGithubSettings,
  updateJenkinsSettings,
  updateProject,
  uploadModuleAsset,
} from "./lib/api";
import type {
  BambooSettings,
  BitbucketSettings,
  BuildPlanActiveDefinition,
  BuildPlanExecution,
  BuildPlanPrepareContext,
  BambooPlanDetail,
  BambooPlanStatus,
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
} from "./types";

const TEST_ENV = {
  bambooUrl: "http://127.0.0.1:8085/bamboo",
  jenkinsUrl: "http://127.0.0.1:8081",
  jenkinsAgentPort: "50001",
  giteaUrl: "http://127.0.0.1:3001",
};

type FilterMode = "all" | "attention" | "healthy";
type WorkspaceMode = "projects" | "build-plans" | "modules" | "settings" | "admin";
type ProjectFormMode = "create" | "update";
type SettingsTarget =
  | "coverity"
  | "bamboo"
  | "jenkins"
  | "github"
  | "bitbucket"
  | "gitea";
type AdminTarget = "drafts" | "module-snapshot";
type ProjectRepositoryFormState = {
  repoSlug: string;
  coverityProject: string;
  coverityStream: string;
  isRepresentative: boolean;
};

type ProjectBuildFormState = {
  buildName: string;
  language: string;
  compiler: string;
  runtimeStack: string;
  buildId: string;
  planKey: string;
  repositorySlug: string;
};

type QueueFormState = {
  stage: string;
  executeAllStages: boolean;
  customRevision: string;
  variableKey: string;
  variableValue: string;
};

type ProjectFormState = {
  projectKey: string;
  name: string;
  ciProvider: string;
  bitbucketProjectKey: string;
  representativeRepoSlug: string;
  repositories: ProjectRepositoryFormState[];
  builds: ProjectBuildFormState[];
};

type CoverityFormState = {
  connectUrl: string;
  onNewCert: string;
  commitEnabled: boolean;
  gitCloneUrlTemplate: string;
  repositoryLinkageMode: string;
};

type BambooFormState = {
  serverUrl: string;
  token: string;
};

type JenkinsFormState = {
  serverUrl: string;
  username: string;
  token: string;
};

type GithubFormState = {
  serverUrl: string;
  token: string;
};

type BitbucketFormState = {
  serverUrl: string;
  token: string;
};

type GiteaFormState = {
  serverUrl: string;
  token: string;
};

type ModuleUploadFormState = {
  assetKind: string;
  providerScope: string;
  moduleId: string;
  activateAfterUpload: boolean;
  file: File | null;
};

const filterLabels: Array<{ id: FilterMode; label: string }> = [
  { id: "all", label: "전체" },
  { id: "attention", label: "주의 필요" },
  { id: "healthy", label: "정상" },
];
const CUSTOM_LANGUAGE = "__custom_language__";
const CUSTOM_COMPILER = "__custom_compiler__";
const CUSTOM_RUNTIME_STACK = "__custom__";
const languagePresets = ["java", "javascript", "typescript", "python", "csharp", "cpp"];
const compilerPresets = ["maven", "gradle", "node", "python", "dotnet", "msbuild", "gcc", "clang"];
const runtimeStackPresets = [
  "java17",
  "java21",
  "node18",
  "node20",
  "python3.11",
  "python3.12",
  "dotnet8",
  "vs2022",
];
const workspaceMeta: Record<WorkspaceMode, { eyebrow: string; title: string; description: string }> = {
  projects: {
    eyebrow: "project register",
    title: "프로젝트 운영",
    description: "준비도, 누락 메타데이터, 저장소 구성을 한 작업면에서 다룹니다.",
  },
  "build-plans": {
    eyebrow: "plan operations",
    title: "빌드 플랜 운영",
    description: "Bamboo 상태, publish, queue, execution 이력을 한곳에서 확인합니다.",
  },
  modules: {
    eyebrow: "module registry",
    title: "모듈 운영",
    description: "선언형 모듈 버전, reload 상태, 활성 자산을 추적합니다.",
  },
  settings: {
    eyebrow: "system integrations",
    title: "시스템 설정",
    description: "CI, 형상관리, 정적분석 외부 시스템 연결을 관리합니다.",
  },
  admin: {
    eyebrow: "operations admin",
    title: "관리 작업",
    description: "drafts 초기화와 module snapshot 같은 내부 관리 기능을 다룹니다.",
  },
};
const workspaceSearchPlaceholder: Record<WorkspaceMode, string> = {
  projects: "project key, repo slug, bitbucket key",
  "build-plans": "plan key, build id, repo slug",
  modules: "module id, asset kind, provider scope",
  settings: "",
  admin: "",
};

function formatIssueLabel(project: ProjectSummary) {
  if (project.generationReady && !project.needsAttention) {
    return "ready";
  }
  if (project.warningTags.length > 0) {
    return project.warningTags[0];
  }
  if (project.generationReadinessIssues.length > 0) {
    return project.generationReadinessIssues[0];
  }
  return "metadata pending";
}

function emptyProjectForm(): ProjectFormState {
  return {
    projectKey: "",
    name: "",
    ciProvider: "bamboo",
    bitbucketProjectKey: "",
    representativeRepoSlug: "",
    repositories: [
      {
        repoSlug: "",
        coverityProject: "",
        coverityStream: "",
        isRepresentative: true,
      },
    ],
    builds: [
      {
        buildName: "",
        language: "",
        compiler: "",
        runtimeStack: "",
        buildId: "",
        planKey: "",
        repositorySlug: "",
      },
    ],
  };
}

function projectToForm(project: ProjectDetail): ProjectFormState {
  const repositories =
    project.repositories.length > 0
      ? project.repositories.map((repository) => ({
          repoSlug: repository.repoSlug,
          coverityProject: repository.coverityProject,
          coverityStream: repository.coverityStream,
          isRepresentative: repository.isRepresentative,
        }))
      : emptyProjectForm().repositories;
  const builds =
    project.builds.length > 0
      ? project.builds.map((build) => ({
          buildName: build.buildName,
          language: build.language,
          compiler: build.compiler,
          runtimeStack: build.runtimeStack,
          buildId: build.buildId,
          planKey: build.planKey,
          repositorySlug: build.repositorySlug,
        }))
      : emptyProjectForm().builds;
  return {
    projectKey: project.projectKey,
    name: project.name,
    ciProvider: project.ciProvider || "bamboo",
    bitbucketProjectKey: project.bitbucketProjectKey,
    representativeRepoSlug: project.representativeRepoSlug,
    repositories,
    builds,
  };
}

function coverityToForm(settings: CoveritySettings): CoverityFormState {
  return {
    connectUrl: settings.connectUrl,
    onNewCert: settings.onNewCert,
    commitEnabled: settings.commitEnabled,
    gitCloneUrlTemplate: settings.gitCloneUrlTemplate,
    repositoryLinkageMode: settings.repositoryLinkageMode,
  };
}

function bambooToForm(settings: BambooSettings): BambooFormState {
  return {
    serverUrl: settings.serverUrl,
    token: "",
  };
}

function jenkinsToForm(settings: JenkinsSettings): JenkinsFormState {
  return {
    serverUrl: settings.serverUrl,
    username: settings.username,
    token: "",
  };
}

function githubToForm(settings: GithubSettings): GithubFormState {
  return {
    serverUrl: settings.serverUrl,
    token: "",
  };
}

function bitbucketToForm(settings: BitbucketSettings): BitbucketFormState {
  return {
    serverUrl: settings.serverUrl,
    token: "",
  };
}

function giteaToForm(settings: GiteaSettings): GiteaFormState {
  return {
    serverUrl: settings.serverUrl,
    token: "",
  };
}

function emptyQueueForm(): QueueFormState {
  return {
    stage: "",
    executeAllStages: true,
    customRevision: "",
    variableKey: "",
    variableValue: "",
  };
}

function bambooUrlNeedsContextPath(url: string): boolean {
  const trimmed = url.trim();
  return trimmed !== "" && !trimmed.includes("/bamboo");
}

function duplicateValues(values: string[]): string[] {
  const counts = new Map<string, number>();
  for (const value of values.map((item) => item.trim()).filter(Boolean)) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .filter(([, count]) => count > 1)
    .map(([value]) => value);
}

function flattenMetrics(
  value: unknown,
  prefix = "",
): Array<{ key: string; value: string }> {
  if (value === null || value === undefined) {
    return [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((entry, index) =>
      flattenMetrics(entry, prefix ? `${prefix}[${index}]` : `[${index}]`),
    );
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, entry]) =>
      flattenMetrics(entry, prefix ? `${prefix}.${key}` : key),
    );
  }
  return [
    {
      key: prefix || "value",
      value: typeof value === "string" ? value : JSON.stringify(value),
    },
  ];
}

function mergeSuggestions(currentValue: string, presets: string[]): string[] {
  const suggestions = new Set(presets);
  if (currentValue.trim()) {
    suggestions.add(currentValue.trim());
  }
  return Array.from(suggestions);
}

function suggestedLanguages(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string[] {
  const suggestions = new Set(mergeSuggestions(build.language, languagePresets));
  const normalizedCompiler = build.compiler.trim().toLowerCase();
  const normalizedRuntime = build.runtimeStack.trim().toLowerCase();

  if (normalizedCompiler === "maven" || normalizedCompiler === "gradle" || normalizedRuntime.includes("java")) {
    suggestions.add("java");
  }
  if (
    ["node", "node.js"].includes(normalizedCompiler) ||
    normalizedRuntime.includes("node")
  ) {
    suggestions.add("javascript");
    suggestions.add("typescript");
  }
  if (normalizedCompiler === "python" || normalizedRuntime.includes("python")) {
    suggestions.add("python");
  }
  if (normalizedCompiler === "dotnet" || normalizedRuntime.includes(".net")) {
    suggestions.add("csharp");
  }
  if (["msbuild", "gcc", "clang"].includes(normalizedCompiler)) {
    suggestions.add("cpp");
  }

  return Array.from(suggestions);
}

function languageSelectValue(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string {
  const language = build.language.trim();
  if (!language) {
    return "";
  }
  return suggestedLanguages(build).includes(language) ? language : CUSTOM_LANGUAGE;
}

function suggestedCompilers(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string[] {
  const suggestions = new Set(mergeSuggestions(build.compiler, compilerPresets));
  const normalizedLanguage = build.language.trim().toLowerCase();
  const normalizedRuntime = build.runtimeStack.trim().toLowerCase();

  if (normalizedLanguage === "java" || normalizedRuntime.includes("java")) {
    suggestions.add("maven");
    suggestions.add("gradle");
  }
  if (["javascript", "typescript"].includes(normalizedLanguage) || normalizedRuntime.includes("node")) {
    suggestions.add("node");
  }
  if (normalizedLanguage === "python" || normalizedRuntime.includes("python")) {
    suggestions.add("python");
  }
  if (normalizedLanguage === "csharp" || normalizedRuntime.includes(".net")) {
    suggestions.add("dotnet");
  }
  if (normalizedLanguage === "cpp") {
    suggestions.add("msbuild");
    suggestions.add("gcc");
    suggestions.add("clang");
  }

  return Array.from(suggestions);
}

function compilerSelectValue(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string {
  const compiler = build.compiler.trim();
  if (!compiler) {
    return "";
  }
  return suggestedCompilers(build).includes(compiler) ? compiler : CUSTOM_COMPILER;
}

function preferredLanguage(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string {
  const options = suggestedLanguages(build).filter(Boolean);
  return options[0] ?? "";
}

function preferredCompiler(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string {
  const options = suggestedCompilers(build).filter(Boolean);
  return options[0] ?? "";
}

function suggestedRuntimeStacks(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string[] {
  const normalizedLanguage = build.language.trim().toLowerCase();
  const normalizedCompiler = build.compiler.trim().toLowerCase();
  const suggestions = new Set<string>();

  if (normalizedLanguage === "java" || normalizedCompiler === "maven" || normalizedCompiler === "gradle") {
    suggestions.add("java17");
    suggestions.add("java21");
  }
  if (
    ["javascript", "typescript", "node", "node.js"].includes(normalizedLanguage) ||
    ["node", "node.js"].includes(normalizedCompiler)
  ) {
    suggestions.add("node18");
    suggestions.add("node20");
  }
  if (normalizedLanguage === "python" || normalizedCompiler === "python") {
    suggestions.add("python3.11");
    suggestions.add("python3.12");
  }
  if (normalizedLanguage === "csharp" || normalizedCompiler === "dotnet") {
    suggestions.add("dotnet8");
  }
  if (normalizedCompiler.startsWith("vs") || normalizedCompiler === "msbuild") {
    suggestions.add("vs2022");
  }
  if (build.runtimeStack.trim()) {
    suggestions.add(build.runtimeStack.trim());
  }

  for (const preset of runtimeStackPresets) {
    suggestions.add(preset);
  }

  return Array.from(suggestions);
}

function runtimeStackSelectValue(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string {
  const runtimeStack = build.runtimeStack.trim();
  if (!runtimeStack) {
    return "";
  }
  return suggestedRuntimeStacks(build).includes(runtimeStack) ? runtimeStack : CUSTOM_RUNTIME_STACK;
}

function preferredRuntimeStack(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">): string {
  const options = suggestedRuntimeStacks(build).filter(Boolean);
  return options[0] ?? "";
}

function recommendedBuildMeta(build: Pick<ProjectBuildFormState, "language" | "compiler" | "runtimeStack">) {
  const language = build.language.trim() || preferredLanguage(build);
  const compiler = build.compiler.trim() || preferredCompiler({ ...build, language });
  const runtimeStack =
    build.runtimeStack.trim() || preferredRuntimeStack({ ...build, language, compiler });
  return { language, compiler, runtimeStack };
}

function slugToken(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function compactToken(value: string): string {
  return value
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "");
}

function preferredBuildId(
  build: Pick<ProjectBuildFormState, "buildName" | "repositorySlug" | "buildId">,
): string {
  return (
    slugToken(build.repositorySlug) ||
    slugToken(build.buildName) ||
    slugToken(build.buildId)
  );
}

function preferredPlanKey(
  projectKey: string,
  build: Pick<ProjectBuildFormState, "buildName" | "repositorySlug" | "buildId" | "planKey">,
): string {
  const projectToken = compactToken(projectKey).slice(0, 6);
  const buildToken = compactToken(build.buildName || build.repositorySlug || build.buildId || build.planKey).slice(0, 4);
  return `${projectToken}${buildToken}`.slice(0, 10) || compactToken(build.planKey).slice(0, 10);
}

function recommendedBuildIdentity(
  projectKey: string,
  build: Pick<ProjectBuildFormState, "buildName" | "repositorySlug" | "buildId" | "planKey">,
) {
  const buildId = build.buildId.trim() || preferredBuildId(build);
  const planKey = build.planKey.trim() || preferredPlanKey(projectKey, { ...build, buildId });
  return { buildId, planKey };
}

function validateProjectForm(form: ProjectFormState): string[] {
  const errors: string[] = [];
  if (!form.projectKey.trim()) {
    errors.push("project key를 입력해 주세요.");
  }
  if (!form.name.trim()) {
    errors.push("display name을 입력해 주세요.");
  }
  const repositories = form.repositories.filter((repository) => repository.repoSlug.trim() !== "");
  if (repositories.length === 0) {
    errors.push("최소 1개의 repository slug가 필요합니다.");
  }
  const duplicateRepositories = duplicateValues(repositories.map((repository) => repository.repoSlug));
  if (duplicateRepositories.length > 0) {
    errors.push(`repository slug 중복: ${duplicateRepositories.join(", ")}`);
  }
  const representativeCount = repositories.filter((repository) => repository.isRepresentative).length;
  if (repositories.length > 0 && representativeCount !== 1) {
    errors.push("대표 저장소는 정확히 1개여야 합니다.");
  }
  const repositorySlugs = new Set(repositories.map((repository) => repository.repoSlug.trim()));
  const builds = form.builds.filter(
    (build) =>
      build.buildName.trim() !== "" ||
      build.buildId.trim() !== "" ||
      build.planKey.trim() !== "" ||
      build.repositorySlug.trim() !== "",
  );
  if (builds.length === 0) {
    errors.push("최소 1개의 build가 필요합니다.");
  }
  const duplicateBuildIds = duplicateValues(builds.map((build) => build.buildId));
  if (duplicateBuildIds.length > 0) {
    errors.push(`build id 중복: ${duplicateBuildIds.join(", ")}`);
  }
  const duplicatePlanKeys = duplicateValues(builds.map((build) => build.planKey));
  if (duplicatePlanKeys.length > 0) {
    errors.push(`plan key 중복: ${duplicatePlanKeys.join(", ")}`);
  }
  for (const build of builds) {
    if (!build.buildName.trim()) {
      errors.push("각 build에는 build name이 필요합니다.");
      break;
    }
    if (!build.buildId.trim()) {
      errors.push("각 build에는 build id가 필요합니다.");
      break;
    }
    if (!build.planKey.trim()) {
      errors.push("각 build에는 plan key가 필요합니다.");
      break;
    }
    if (!build.repositorySlug.trim()) {
      errors.push("각 build에는 연결된 repository slug가 필요합니다.");
      break;
    }
    if (!repositorySlugs.has(build.repositorySlug.trim())) {
      errors.push("build의 repository slug는 등록된 repository 중 하나여야 합니다.");
      break;
    }
  }
  return errors;
}

export function App() {
  const [workspace, setWorkspace] = useState<WorkspaceMode>("projects");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [buildPlans, setBuildPlans] = useState<BuildPlanSummary[]>([]);
  const [selectedPlanKey, setSelectedPlanKey] = useState("");
  const [selectedBuildPlan, setSelectedBuildPlan] = useState<BuildPlanSummary | null>(null);
  const [activeDefinition, setActiveDefinition] = useState<BuildPlanActiveDefinition | null>(null);
  const [prepareContext, setPrepareContext] = useState<BuildPlanPrepareContext | null>(null);
  const [buildPlanExecutions, setBuildPlanExecutions] = useState<BuildPlanExecution[]>([]);
  const [selectedExecutionId, setSelectedExecutionId] = useState("");
  const [bambooPlanStatus, setBambooPlanStatus] = useState<BambooPlanStatus | null>(null);
  const [bambooPlanDetail, setBambooPlanDetail] = useState<BambooPlanDetail | null>(null);
  const [bambooLoading, setBambooLoading] = useState(false);
  const [bambooActionLoading, setBambooActionLoading] = useState(false);
  const [queueForm, setQueueForm] = useState<QueueFormState>(emptyQueueForm());
  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [selectedModuleId, setSelectedModuleId] = useState("");
  const [selectedModule, setSelectedModule] = useState<ModuleDetail | null>(null);
  const [moduleLoadStatus, setModuleLoadStatus] = useState<ModuleLoadStatus | null>(null);
  const [bambooSettings, setBambooSettings] = useState<BambooSettings | null>(null);
  const [coveritySettings, setCoveritySettings] = useState<CoveritySettings | null>(null);
  const [jenkinsSettings, setJenkinsSettings] = useState<JenkinsSettings | null>(null);
  const [githubSettings, setGithubSettings] = useState<GithubSettings | null>(null);
  const [bitbucketSettings, setBitbucketSettings] = useState<BitbucketSettings | null>(null);
  const [giteaSettings, setGiteaSettings] = useState<GiteaSettings | null>(null);
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [selectedProject, setSelectedProject] = useState<ProjectDetail | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterMode>("all");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [buildPlanError, setBuildPlanError] = useState("");
  const [buildPlanNotice, setBuildPlanNotice] = useState("");
  const [projectFormMode, setProjectFormMode] = useState<ProjectFormMode>("update");
  const [projectForm, setProjectForm] = useState<ProjectFormState>(emptyProjectForm());
  const [savingProject, setSavingProject] = useState(false);
  const [projectFormErrors, setProjectFormErrors] = useState<string[]>([]);
  const [coverityForm, setCoverityForm] = useState<CoverityFormState>({
    connectUrl: "",
    onNewCert: "trust",
    commitEnabled: false,
    gitCloneUrlTemplate: "",
    repositoryLinkageMode: "linked",
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [initializingDrafts, setInitializingDrafts] = useState(false);
  const [selectedSettingsTarget, setSelectedSettingsTarget] = useState<SettingsTarget>("coverity");
  const [selectedAdminTarget, setSelectedAdminTarget] = useState<AdminTarget>("drafts");
  const [moduleActionLoading, setModuleActionLoading] = useState(false);
  const [moduleUploadForm, setModuleUploadForm] = useState<ModuleUploadFormState>({
    assetKind: "task_module",
    providerScope: "common",
    moduleId: "",
    activateAfterUpload: true,
    file: null,
  });
  const [showModuleComposer, setShowModuleComposer] = useState(false);
  const [bambooForm, setBambooForm] = useState<BambooFormState>({
    serverUrl: "",
    token: "",
  });
  const [jenkinsForm, setJenkinsForm] = useState<JenkinsFormState>({
    serverUrl: "",
    username: "",
    token: "",
  });
  const [githubForm, setGithubForm] = useState<GithubFormState>({
    serverUrl: "",
    token: "",
  });
  const [bitbucketForm, setBitbucketForm] = useState<BitbucketFormState>({
    serverUrl: "",
    token: "",
  });
  const [giteaForm, setGiteaForm] = useState<GiteaFormState>({
    serverUrl: "",
    token: "",
  });

  const loadProjects = () =>
    fetchProjects()
      .then((items) => {
        setProjects(items);
        setSelectedKey((current) => current || items[0]?.projectKey || "");
        return items;
      });

  const loadBuildPlans = () =>
    fetchBuildPlans()
      .then((items) => {
        setBuildPlans(items);
        setSelectedPlanKey((current) => current || items[0]?.planKey || "");
        return items;
      });

  const loadModules = () =>
    fetchModules().then((items) => {
      setModules(items);
      setSelectedModuleId((current) => current || items[0]?.assetId || "");
      return items;
    });

  const loadModuleLoadStatus = () =>
    fetchModuleLoadStatus().then((status) => {
      setModuleLoadStatus(status);
      return status;
    });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    loadProjects()
      .then((items) => {
        if (cancelled) {
          return;
        }
        setProjects(items);
      })
      .catch((reason: unknown) => {
        if (cancelled) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "프로젝트를 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const nextPlan = buildPlans.find((plan) => plan.planKey === selectedPlanKey) ?? null;
    setSelectedBuildPlan(nextPlan);
  }, [buildPlans, selectedPlanKey]);

  useEffect(() => {
    setSelectedExecutionId((current) => current || buildPlanExecutions[0]?.buildExecutionId || "");
  }, [buildPlanExecutions]);

  useEffect(() => {
    if (workspace !== "build-plans" || !selectedPlanKey) {
      setActiveDefinition(null);
      setPrepareContext(null);
      setBuildPlanExecutions([]);
      setBambooPlanStatus(null);
      setBambooPlanDetail(null);
      setBuildPlanError("");
      setBuildPlanNotice("");
      return;
    }
    let cancelled = false;
    setBambooLoading(true);
    setBuildPlanError("");
    Promise.all([
      fetchBuildPlanActiveDefinition(selectedPlanKey),
      fetchBuildPlanPrepareContext(selectedPlanKey),
      fetchBuildPlanExecutions(selectedPlanKey),
      fetchBambooPlanStatus(selectedPlanKey),
      fetchBambooPlanDetail(selectedPlanKey),
    ])
      .then(([definition, context, executions, status, detail]) => {
        if (cancelled) {
          return;
        }
        setActiveDefinition(definition);
        setPrepareContext(context);
        setBuildPlanExecutions(executions);
        setBambooPlanStatus(status);
        setBambooPlanDetail(detail);
      })
      .catch((reason: unknown) => {
        if (cancelled) {
          return;
        }
        setBuildPlanError(reason instanceof Error ? reason.message : "Bamboo 플랜 정보를 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!cancelled) {
          setBambooLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedPlanKey, workspace]);

  useEffect(() => {
    let cancelled = false;
    loadBuildPlans()
      .then((items) => {
        if (!cancelled) {
          setBuildPlans(items);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "빌드 플랜을 불러오지 못했습니다.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadModules()
      .then((items) => {
        if (!cancelled) {
          setModules(items);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "모듈 목록을 불러오지 못했습니다.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadModuleLoadStatus()
      .then((status) => {
        if (!cancelled) {
          setModuleLoadStatus(status);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "모듈 로드 상태를 불러오지 못했습니다.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedModuleId) {
      setSelectedModule(null);
      return;
    }
    let cancelled = false;
    fetchModuleDetail(selectedModuleId)
      .then((detail) => {
        if (!cancelled) {
          setSelectedModule(detail);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "모듈 상세를 불러오지 못했습니다.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedModuleId]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchCoveritySettings(),
      fetchBambooSettings(),
      fetchJenkinsSettings(),
      fetchGithubSettings(),
      fetchBitbucketSettings(),
      fetchGiteaSettings(),
    ])
      .then(([coverity, bamboo, jenkins, github, bitbucket, gitea]) => {
        if (!cancelled) {
          setCoveritySettings(coverity);
          setCoverityForm(coverityToForm(coverity));
          setBambooSettings(bamboo);
          setBambooForm(bambooToForm(bamboo));
          setJenkinsSettings(jenkins);
          setJenkinsForm(jenkinsToForm(jenkins));
          setGithubSettings(github);
          setGithubForm(githubToForm(github));
          setBitbucketSettings(bitbucket);
          setBitbucketForm(bitbucketToForm(bitbucket));
          setGiteaSettings(gitea);
          setGiteaForm(giteaToForm(gitea));
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "시스템 설정을 불러오지 못했습니다.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedKey) {
      setSelectedProject(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    fetchProjectDetail(selectedKey)
      .then((project) => {
        if (!cancelled) {
          setSelectedProject(project);
          if (projectFormMode === "update") {
            setProjectForm(projectToForm(project));
          }
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "프로젝트 상세를 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDetailLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedKey]);

  const startNewProject = () => {
    setProjectFormMode("create");
    setProjectForm(emptyProjectForm());
    setProjectFormErrors([]);
    setNotice("");
    setError("");
  };

  const editSelectedProject = () => {
    if (selectedProject) {
      setProjectFormMode("update");
      setProjectForm(projectToForm(selectedProject));
      setProjectFormErrors([]);
      setNotice("");
      setError("");
    }
  };

  const closeNewProjectEditor = () => {
    setProjectFormMode("update");
    setProjectFormErrors([]);
    setNotice("");
    setError("");
    if (selectedProject) {
      setProjectForm(projectToForm(selectedProject));
    } else {
      setProjectForm(emptyProjectForm());
    }
  };

  const handleProjectFormChange = (field: keyof ProjectFormState, value: string) => {
    setProjectForm((current) => {
      if (field === "representativeRepoSlug") {
        const repositories = current.repositories.map((repository) => ({
          ...repository,
          isRepresentative: repository.repoSlug === value,
        }));
        const next = { ...current, representativeRepoSlug: value, repositories };
        return next;
      }
      const next = { ...current, [field]: value };
      return next;
    });
    setProjectFormErrors([]);
  };

  const handleRepositoryFormChange = (
    index: number,
    field: keyof ProjectRepositoryFormState,
    value: string | boolean,
  ) => {
    setProjectForm((current) => {
      const currentRepository = current.repositories[index];
      const previousSlug = currentRepository?.repoSlug ?? "";
      const repositories = current.repositories.map((repository, repositoryIndex) =>
        repositoryIndex === index ? { ...repository, [field]: value } : repository,
      );
      if (field === "isRepresentative" && value === true) {
        repositories.forEach((repository, repositoryIndex) => {
          if (repositoryIndex !== index) {
            repository.isRepresentative = false;
          }
        });
      }
      const representative =
        repositories.find((repository) => repository.isRepresentative)?.repoSlug ||
        current.representativeRepoSlug;
      const normalizedRepresentative =
        representative ||
        repositories.find((repository) => repository.repoSlug.trim() !== "")?.repoSlug ||
        "";
      const builds =
        field === "repoSlug"
          ? current.builds.map((build) => ({
              ...build,
              repositorySlug: build.repositorySlug === previousSlug ? String(value) : build.repositorySlug,
            }))
          : current.builds;
      return {
        ...current,
        repositories,
        representativeRepoSlug: normalizedRepresentative,
        builds,
      };
    });
    setProjectFormErrors([]);
  };

  const addRepositoryFormRow = () => {
    setProjectForm((current) => ({
      ...current,
      repositories: [
        ...current.repositories,
        {
          repoSlug: "",
          coverityProject: "",
          coverityStream: "",
          isRepresentative: false,
        },
      ],
    }));
    setProjectFormErrors([]);
  };

  const removeRepositoryFormRow = (index: number) => {
    setProjectForm((current) => {
      const repositories = current.repositories.filter((_, repositoryIndex) => repositoryIndex !== index);
      if (repositories.length === 0) {
        return {
          ...current,
          repositories: emptyProjectForm().repositories,
          representativeRepoSlug: "",
          builds: current.builds.map((build) => ({ ...build, repositorySlug: "" })),
        };
      }
      if (!repositories.some((repository) => repository.isRepresentative)) {
        const firstFilledIndex = repositories.findIndex((repository) => repository.repoSlug.trim() !== "");
        repositories[firstFilledIndex >= 0 ? firstFilledIndex : 0].isRepresentative = true;
      }
      const representativeRepoSlug =
        repositories.find((repository) => repository.isRepresentative)?.repoSlug || "";
      const validRepoSlugs = new Set(repositories.map((repository) => repository.repoSlug));
      const builds = current.builds.map((build) => ({
        ...build,
        repositorySlug: validRepoSlugs.has(build.repositorySlug) ? build.repositorySlug : representativeRepoSlug,
      }));
      return {
        ...current,
        repositories,
        representativeRepoSlug,
        builds,
      };
    });
    setProjectFormErrors([]);
  };

  const handleBuildFormChange = (
    index: number,
    field: keyof ProjectBuildFormState,
    value: string,
  ) => {
    setProjectForm((current) => ({
      ...current,
      builds: current.builds.map((build, buildIndex) => {
        if (buildIndex !== index) {
          return build;
        }

        const nextBuild = { ...build, [field]: value };

        if (field === "language") {
          if (!nextBuild.compiler.trim()) {
            nextBuild.compiler = preferredCompiler(nextBuild);
          }
          if (!nextBuild.runtimeStack.trim()) {
            nextBuild.runtimeStack = preferredRuntimeStack(nextBuild);
          }
        }

        if (field === "compiler") {
          if (!nextBuild.language.trim()) {
            nextBuild.language = preferredLanguage(nextBuild);
          }
          if (!nextBuild.runtimeStack.trim()) {
            nextBuild.runtimeStack = preferredRuntimeStack(nextBuild);
          }
        }

        if (field === "buildName" || field === "repositorySlug") {
          if (!nextBuild.buildId.trim()) {
            nextBuild.buildId = preferredBuildId(nextBuild);
          }
          if (!nextBuild.planKey.trim()) {
            nextBuild.planKey = preferredPlanKey(current.projectKey, nextBuild);
          }
        }

        return nextBuild;
      }),
    }));
    setProjectFormErrors([]);
  };

  const applyRecommendedBuildMeta = (index: number) => {
    setProjectForm((current) => ({
      ...current,
      builds: current.builds.map((build, buildIndex) =>
        buildIndex === index ? { ...build, ...recommendedBuildMeta(build) } : build,
      ),
    }));
    setProjectFormErrors([]);
  };

  const resetBuildMeta = (index: number) => {
    setProjectForm((current) => ({
      ...current,
      builds: current.builds.map((build, buildIndex) =>
        buildIndex === index
          ? {
              ...build,
              language: "",
              compiler: "",
              runtimeStack: "",
            }
          : build,
      ),
    }));
    setProjectFormErrors([]);
  };

  const applyRecommendedBuildIdentity = (index: number) => {
    setProjectForm((current) => ({
      ...current,
      builds: current.builds.map((build, buildIndex) =>
        buildIndex === index
          ? { ...build, ...recommendedBuildIdentity(current.projectKey, build) }
          : build,
      ),
    }));
    setProjectFormErrors([]);
  };

  const resetBuildIdentity = (index: number) => {
    setProjectForm((current) => ({
      ...current,
      builds: current.builds.map((build, buildIndex) =>
        buildIndex === index
          ? {
              ...build,
              buildId: "",
              planKey: "",
            }
          : build,
      ),
    }));
    setProjectFormErrors([]);
  };

  const addBuildFormRow = () => {
    setProjectForm((current) => ({
      ...current,
      builds: [
        ...current.builds,
        {
          buildName: "",
          language: "",
          compiler: "",
          runtimeStack: "",
          buildId: "",
          planKey: "",
          repositorySlug:
            current.repositories.find((repository) => repository.isRepresentative)?.repoSlug ||
            current.repositories[0]?.repoSlug ||
            "",
        },
      ],
    }));
    setProjectFormErrors([]);
  };

  const removeBuildFormRow = (index: number) => {
    setProjectForm((current) => ({
      ...current,
      builds:
        current.builds.length === 1
          ? emptyProjectForm().builds
          : current.builds.filter((_, buildIndex) => buildIndex !== index),
    }));
    setProjectFormErrors([]);
  };

  const handleProjectSubmit = async () => {
    const validationErrors = validateProjectForm(projectForm);
    if (validationErrors.length > 0) {
      setProjectFormErrors(validationErrors);
      setError("");
      setNotice("");
      return;
    }
    setSavingProject(true);
    setError("");
    setNotice("");
    setProjectFormErrors([]);
    try {
      const payload = {
        projectKey: projectForm.projectKey,
        jiraProjectKey: projectForm.projectKey,
        name: projectForm.name,
        ciProvider: projectForm.ciProvider,
        bitbucketProjectKey: projectForm.bitbucketProjectKey,
        representativeRepoSlug:
          projectForm.representativeRepoSlug ||
          projectForm.repositories.find((repository) => repository.isRepresentative)?.repoSlug ||
          projectForm.repositories[0]?.repoSlug ||
          "",
        repositories: projectForm.repositories.map((repository) => ({
          repoSlug: repository.repoSlug,
          coverityProject: repository.coverityProject,
          coverityStream: repository.coverityStream,
          isRepresentative: repository.isRepresentative,
        })),
        builds: projectForm.builds.map((build) => ({
          buildName: build.buildName,
          language: build.language,
          compiler: build.compiler,
          runtimeStack: build.runtimeStack,
          buildId: build.buildId,
          planKey: build.planKey,
          repositorySlug:
            build.repositorySlug ||
            projectForm.repositories.find((repository) => repository.isRepresentative)?.repoSlug ||
            "",
        })),
      };

      const savedProject =
        projectFormMode === "create"
          ? await createProject(payload)
          : await updateProject(projectForm.projectKey, payload);

      await loadProjects();
      await loadBuildPlans();
      setProjectFormMode("update");
      setSelectedKey(savedProject.projectKey);
      setProjectForm(projectToForm(savedProject));
      setNotice(projectFormMode === "create" ? "프로젝트를 등록했습니다." : "프로젝트를 수정했습니다.");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "프로젝트 저장에 실패했습니다.");
    } finally {
      setSavingProject(false);
    }
  };

  const handleCoverityFormChange = (field: keyof CoverityFormState, value: string | boolean) => {
    setCoverityForm((current) => ({ ...current, [field]: value }));
  };

  const handleBambooFormChange = (field: keyof BambooFormState, value: string) => {
    setBambooForm((current) => ({ ...current, [field]: value }));
  };

  const handleJenkinsFormChange = (field: keyof JenkinsFormState, value: string) => {
    setJenkinsForm((current) => ({ ...current, [field]: value }));
  };

  const handleGithubFormChange = (field: keyof GithubFormState, value: string) => {
    setGithubForm((current) => ({ ...current, [field]: value }));
  };

  const handleBitbucketFormChange = (field: keyof BitbucketFormState, value: string) => {
    setBitbucketForm((current) => ({ ...current, [field]: value }));
  };

  const handleGiteaFormChange = (field: keyof GiteaFormState, value: string) => {
    setGiteaForm((current) => ({ ...current, [field]: value }));
  };

  const handleSettingsSave = async () => {
    setSavingSettings(true);
    setError("");
    setNotice("");
    try {
      const saved = await updateCoveritySettings(coverityForm);
      setCoveritySettings(saved);
      setCoverityForm(coverityToForm(saved));
      setNotice("시스템 설정을 저장했습니다.");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "시스템 설정 저장에 실패했습니다.");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleBambooSettingsSave = async () => {
    setSavingSettings(true);
    setError("");
    setNotice("");
    try {
      const saved = await updateBambooSettings(bambooForm);
      setBambooSettings(saved);
      setBambooForm(bambooToForm(saved));
      setNotice("Bamboo 설정을 저장했습니다.");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Bamboo 설정 저장에 실패했습니다.");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleJenkinsSettingsSave = async () => {
    setSavingSettings(true);
    setError("");
    setNotice("");
    try {
      const saved = await updateJenkinsSettings(jenkinsForm);
      setJenkinsSettings(saved);
      setJenkinsForm(jenkinsToForm(saved));
      setNotice("Jenkins 설정을 저장했습니다.");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Jenkins 설정 저장에 실패했습니다.");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleGithubSettingsSave = async () => {
    setSavingSettings(true);
    setError("");
    setNotice("");
    try {
      const saved = await updateGithubSettings(githubForm);
      setGithubSettings(saved);
      setGithubForm(githubToForm(saved));
      setNotice("GitHub 설정을 저장했습니다.");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "GitHub 설정 저장에 실패했습니다.");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleBitbucketSettingsSave = async () => {
    setSavingSettings(true);
    setError("");
    setNotice("");
    try {
      const saved = await updateBitbucketSettings(bitbucketForm);
      setBitbucketSettings(saved);
      setBitbucketForm(bitbucketToForm(saved));
      setNotice("Bitbucket 설정을 저장했습니다.");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Bitbucket 설정 저장에 실패했습니다.");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleGiteaSettingsSave = async () => {
    setSavingSettings(true);
    setError("");
    setNotice("");
    try {
      const saved = await updateGiteaSettings(giteaForm);
      setGiteaSettings(saved);
      setGiteaForm(giteaToForm(saved));
      setNotice("Gitea 설정을 저장했습니다.");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Gitea 설정 저장에 실패했습니다.");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleInitializeDrafts = async () => {
    setInitializingDrafts(true);
    setError("");
    setNotice("");
    try {
      const summary = await initializeSpecsDrafts(true);
      setNotice(
        `Specs drafts 초기화 완료: initialized=${summary.initializedCount}, updated=${summary.updatedCount}, skipped=${summary.skippedCount}`,
      );
      await loadBuildPlans();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Specs drafts 초기화에 실패했습니다.");
    } finally {
      setInitializingDrafts(false);
    }
  };

  const handleModuleAction = async (action: "reload" | "activate" | "deactivate", versionId?: string) => {
    if (!selectedModuleId) {
      return;
    }
    setModuleActionLoading(true);
    setError("");
    setNotice("");
    try {
      if (action === "reload") {
        const summary = await reloadModules();
        await loadModules();
        await loadModuleLoadStatus();
        setNotice(
          `모듈 reload 완료: loaded=${summary.loadedCount}, invalid=${summary.invalidCount}, skipped=${summary.skippedCount}`,
        );
      } else if (action === "activate" && versionId) {
        await activateModule(selectedModuleId, versionId);
        await loadModules();
        setSelectedModule(await fetchModuleDetail(selectedModuleId));
        await loadModuleLoadStatus();
        setNotice("모듈 버전을 활성화했습니다.");
      } else if (action === "deactivate") {
        await deactivateModule(selectedModuleId);
        await loadModules();
        setSelectedModule(await fetchModuleDetail(selectedModuleId));
        await loadModuleLoadStatus();
        setNotice("모듈을 비활성화했습니다.");
      }
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "모듈 작업에 실패했습니다.");
    } finally {
      setModuleActionLoading(false);
    }
  };

  const handleModuleUpload = async () => {
    if (!moduleUploadForm.file) {
      setError("업로드할 파일을 선택해 주세요.");
      return;
    }
    setModuleActionLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await uploadModuleAsset({
        assetKind: moduleUploadForm.assetKind,
        providerScope: moduleUploadForm.providerScope,
        moduleId: moduleUploadForm.moduleId,
        activateAfterUpload: moduleUploadForm.activateAfterUpload,
        file: moduleUploadForm.file,
      });
      await loadModules();
      setSelectedModuleId(result.assetId);
      setSelectedModule(await fetchModuleDetail(result.assetId));
      await loadModuleLoadStatus();
      setNotice(
        `모듈 업로드 완료: validation=${result.validationStatus}, activated=${String(result.activated)}`,
      );
      setModuleUploadForm((current) => ({ ...current, file: null }));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "모듈 업로드에 실패했습니다.");
    } finally {
      setModuleActionLoading(false);
    }
  };

  const handleQueueFormChange = <K extends keyof QueueFormState>(key: K, value: QueueFormState[K]) => {
    setQueueForm((current) => ({ ...current, [key]: value }));
  };

  const refreshBambooPlan = async (planKey: string) => {
    const [definition, context, executions, status, detail, plans] = await Promise.all([
      fetchBuildPlanActiveDefinition(planKey),
      fetchBuildPlanPrepareContext(planKey),
      fetchBuildPlanExecutions(planKey),
      fetchBambooPlanStatus(planKey),
      fetchBambooPlanDetail(planKey),
      loadBuildPlans(),
    ]);
    setActiveDefinition(definition);
    setPrepareContext(context);
    setBuildPlanExecutions(executions);
    setBambooPlanStatus(status);
    setBambooPlanDetail(detail);
    setBuildPlans(plans);
  };

  const openBuildPlanWorkspace = (planKey: string) => {
    setWorkspace("build-plans");
    setSelectedPlanKey(planKey);
    setQuery("");
    setFilter("all");
  };

  const handleBambooPublish = async () => {
    if (!selectedBuildPlan) {
      return;
    }
    setBambooActionLoading(true);
    setBuildPlanError("");
    setBuildPlanNotice("");
    try {
      const result = await publishBambooSpecs(selectedBuildPlan.planKey);
      await refreshBambooPlan(selectedBuildPlan.planKey);
      setBuildPlanNotice(result.message);
    } catch (reason: unknown) {
      setBuildPlanError(reason instanceof Error ? reason.message : "Bamboo publish에 실패했습니다.");
    } finally {
      setBambooActionLoading(false);
    }
  };

  const handleBambooQueue = async () => {
    if (!selectedBuildPlan) {
      return;
    }
    setBambooActionLoading(true);
    setBuildPlanError("");
    setBuildPlanNotice("");
    try {
      const variables =
        queueForm.variableKey.trim() !== ""
          ? { [queueForm.variableKey.trim()]: queueForm.variableValue }
          : {};
      const result = await queueBambooPlan({
        planKey: selectedBuildPlan.planKey,
        stage: queueForm.stage,
        executeAllStages: queueForm.executeAllStages,
        customRevision: queueForm.customRevision,
        variables,
      });
      await refreshBambooPlan(selectedBuildPlan.planKey);
      setBuildPlanNotice(result.message);
      setQueueForm(emptyQueueForm());
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Bamboo queue 요청에 실패했습니다.";
      if (message.includes("maximum number of concurrent builds")) {
        setBuildPlanError("Bamboo 동시 실행 한도에 걸려 큐잉하지 못했습니다. 현재 실행 중인 빌드가 끝난 뒤 다시 시도해 주세요.");
      } else {
        setBuildPlanError(message);
      }
    } finally {
      setBambooActionLoading(false);
    }
  };

  const filteredProjects = projects.filter((project) => {
    const matchesQuery =
      query.trim() === "" ||
      [project.projectKey, project.name, project.representativeRepoSlug, project.bitbucketProjectKey]
        .join(" ")
        .toLowerCase()
        .includes(query.trim().toLowerCase());
    if (!matchesQuery) {
      return false;
    }
    if (filter === "attention") {
      return project.needsAttention;
    }
    if (filter === "healthy") {
      return !project.needsAttention;
    }
    return true;
  });

  const attentionCount = projects.filter((project) => project.needsAttention).length;
  const readyCount = projects.filter((project) => project.generationReady).length;
  const failedCount = projects.reduce((sum, project) => sum + project.failedBuildCount, 0);
  const selectedProjectMissingCoverityCount = selectedProject
    ? selectedProject.repositories.filter(
        (repository) => !repository.coverityProject || !repository.coverityStream,
      ).length
    : 0;
  const selectedProjectFailedBuildCount = selectedProject
    ? selectedProject.buildUnits.filter((buildUnit) => buildUnit.latestSuccess === false).length
    : 0;
  const selectedProjectTrackedBuildCount = selectedProject
    ? selectedProject.buildUnits.filter((buildUnit) => buildUnit.planKey || buildUnit.jobPath).length
    : 0;
  const selectedBuildPlanAnalysisCount = buildPlanExecutions.reduce(
    (sum, execution) => sum + execution.staticAnalysisResults.length,
    0,
  );
  const selectedBuildPlanFailedCount = buildPlanExecutions.filter((execution) => execution.success === false).length;
  const selectedBuildPlanPublishCount = bambooPlanDetail?.recentPublishExecutions.length ?? 0;
  const selectedBuildPlanStageCount = bambooPlanDetail?.stages.length ?? 0;
  const moduleFailureCount = moduleLoadStatus?.recentFailures.length ?? 0;
  const selectedModuleVersionCount = selectedModule?.versions.length ?? 0;
  const selectedModuleIssueCount = selectedModule?.recentIssues.length ?? 0;
  const ciConfiguredCount = [
    Boolean(bambooSettings?.serverUrl),
    Boolean(jenkinsSettings?.serverUrl),
  ].filter(Boolean).length;
  const settingsConfiguredCount = [
    Boolean(coveritySettings?.connectUrl),
    Boolean(bambooSettings?.serverUrl),
    Boolean(jenkinsSettings?.serverUrl),
    Boolean(githubSettings?.serverUrl),
    Boolean(bitbucketSettings?.serverUrl),
    Boolean(giteaSettings?.serverUrl),
  ].filter(Boolean).length;
  const filteredBuildPlans = buildPlans.filter((plan) => {
    const matchesQuery =
      query.trim() === "" ||
      [plan.projectKey, plan.buildName, plan.planKey, plan.buildId, plan.repositorySlug]
        .join(" ")
        .toLowerCase()
        .includes(query.trim().toLowerCase());
    if (!matchesQuery) {
      return false;
    }
    if (filter === "attention") {
      return !plan.repositorySlug || plan.latestSuccess === false || !plan.coverityProject;
    }
    if (filter === "healthy") {
      return !!plan.repositorySlug && plan.latestSuccess !== false && !!plan.coverityProject;
    }
    return true;
  });
  const filteredModules = modules.filter((module) => {
    const matchesQuery =
      query.trim() === "" ||
      [module.moduleId, module.displayName, module.assetKind, module.providerScope]
        .join(" ")
        .toLowerCase()
        .includes(query.trim().toLowerCase());
    if (!matchesQuery) {
      return false;
    }
    if (filter === "attention") {
      return module.status !== "active";
    }
    if (filter === "healthy") {
      return module.status === "active";
    }
    return true;
  });
  const selectedExecution =
    buildPlanExecutions.find((execution) => execution.buildExecutionId === selectedExecutionId) ?? null;
  const availableRepositorySlugs = projectForm.repositories
    .map((repository) => repository.repoSlug.trim())
    .filter((repoSlug, index, values) => repoSlug !== "" && values.indexOf(repoSlug) === index);
  const currentWorkspaceMeta = workspaceMeta[workspace];
  const bambooConfigured = Boolean(bambooSettings?.serverUrl);
  const bambooContextHealthy = bambooConfigured && !bambooUrlNeedsContextPath(bambooSettings?.serverUrl ?? "");
  const coverityConfigured = Boolean(coveritySettings?.connectUrl);
  const jenkinsConfigured = Boolean(jenkinsSettings?.serverUrl);
  const githubConfigured = Boolean(githubSettings?.serverUrl);
  const bitbucketConfigured = Boolean(bitbucketSettings?.serverUrl);
  const giteaConfigured = Boolean(giteaSettings?.serverUrl);
  const coverityCommitState = coveritySettings?.commitEnabled ? "commit on" : "commit off";
  const ciSystemItems: Array<{
    id: SettingsTarget;
    label: string;
    description: string;
    status: string;
  }> = [
    {
      id: "bamboo",
      label: "Bamboo",
      description: bambooConfigured
        ? bambooSettings?.tokenConfigured
          ? "server URL and auth token configured"
          : "server URL configured, auth pending"
        : "server URL and auth token",
      status: !bambooConfigured
        ? "missing"
        : bambooContextHealthy
          ? "context ok"
          : "context missing",
    },
    {
      id: "jenkins",
      label: "Jenkins",
      description: `${jenkinsSettings?.serverUrl || TEST_ENV.jenkinsUrl} / user ${jenkinsSettings?.username || "not set"}`,
      status: jenkinsConfigured ? "configured" : "missing",
    },
  ];
  const scmSystemItems: Array<{
    id: SettingsTarget;
    label: string;
    description: string;
    status: string;
  }> = [
    {
      id: "github",
      label: "GitHub",
      description: githubSettings?.serverUrl
        ? `${githubSettings.serverUrl}`
        : "server URL and auth token",
      status: githubConfigured ? "configured" : "optional scm",
    },
    {
      id: "bitbucket",
      label: "Bitbucket",
      description: bitbucketSettings?.serverUrl
        ? `${bitbucketSettings.serverUrl}`
        : "server URL and auth token",
      status: bitbucketConfigured ? "configured" : "project-linked",
    },
    {
      id: "gitea",
      label: "Gitea",
      description: giteaSettings?.serverUrl
        ? `${giteaSettings.serverUrl}`
        : "server URL and auth token",
      status: giteaConfigured ? "configured" : "local ready",
    },
  ];
  const analysisSystemItems: Array<{
    id: SettingsTarget;
    label: string;
    description: string;
    status: string;
  }> = [
    {
      id: "coverity",
      label: "Coverity",
      description: coverityConfigured
        ? `${coverityCommitState}, ${coveritySettings?.repositoryLinkageMode || "linkage pending"}`
        : "connect URL, cert policy, linkage mode",
      status: coverityConfigured ? coverityCommitState : "missing",
    },
  ];
  const sidebarMetricsByWorkspace: Record<WorkspaceMode, Array<{ label: string; value: string | number }>> = {
    projects: [
      { label: "catalog", value: projects.length },
      { label: "ready", value: readyCount },
      { label: "attention", value: attentionCount },
      { label: "failed units", value: failedCount },
    ],
    "build-plans": [
      { label: "plans", value: buildPlans.length },
      { label: "healthy", value: buildPlans.filter((plan) => plan.latestSuccess !== false).length },
      { label: "attention", value: buildPlans.filter((plan) => plan.latestSuccess === false || !plan.repositorySlug).length },
      { label: "definitions", value: buildPlans.reduce((sum, plan) => sum + (plan.buildInfoCount || 0), 0) },
    ],
    modules: [
      { label: "assets", value: modules.length },
      { label: "active", value: modules.filter((module) => module.status === "active").length },
      { label: "inactive", value: modules.filter((module) => module.status !== "active").length },
      { label: "failures", value: moduleFailureCount },
    ],
    settings: [
      { label: "ci tools", value: ciSystemItems.length },
      { label: "scm tools", value: scmSystemItems.length },
      { label: "analysis", value: analysisSystemItems.length },
      { label: "configured", value: `${settingsConfiguredCount}/6` },
    ],
    admin: [
      { label: "drafts", value: "action" },
      { label: "snapshot", value: moduleLoadStatus?.lastSnapshot?.status ?? "unknown" },
      { label: "active assets", value: moduleLoadStatus?.activeAssetCount ?? 0 },
      { label: "failures", value: moduleFailureCount },
    ],
  };
  const currentSidebarMetrics = sidebarMetricsByWorkspace[workspace];
  const settingsCategoryMeta: Record<SettingsTarget, { eyebrow: string; title: string; status: string }> = {
    bamboo: {
      eyebrow: "ci tool",
      title: "Bamboo Integration",
      status: bambooSettings?.serverUrl ? "configured" : "missing",
    },
    jenkins: {
      eyebrow: "ci tool",
      title: "Jenkins Integration",
      status: jenkinsConfigured ? "configured" : "missing",
    },
    github: {
      eyebrow: "scm integration",
      title: "GitHub Integration",
      status: githubConfigured ? "configured" : "optional",
    },
    bitbucket: {
      eyebrow: "scm integration",
      title: "Bitbucket Integration",
      status: bitbucketConfigured ? "configured" : "optional",
    },
    gitea: {
      eyebrow: "scm integration",
      title: "Gitea Integration",
      status: giteaConfigured ? "configured" : "optional",
    },
    coverity: {
      eyebrow: "analysis integration",
      title: "Coverity Integration",
      status: coveritySettings?.connectUrl ? "configured" : "missing",
    },
  };
  const currentSettingsMeta = settingsCategoryMeta[selectedSettingsTarget];
  const settingsReadinessClass =
    currentSettingsMeta.status === "configured"
      ? "is-ready"
      : currentSettingsMeta.status === "missing"
        ? ""
        : "is-muted";
  const settingsOverviewStats = [
    { label: "ci configured", value: `${ciConfiguredCount}/2` },
    { label: "scm available", value: scmSystemItems.length },
    { label: "analysis configured", value: coveritySettings?.connectUrl ? "1/1" : "0/1" },
    { label: "total systems", value: ciSystemItems.length + scmSystemItems.length + analysisSystemItems.length },
    { label: "configured", value: `${settingsConfiguredCount}/6` },
  ];
  const adminItems: Array<{
    id: "drafts" | "module-snapshot";
    label: string;
    description: string;
    status: string;
  }> = [
    {
      id: "drafts",
      label: "Specs Drafts",
      description: "initialize BuildInfo drafts from current metadata",
      status: "ready",
    },
    {
      id: "module-snapshot",
      label: "Module Snapshot",
      description: "reload status, failures, and active asset summary",
      status: moduleLoadStatus?.lastSnapshot?.status ?? "unknown",
    },
  ];
  const projectEditorSection = (
    <section className="detail-section project-editor-shell">
      <div className="composer-header">
        <div>
          <span className="eyebrow">project composer</span>
          <h3>{projectFormMode === "create" ? "새 프로젝트 초안" : "선택 프로젝트 편집"}</h3>
          <p className="detail-subcopy">
            기본 메타데이터, repositories, builds를 순서대로 채우고 마지막에 저장합니다.
          </p>
        </div>
        <div className="composer-state">
          {projectFormMode === "create" ? "draft open" : "editing selected"}
        </div>
      </div>
      <div className="panel-heading">
        <span>project editor</span>
        <strong>{projectFormMode === "create" ? "create draft" : "update selected"}</strong>
      </div>
      <div className="form-actions">
        {projectFormMode === "create" ? (
          <button type="button" className="ghost-button" onClick={closeNewProjectEditor}>
            Close Draft
          </button>
        ) : (
          <button type="button" className="ghost-button" onClick={editSelectedProject}>
            Sync Selected
          </button>
        )}
      </div>
      {projectFormErrors.length > 0 ? (
        <div className="inline-hint">
          {projectFormErrors.join(" ")}
        </div>
      ) : null}
      <div className="editor-form">
        <label>
          <span>project key</span>
          <input
            value={projectForm.projectKey}
            onChange={(event) => handleProjectFormChange("projectKey", event.target.value.toUpperCase())}
            disabled={projectFormMode === "update"}
          />
        </label>
        <label>
          <span>display name</span>
          <input
            value={projectForm.name}
            onChange={(event) => handleProjectFormChange("name", event.target.value)}
          />
        </label>
        <label>
          <span>ci provider</span>
          <input
            value={projectForm.ciProvider}
            onChange={(event) => handleProjectFormChange("ciProvider", event.target.value)}
          />
        </label>
        <label>
          <span>bitbucket key</span>
          <input
            value={projectForm.bitbucketProjectKey}
            onChange={(event) => handleProjectFormChange("bitbucketProjectKey", event.target.value.toUpperCase())}
          />
        </label>
        <label>
          <span>representative repo</span>
          <select
            value={projectForm.representativeRepoSlug}
            onChange={(event) => handleProjectFormChange("representativeRepoSlug", event.target.value)}
          >
            <option value="">Select repository</option>
            {availableRepositorySlugs.map((repoSlug) => (
              <option key={`representative-${repoSlug}`} value={repoSlug}>
                {repoSlug}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="composer-caption">
        project basics를 먼저 고정한 다음 repositories와 builds를 채우는 흐름이 가장 안정적입니다.
      </div>

      <section className="subform-section">
        <div className="panel-heading">
          <span>repositories</span>
          <strong>{projectForm.repositories.length}</strong>
        </div>
        <div className="subform-list">
          {projectForm.repositories.map((repository, index) => (
            <div key={`repo-${index}`} className="subform-card">
              <div className="panel-heading">
                <span>repo {index + 1}</span>
                <strong>{repository.isRepresentative ? "representative" : "linked"}</strong>
              </div>
              <div className="editor-form">
                <label>
                  <span>repository slug</span>
                  <input
                    value={repository.repoSlug}
                    onChange={(event) =>
                      handleRepositoryFormChange(index, "repoSlug", event.target.value)
                    }
                  />
                </label>
                <label>
                  <span>coverity project</span>
                  <input
                    value={repository.coverityProject}
                    onChange={(event) =>
                      handleRepositoryFormChange(index, "coverityProject", event.target.value)
                    }
                  />
                </label>
                <label>
                  <span>coverity stream</span>
                  <input
                    value={repository.coverityStream}
                    onChange={(event) =>
                      handleRepositoryFormChange(index, "coverityStream", event.target.value)
                    }
                  />
                </label>
                <label className="checkbox-field">
                  <span>representative</span>
                  <input
                    type="checkbox"
                    checked={repository.isRepresentative}
                    disabled={repository.isRepresentative}
                    onChange={(event) =>
                      handleRepositoryFormChange(index, "isRepresentative", event.target.checked)
                    }
                  />
                </label>
              </div>
              <div className="form-actions">
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => removeRepositoryFormRow(index)}
                  disabled={projectForm.repositories.length === 1}
                >
                  Remove Repo
                </button>
              </div>
            </div>
          ))}
        </div>
        <div className="form-actions">
          <button type="button" className="ghost-button" onClick={addRepositoryFormRow}>
            Add Repository
          </button>
        </div>
        <div className="inline-hint">
          대표 저장소는 다른 row를 체크해서 전환합니다. build의 `repository slug`는 아래 선택 목록으로만 연결됩니다.
        </div>
      </section>

      <section className="subform-section">
        <div className="panel-heading">
          <span>builds</span>
          <strong>{projectForm.builds.length}</strong>
        </div>
        <div className="subform-list">
          {projectForm.builds.map((build, index) => (
            <div key={`build-${index}`} className="subform-card">
              {(() => {
                const languageOptions = suggestedLanguages(build);
                const selectedLanguage = languageSelectValue(build);
                const compilerOptions = suggestedCompilers(build);
                const selectedCompiler = compilerSelectValue(build);
                const runtimeStackOptions = suggestedRuntimeStacks(build);
                const selectedRuntimeStack = runtimeStackSelectValue(build);
                const recommended = recommendedBuildMeta(build);
                const recommendedIdentity = recommendedBuildIdentity(projectForm.projectKey, build);
                const recommendationChanged =
                  build.language !== recommended.language ||
                  build.compiler !== recommended.compiler ||
                  build.runtimeStack !== recommended.runtimeStack;
                const identityChanged =
                  build.buildId !== recommendedIdentity.buildId ||
                  build.planKey !== recommendedIdentity.planKey;
                return (
                  <>
                    <div className="panel-heading">
                      <span>build {index + 1}</span>
                      <strong>{build.planKey || build.buildId || "draft"}</strong>
                    </div>
                    <div className="editor-form">
                      <label>
                        <span>build name</span>
                        <input
                          value={build.buildName}
                          onChange={(event) =>
                            handleBuildFormChange(index, "buildName", event.target.value)
                          }
                        />
                      </label>
                      <label>
                        <span>language</span>
                        <select
                          value={selectedLanguage}
                          onChange={(event) =>
                            handleBuildFormChange(
                              index,
                              "language",
                              event.target.value === CUSTOM_LANGUAGE ? build.language : event.target.value,
                            )
                          }
                        >
                          <option value="">Select language</option>
                          {languageOptions.map((language) => (
                            <option key={`language-${index}-${language}`} value={language}>
                              {language}
                            </option>
                          ))}
                          <option value={CUSTOM_LANGUAGE}>Custom input</option>
                        </select>
                      </label>
                      {selectedLanguage === CUSTOM_LANGUAGE ? (
                        <label className="span-two">
                          <span>custom language</span>
                          <input
                            value={build.language}
                            onChange={(event) =>
                              handleBuildFormChange(index, "language", event.target.value)
                            }
                            placeholder="예: kotlin, go, rust"
                          />
                        </label>
                      ) : null}
                      <label>
                        <span>compiler</span>
                        <select
                          value={selectedCompiler}
                          onChange={(event) =>
                            handleBuildFormChange(
                              index,
                              "compiler",
                              event.target.value === CUSTOM_COMPILER ? build.compiler : event.target.value,
                            )
                          }
                        >
                          <option value="">Select compiler</option>
                          {compilerOptions.map((compiler) => (
                            <option key={`compiler-${index}-${compiler}`} value={compiler}>
                              {compiler}
                            </option>
                          ))}
                          <option value={CUSTOM_COMPILER}>Custom input</option>
                        </select>
                      </label>
                      {selectedCompiler === CUSTOM_COMPILER ? (
                        <label className="span-two">
                          <span>custom compiler</span>
                          <input
                            value={build.compiler}
                            onChange={(event) =>
                              handleBuildFormChange(index, "compiler", event.target.value)
                            }
                            placeholder="예: bazel, pnpm, uv"
                          />
                        </label>
                      ) : null}
                      <label>
                        <span>runtime stack</span>
                        <select
                          value={selectedRuntimeStack}
                          onChange={(event) =>
                            handleBuildFormChange(
                              index,
                              "runtimeStack",
                              event.target.value === CUSTOM_RUNTIME_STACK ? build.runtimeStack : event.target.value,
                            )
                          }
                        >
                          <option value="">Select runtime</option>
                          {runtimeStackOptions.map((runtimeStack) => (
                            <option key={`runtime-${index}-${runtimeStack}`} value={runtimeStack}>
                              {runtimeStack}
                            </option>
                          ))}
                          <option value={CUSTOM_RUNTIME_STACK}>Custom input</option>
                        </select>
                      </label>
                      {selectedRuntimeStack === CUSTOM_RUNTIME_STACK ? (
                        <label className="span-two">
                          <span>custom runtime stack</span>
                          <input
                            value={build.runtimeStack}
                            onChange={(event) =>
                              handleBuildFormChange(index, "runtimeStack", event.target.value)
                            }
                            placeholder="예: java17-temurin, node22, python3.13"
                          />
                        </label>
                      ) : null}
                      <label>
                        <span>build id</span>
                        <input
                          value={build.buildId}
                          onChange={(event) =>
                            handleBuildFormChange(index, "buildId", event.target.value)
                          }
                        />
                      </label>
                      <label>
                        <span>plan key</span>
                        <input
                          value={build.planKey}
                          onChange={(event) =>
                            handleBuildFormChange(index, "planKey", event.target.value.toUpperCase())
                          }
                        />
                      </label>
                      <label>
                        <span>repository slug</span>
                        <select
                          value={build.repositorySlug}
                          onChange={(event) =>
                            handleBuildFormChange(index, "repositorySlug", event.target.value)
                          }
                        >
                          <option value="">Select repository</option>
                          {availableRepositorySlugs.map((repoSlug) => (
                            <option key={`build-${index}-${repoSlug}`} value={repoSlug}>
                              {repoSlug}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="form-actions build-meta-actions">
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => applyRecommendedBuildMeta(index)}
                        disabled={!recommendationChanged}
                      >
                        Apply Recommended
                      </button>
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => resetBuildMeta(index)}
                        disabled={!build.language && !build.compiler && !build.runtimeStack}
                      >
                        Reset Build Meta
                      </button>
                    </div>
                    <div className="compact-inline-hint">
                      recommended: {recommended.language || "-"} / {recommended.compiler || "-"} / {recommended.runtimeStack || "-"}
                    </div>
                    <div className="form-actions build-meta-actions">
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => applyRecommendedBuildIdentity(index)}
                        disabled={!identityChanged}
                      >
                        Apply Suggested IDs
                      </button>
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => resetBuildIdentity(index)}
                        disabled={!build.buildId && !build.planKey}
                      >
                        Reset IDs
                      </button>
                    </div>
                    <div className="compact-inline-hint">
                      suggested id: {recommendedIdentity.buildId || "-"} / {recommendedIdentity.planKey || "-"}
                    </div>
                    <div className="form-actions">
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => removeBuildFormRow(index)}
                      >
                        Remove Build
                      </button>
                    </div>
                  </>
                );
              })()}
            </div>
          ))}
        </div>
        <div className="form-actions">
          <button type="button" className="ghost-button" onClick={addBuildFormRow}>
            Add Build
          </button>
        </div>
        <div className="inline-hint">
          입력 기준은 `language / compiler / runtime stack`입니다. `plan key`와 `build id`는 각 build마다 고유해야 합니다.
        </div>
      </section>
      <div className="form-actions">
        <button
          type="button"
          className="primary-button"
          onClick={handleProjectSubmit}
          disabled={savingProject}
        >
          {savingProject ? "Saving..." : projectFormMode === "create" ? "Create Project" : "Update Project"}
        </button>
      </div>
    </section>
  );
  const moduleUploadSection = (
    <section className="detail-section project-editor-shell">
      <div className="composer-header">
        <div>
          <span className="eyebrow">module composer</span>
          <h3>새 모듈 자산 업로드</h3>
          <p className="detail-subcopy">
            registry snapshot과 분리된 작성 패널입니다. asset kind, scope, module id를 정한 뒤 파일을 올립니다.
          </p>
        </div>
        <div className="composer-state">
          {moduleUploadForm.file ? "file attached" : "awaiting file"}
        </div>
      </div>
      <div className="panel-heading">
        <span>upload module</span>
        <strong>manual</strong>
      </div>
      <div className="editor-form settings-form">
        <label>
          <span>asset kind</span>
          <input
            value={moduleUploadForm.assetKind}
            onChange={(event) =>
              setModuleUploadForm((current) => ({ ...current, assetKind: event.target.value }))
            }
          />
        </label>
        <label>
          <span>provider scope</span>
          <input
            value={moduleUploadForm.providerScope}
            onChange={(event) =>
              setModuleUploadForm((current) => ({ ...current, providerScope: event.target.value }))
            }
          />
        </label>
        <label>
          <span>module id</span>
          <input
            value={moduleUploadForm.moduleId}
            onChange={(event) =>
              setModuleUploadForm((current) => ({ ...current, moduleId: event.target.value }))
            }
          />
        </label>
        <label className="checkbox-field">
          <span>activate after upload</span>
          <input
            type="checkbox"
            checked={moduleUploadForm.activateAfterUpload}
            onChange={(event) =>
              setModuleUploadForm((current) => ({
                ...current,
                activateAfterUpload: event.target.checked,
              }))
            }
          />
        </label>
        <label className="file-field span-two">
          <span>source file</span>
          <input
            type="file"
            onChange={(event) =>
              setModuleUploadForm((current) => ({
                ...current,
                file: event.target.files?.[0] ?? null,
              }))
            }
          />
        </label>
      </div>
      <div className="composer-caption">
        upload 이후 활성화 여부는 selected module 패널과 reload snapshot에서 바로 확인할 수 있습니다.
      </div>
      <div className="form-actions">
        <button
          type="button"
          className="ghost-button"
          onClick={() => setShowModuleComposer(false)}
        >
          Close Composer
        </button>
        <button
          type="button"
          className="primary-button"
          onClick={handleModuleUpload}
          disabled={moduleActionLoading}
        >
          {moduleActionLoading ? "Working..." : "Upload Module"}
        </button>
      </div>
    </section>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block reveal reveal-1">
          <span className="eyebrow">ci operations</span>
          <h1>Spec Console</h1>
          <p>프로젝트 메타데이터, 플랜 상태, 모듈 자산을 같은 워크벤치에서 운영합니다.</p>
        </div>

        <div className="summary-stack reveal reveal-2">
          {currentSidebarMetrics.map((metric) => (
            <section key={`${workspace}-${metric.label}`}>
              <span className="metric-label">{metric.label}</span>
              <strong>{metric.value}</strong>
            </section>
          ))}
        </div>

        <div className="sidebar-note reveal reveal-3">
          <p>왼쪽은 탐색, 가운데는 목록, 오른쪽은 inspector입니다. 작성 흐름은 상단 composer로 분리합니다.</p>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar reveal reveal-1">
          <div>
            <span className="eyebrow">{currentWorkspaceMeta.eyebrow}</span>
            <h2>{currentWorkspaceMeta.title}</h2>
            <p className="topbar-copy">{currentWorkspaceMeta.description}</p>
          </div>
          <div className="status-pill">{loading ? "syncing" : "live from rust api"}</div>
        </header>

        <section className={`toolbar reveal reveal-2 ${workspace === "settings" || workspace === "admin" ? "toolbar-compact" : ""}`}>
          <div className="workspace-switch" role="tablist" aria-label="작업면 전환">
            <button
              type="button"
              className={workspace === "projects" ? "is-active" : ""}
              onClick={() => setWorkspace("projects")}
            >
              Projects
            </button>
            <button
              type="button"
              className={workspace === "build-plans" ? "is-active" : ""}
              onClick={() => setWorkspace("build-plans")}
            >
              Build Plans
            </button>
            <button
              type="button"
              className={workspace === "modules" ? "is-active" : ""}
              onClick={() => setWorkspace("modules")}
            >
              Modules
            </button>
            <button
              type="button"
              className={workspace === "settings" ? "is-active" : ""}
              onClick={() => setWorkspace("settings")}
            >
              Settings
            </button>
            <button
              type="button"
              className={workspace === "admin" ? "is-active" : ""}
              onClick={() => setWorkspace("admin")}
            >
              Admin
            </button>
          </div>
          {workspace !== "settings" && workspace !== "admin" ? (
            <label className="search-field">
              <span>검색</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={workspaceSearchPlaceholder[workspace]}
              />
            </label>
          ) : null}
          {workspace !== "settings" && workspace !== "admin" ? (
            <div className="filter-strip" role="tablist" aria-label="프로젝트 상태 필터">
              {filterLabels.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={item.id === filter ? "is-active" : ""}
                  onClick={() => setFilter(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}
          {workspace === "projects" ? (
            <button type="button" className="primary-button toolbar-button" onClick={startNewProject}>
              New Project
            </button>
          ) : workspace === "modules" ? (
            <button
              type="button"
              className="primary-button toolbar-button"
              onClick={() => setShowModuleComposer(true)}
            >
              Upload Module
            </button>
          ) : null}
        </section>

        {error ? <div className="error-banner reveal reveal-2">{error}</div> : null}
        {notice ? <div className="notice-banner reveal reveal-2">{notice}</div> : null}
        {workspace === "build-plans" && buildPlanError ? (
          <div className="error-banner reveal reveal-2">{buildPlanError}</div>
        ) : null}
        {workspace === "build-plans" && buildPlanNotice ? (
          <div className="notice-banner reveal reveal-2">{buildPlanNotice}</div>
        ) : null}
        {workspace === "projects" && projectFormMode === "create" ? (
          <section className="floating-editor-panel reveal reveal-2">
            {projectEditorSection}
          </section>
        ) : null}
        {workspace === "modules" && showModuleComposer ? (
          <section className="floating-editor-panel reveal reveal-2">
            {moduleUploadSection}
          </section>
        ) : null}
        {workspace === "settings" ? (
          <section className="floating-editor-panel reveal reveal-2">
            <div className="panel-heading">
              <span>systems overview</span>
              <strong>{ciSystemItems.length + scmSystemItems.length + analysisSystemItems.length} targets</strong>
            </div>
            <p className="section-copy compact-section-copy">
              전체 외부 시스템 현황은 여기서 먼저 읽고, 아래 workspace에서는 선택한 시스템의 연결 기준과 설정 항목만 다룹니다.
            </p>
            <div className="kpi-strip compact-kpi-strip wide-kpi-strip">
              {settingsOverviewStats.map((stat) => (
                <article key={stat.label}>
                  <span>{stat.label}</span>
                  <strong>{stat.value}</strong>
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {workspace === "admin" ? (
          <section className="floating-editor-panel reveal reveal-2">
            <div className="panel-heading">
              <span>admin overview</span>
              <strong>{adminItems.length} operations</strong>
            </div>
            <div className="kpi-strip compact-kpi-strip wide-kpi-strip">
              <article>
                <span>drafts</span>
                <strong>{initializingDrafts ? "running" : "ready"}</strong>
              </article>
              <article>
                <span>snapshot</span>
                <strong>{moduleLoadStatus?.lastSnapshot?.status ?? "unknown"}</strong>
              </article>
              <article>
                <span>active assets</span>
                <strong>{moduleLoadStatus?.activeAssetCount ?? 0}</strong>
              </article>
              <article>
                <span>failures</span>
                <strong>{moduleFailureCount}</strong>
              </article>
            </div>
          </section>
        ) : null}

        <section className="workspace-grid">
          {workspace === "projects" ? (
            <>
              <div className="project-list-panel reveal reveal-2">
                <div className="panel-heading">
                  <span>project register</span>
                  <strong>{filteredProjects.length} visible</strong>
                </div>

                <div className="project-list">
                  {filteredProjects.map((project, index) => (
                    <button
                      key={project.projectKey}
                      type="button"
                      className={`project-row ${project.projectKey === selectedKey ? "is-selected" : ""}`}
                      onClick={() => setSelectedKey(project.projectKey)}
                      style={{ animationDelay: `${120 + index * 36}ms` }}
                    >
                      <div className="project-row-head">
                        <strong>{project.projectKey}</strong>
                        <span>{project.ciProvider}</span>
                      </div>
                      <p>{project.name}</p>
                      <div className="project-row-meta">
                        <span>{project.representativeRepoSlug || "repo pending"}</span>
                        <span>{formatIssueLabel(project)}</span>
                      </div>
                      <div className="project-row-kpis">
                        <span className={`row-state ${project.generationReady ? "is-ok" : "is-warn"}`}>
                          {project.generationReady ? "ready" : "needs work"}
                        </span>
                        <span>{project.buildCount} builds</span>
                        <span>{project.failedBuildCount} failed</span>
                      </div>
                    </button>
                  ))}

                  {!loading && filteredProjects.length === 0 ? (
                    <div className="empty-state">조건에 맞는 프로젝트가 없습니다.</div>
                  ) : null}
                </div>
              </div>

              <div className="project-detail-panel reveal reveal-3">
                {detailLoading ? (
                  <div className="detail-placeholder">프로젝트 상세를 불러오는 중입니다.</div>
                ) : selectedProject ? (
                  <>
                    <div className="detail-header">
                      <div>
                        <span className="eyebrow">{selectedProject.ciProvider}</span>
                        <h3>{selectedProject.name}</h3>
                        <p className="detail-subcopy">
                          {selectedProject.projectKey} / {selectedProject.representativeRepoSlug || "repo pending"} / {selectedProject.bitbucketProjectKey || "bitbucket pending"}
                        </p>
                      </div>
                      <div className={`readiness-badge ${selectedProject.generation.generationReady ? "is-ready" : ""}`}>
                        {selectedProject.generation.generationReady ? "generation ready" : "needs metadata"}
                      </div>
                    </div>

                    <section className="kpi-strip">
                      <article>
                        <span className="metric-label">ready builds</span>
                        <strong>{selectedProject.generation.readyBuildCount}</strong>
                      </article>
                      <article>
                        <span className="metric-label">active defs</span>
                        <strong>{selectedProject.generation.activeDefinitionCount}</strong>
                      </article>
                      <article>
                        <span className="metric-label">missing coverity</span>
                        <strong>{selectedProjectMissingCoverityCount}</strong>
                      </article>
                      <article>
                        <span className="metric-label">failed units</span>
                        <strong>{selectedProjectFailedBuildCount}</strong>
                      </article>
                      <article>
                        <span className="metric-label">tracked plans</span>
                        <strong>{selectedProjectTrackedBuildCount}</strong>
                      </article>
                    </section>

                    <section className="detail-section section-cluster">
                      <div className="panel-heading">
                        <span>project overview</span>
                        <strong>{selectedProject.projectKey}</strong>
                      </div>
                      <p className="section-copy">
                        기본 메타데이터와 generation readiness를 먼저 읽는 구획입니다. 이 단계에서 누락 메타데이터와 소유 정보를 바로 확인합니다.
                      </p>
                      <div className="detail-grid detail-grid-asymmetric">
                        <section>
                          <span className="section-label">identity</span>
                          <dl>
                            <div>
                              <dt>project key</dt>
                              <dd>{selectedProject.projectKey}</dd>
                            </div>
                            <div>
                              <dt>bitbucket key</dt>
                              <dd>{selectedProject.bitbucketProjectKey || "-"}</dd>
                            </div>
                            <div>
                              <dt>owner team</dt>
                              <dd>{selectedProject.ownerTeam || "-"}</dd>
                            </div>
                            <div>
                              <dt>service type</dt>
                              <dd>{selectedProject.serviceType || "-"}</dd>
                            </div>
                          </dl>
                        </section>

                        <section>
                          <span className="section-label">readiness issues</span>
                          <ul className="issue-list">
                            {(selectedProject.generation.generationReadinessIssues.length > 0
                              ? selectedProject.generation.generationReadinessIssues
                              : ["이슈 없음"]
                            ).map((issue) => (
                              <li key={issue}>{issue}</li>
                            ))}
                          </ul>
                        </section>
                      </div>
                    </section>

                    <section className="detail-section section-cluster">
                      <div className="panel-heading">
                        <span>delivery topology</span>
                        <strong>{selectedProject.buildUnits.length} build units</strong>
                      </div>
                      <p className="section-copy">
                        저장소 연결과 build unit 추적 상태를 같은 구획에 배치했습니다. representative repo, coverity 연결, plan 추적 여부를 함께 읽습니다.
                      </p>
                      <div className="detail-grid detail-grid-asymmetric">
                        <section>
                          <div className="panel-heading">
                            <span>repositories</span>
                            <strong>{selectedProject.repositories.length}</strong>
                          </div>
                          <div className="line-list">
                            {selectedProject.repositories.map((repository) => (
                              <article key={repository.repoSlug} className="line-item">
                                <div>
                                  <strong>{repository.repoSlug}</strong>
                                  <span>{repository.defaultBranch || "branch pending"}</span>
                                </div>
                                <div>
                                  <span>{repository.coverityStream || "coverity pending"}</span>
                                  <span>{repository.isRepresentative ? "representative" : repository.repositoryProvider}</span>
                                </div>
                              </article>
                            ))}
                          </div>
                        </section>

                        <section>
                          <div className="panel-heading">
                            <span>build units</span>
                            <strong>{selectedProject.buildUnits.length}</strong>
                          </div>
                          <div className="line-list">
                            {selectedProject.buildUnits.map((buildUnit) => (
                              <article key={buildUnit.externalKey} className="line-item">
                                <div>
                                  <strong>{buildUnit.displayName || buildUnit.externalKey}</strong>
                                  <span>{buildUnit.planKey || buildUnit.jobPath || buildUnit.externalKey}</span>
                                </div>
                                <div>
                                  <span>{buildUnit.repositorySlug || "unlinked"}</span>
                                  {buildUnit.planKey ? (
                                    <button
                                      type="button"
                                      className="inline-link-button"
                                      onClick={() => openBuildPlanWorkspace(buildUnit.planKey)}
                                    >
                                      Open Plan
                                    </button>
                                  ) : (
                                    <span>{buildUnit.latestSuccess === false ? "failed" : "tracked"}</span>
                                  )}
                                </div>
                              </article>
                            ))}
                          </div>
                        </section>
                      </div>
                    </section>

                    {projectFormMode === "update" ? projectEditorSection : null}
                  </>
                ) : (
                  <div className="detail-placeholder">표시할 프로젝트가 없습니다.</div>
                )}
              </div>
            </>
          ) : workspace === "build-plans" ? (
            <>
              <div className="project-list-panel reveal reveal-2">
                <div className="panel-heading">
                  <span>build plans</span>
                  <strong>{filteredBuildPlans.length} visible</strong>
                </div>
                <div className="project-list">
                  {filteredBuildPlans.map((plan, index) => (
                    <button
                      key={`${plan.projectKey}:${plan.planKey}`}
                      type="button"
                      className={`project-row build-plan-row ${plan.planKey === selectedPlanKey ? "is-selected" : ""}`}
                      onClick={() => setSelectedPlanKey(plan.planKey)}
                      style={{ animationDelay: `${120 + index * 28}ms` }}
                    >
                      <div className="project-row-head">
                        <strong>{plan.planKey}</strong>
                        <span>{plan.ciProvider}</span>
                      </div>
                      <p>{plan.buildName}</p>
                      <div className="project-row-kpis">
                        <span className={`row-state ${plan.latestSuccess === false || !plan.repositorySlug ? "is-warn" : "is-ok"}`}>
                          {plan.latestSuccess === false ? "needs attention" : !plan.repositorySlug ? "repo pending" : "tracked"}
                        </span>
                        <span>{plan.language || "lang pending"}</span>
                        <span>{plan.compiler || "compiler pending"}</span>
                        <span>{plan.runtimeStack || "runtime pending"}</span>
                      </div>
                      <div className="project-row-meta">
                        <span>{plan.repositorySlug || "repo pending"}</span>
                        <span>{plan.latestSuccess === false ? "failed" : plan.resultStatus || "idle"}</span>
                      </div>
                    </button>
                  ))}
                  {!loading && filteredBuildPlans.length === 0 ? (
                    <div className="empty-state">조건에 맞는 빌드 플랜이 없습니다.</div>
                  ) : null}
                </div>
              </div>

              <div className="project-detail-panel reveal reveal-3">
                {selectedBuildPlan ? (
                  <>
                    <div className="detail-header">
                      <div>
                        <span className="eyebrow">bamboo build plan</span>
                        <h3>{selectedBuildPlan.buildName}</h3>
                        <p className="detail-subcopy">
                          {selectedBuildPlan.projectKey} / {selectedBuildPlan.repositorySlug || "repo pending"} 기준 실행 상태와
                          스펙 publish 흐름을 한곳에서 관리합니다.
                        </p>
                      </div>
                      <div className={`readiness-badge ${bambooPlanStatus?.exists ? "is-ready" : ""}`}>
                        {bambooLoading ? "syncing" : bambooPlanStatus?.exists ? "registered" : "pending"}
                      </div>
                    </div>

                    <div className="kpi-strip">
                      <article>
                        <span>registered</span>
                        <strong>{bambooPlanStatus?.exists ? "yes" : "no"}</strong>
                      </article>
                      <article>
                        <span>building</span>
                        <strong>{bambooPlanStatus?.building ? "live" : "idle"}</strong>
                      </article>
                      <article>
                        <span>executions</span>
                        <strong>{buildPlanExecutions.length}</strong>
                      </article>
                      <article>
                        <span>analysis runs</span>
                        <strong>{selectedBuildPlanAnalysisCount}</strong>
                      </article>
                      <article>
                        <span>publishes</span>
                        <strong>{selectedBuildPlanPublishCount}</strong>
                      </article>
                    </div>

                    <div className="detail-grid">
                      <section>
                        <div className="panel-heading">
                          <span>control room</span>
                          <strong>{selectedBuildPlan.planKey}</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>project / repo</strong>
                              <span>{selectedBuildPlan.projectKey} / {selectedBuildPlan.repositorySlug || "repo pending"}</span>
                            </div>
                            <div>
                              <span>{selectedBuildPlan.buildId}</span>
                              <span>{selectedBuildPlan.compiler || "compiler pending"}</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>latest result</strong>
                              <span>{bambooPlanStatus?.message || "Bamboo 상태를 불러오는 중입니다."}</span>
                            </div>
                            <div>
                              <span>{bambooPlanStatus?.latestResultState || selectedBuildPlan.resultStatus || "idle"}</span>
                              <span>{bambooPlanStatus?.latestBuildNumber || selectedBuildPlan.latestVersion || "-"}</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>attention</strong>
                              <span>실패 execution과 stage 구성을 같이 확인합니다.</span>
                            </div>
                            <div>
                              <span>{selectedBuildPlanFailedCount} failed</span>
                              <span>{selectedBuildPlanStageCount} stages</span>
                            </div>
                          </article>
                        </div>
                        <div className="form-actions">
                          {bambooPlanStatus?.planUrl ? (
                            <a className="ghost-button action-link" href={bambooPlanStatus.planUrl} target="_blank" rel="noreferrer">
                              Open Bamboo
                            </a>
                          ) : null}
                          <button
                            type="button"
                            className="primary-button"
                            onClick={handleBambooPublish}
                            disabled={bambooActionLoading}
                          >
                            {bambooActionLoading ? "Working..." : "Publish Specs"}
                          </button>
                        </div>
                      </section>

                      <section>
                        <div className="panel-heading">
                          <span>queue build</span>
                          <strong>{bambooPlanStatus?.building ? "running" : "ready"}</strong>
                        </div>
                        <div className="editor-form">
                          <label>
                            <span>stage</span>
                            <input
                              value={queueForm.stage}
                              onChange={(event) => handleQueueFormChange("stage", event.target.value)}
                              placeholder="optional"
                            />
                          </label>
                          <label>
                            <span>custom revision</span>
                            <input
                              value={queueForm.customRevision}
                              onChange={(event) => handleQueueFormChange("customRevision", event.target.value)}
                              placeholder="optional commit or branch"
                            />
                          </label>
                          <label>
                            <span>variable key</span>
                            <input
                              value={queueForm.variableKey}
                              onChange={(event) => handleQueueFormChange("variableKey", event.target.value)}
                              placeholder="custom.flag"
                            />
                          </label>
                          <label>
                            <span>variable value</span>
                            <input
                              value={queueForm.variableValue}
                              onChange={(event) => handleQueueFormChange("variableValue", event.target.value)}
                              placeholder="yes"
                            />
                          </label>
                          <label className="checkbox-field">
                            <span>execute all stages</span>
                            <input
                              type="checkbox"
                              checked={queueForm.executeAllStages}
                              onChange={(event) => handleQueueFormChange("executeAllStages", event.target.checked)}
                            />
                          </label>
                        </div>
                        <div className="form-actions">
                          <button
                            type="button"
                            className="ghost-button"
                            onClick={handleBambooQueue}
                            disabled={bambooActionLoading}
                          >
                            Queue Build
                          </button>
                        </div>
                      </section>
                    </div>

                    <section className="detail-section section-cluster">
                      <div className="panel-heading">
                        <span>definition context</span>
                        <strong>{activeDefinition?.definition.language || selectedBuildPlan.language}</strong>
                      </div>
                      <p className="section-copy">
                        활성 정의와 prepare context를 한 구획에서 점검해 publish 전에 입력 메타데이터와 런타임 전제를 빠르게 확인합니다.
                      </p>
                      <div className="detail-grid detail-grid-asymmetric">
                        <section>
                          <div className="panel-heading">
                            <span>definition preview</span>
                            <strong>{activeDefinition?.definition.compiler || selectedBuildPlan.compiler || "pending"}</strong>
                          </div>
                          <div className="line-list">
                            <article className="line-item">
                              <div>
                                <strong>repository</strong>
                                <span>
                                  {activeDefinition?.definition.repository.projectKey || selectedBuildPlan.projectKey}
                                  {" / "}
                                  {activeDefinition?.definition.repository.repoSlug || selectedBuildPlan.repositorySlug || "repo pending"}
                                </span>
                              </div>
                              <div>
                                <span>{activeDefinition?.definition.requirements.os || "os pending"}</span>
                                <span>{activeDefinition?.definition.compiler || selectedBuildPlan.compiler}</span>
                              </div>
                            </article>
                            <article className="line-item">
                              <div>
                                <strong>prepare</strong>
                                <span>{activeDefinition?.definition.build.prepareCommand || "미지정"}</span>
                              </div>
                              <div>
                                <span>{activeDefinition?.definition.build.subPath || "."}</span>
                                <span>v{activeDefinition?.definitionVersion || "?"}</span>
                              </div>
                            </article>
                            <article className="line-item">
                              <div>
                                <strong>build</strong>
                                <span>{activeDefinition?.definition.build.buildCommand || "미지정"}</span>
                              </div>
                              <div>
                                <span>
                                  {(activeDefinition?.definition.build.runtimeRequirements.commands ?? []).join(", ") || "runtime pending"}
                                </span>
                              </div>
                            </article>
                          </div>
                        </section>

                        <section>
                          <div className="panel-heading">
                            <span>prepare context</span>
                            <strong>{Object.keys(prepareContext?.variables ?? {}).length} vars</strong>
                          </div>
                          <div className="line-list">
                            <article className="line-item">
                              <div>
                                <strong>current repository</strong>
                                <span>{prepareContext?.currentRepository.repoSlug || selectedBuildPlan.repositorySlug || "repo pending"}</span>
                              </div>
                              <div>
                                <span>{prepareContext?.currentRepository.linkageMode || "linked"}</span>
                                <span>{prepareContext?.currentRepository.applicationLink || "app link pending"}</span>
                              </div>
                            </article>
                            <article className="line-item">
                              <div>
                                <strong>clone url</strong>
                                <span>{prepareContext?.currentRepository.cloneUrl || "미지정"}</span>
                              </div>
                              <div>
                                <span>{prepareContext?.project.jiraProjectKey || "-"}</span>
                                <span>{prepareContext?.project.bitbucketProjectKey || "-"}</span>
                              </div>
                            </article>
                            <article className="line-item">
                              <div>
                                <strong>variables snapshot</strong>
                                <span>
                                  {Object.entries(prepareContext?.variables ?? {})
                                    .slice(0, 3)
                                    .map(([key, value]) => `${key}=${value}`)
                                    .join(" · ") || "변수 없음"}
                                </span>
                              </div>
                              <div>
                                <span>{prepareContext?.repositories.length ?? 0} repos</span>
                              </div>
                            </article>
                          </div>
                        </section>
                      </div>
                    </section>

                    <section className="detail-section section-cluster">
                      <div className="panel-heading">
                        <span>execution analysis</span>
                        <strong>{buildPlanExecutions.length} runs</strong>
                      </div>
                      <p className="section-copy">
                        최근 실행 이력과 선택된 execution 분석 결과를 분리해 보여줍니다. 실패 상태와 정적분석 결과를 먼저 읽고 metrics는 아래에서 확인합니다.
                      </p>
                      <div className="detail-grid detail-grid-asymmetric">
                        <section>
                          <div className="panel-heading">
                            <span>executions</span>
                            <strong>{buildPlanExecutions.length}</strong>
                          </div>
                          <div className="line-list">
                            {buildPlanExecutions.length > 0 ? (
                              buildPlanExecutions.slice(0, 6).map((execution) => (
                                <button
                                  key={execution.buildExecutionId}
                                  type="button"
                                  className={`line-item execution-row ${execution.buildExecutionId === selectedExecutionId ? "is-selected" : ""}`}
                                  onClick={() => setSelectedExecutionId(execution.buildExecutionId)}
                                >
                                  <div>
                                    <strong>{execution.resultStatus || (execution.success ? "successful" : "pending")}</strong>
                                    <span>{execution.summaryMessage || execution.buildKey || "summary pending"}</span>
                                  </div>
                                  <div>
                                    <span>{execution.version || `#${execution.buildNumber}`}</span>
                                    <span>
                                      {execution.staticAnalysisResults.length > 0
                                        ? `${execution.staticAnalysisResults.length} analysis`
                                        : execution.finishedAt || execution.startedAt
                                          ? new Date(execution.finishedAt || execution.startedAt).toLocaleString()
                                          : "-"}
                                    </span>
                                  </div>
                                  {execution.staticAnalysisResults.length > 0 ? (
                                    <div className="analysis-list">
                                      {execution.staticAnalysisResults.map((result) => (
                                        <div key={`${execution.buildExecutionId}:${result.toolName}`} className="analysis-chip">
                                          <strong>{result.toolName}</strong>
                                          <span>{result.status || "unknown"}</span>
                                          <span>{result.summary || "summary pending"}</span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
                                </button>
                              ))
                            ) : (
                              <div className="detail-placeholder compact-placeholder">아직 수집된 실행 이력이 없습니다.</div>
                            )}
                          </div>
                        </section>

                        <section>
                          <div className="panel-heading">
                            <span>execution detail</span>
                            <strong>{selectedExecution?.buildKey || selectedExecution?.buildExecutionId || "none"}</strong>
                          </div>
                          {selectedExecution ? (
                            <>
                              <div className="line-list">
                                <article className="line-item">
                                  <div>
                                    <strong>identity</strong>
                                    <span>{selectedExecution.version || `#${selectedExecution.buildNumber}`}</span>
                                  </div>
                                  <div>
                                    <span>{selectedExecution.commitHash || "commit pending"}</span>
                                    <span>{selectedExecution.resultStatus || "status pending"}</span>
                                  </div>
                                </article>
                                <article className="line-item">
                                  <div>
                                    <strong>timeline</strong>
                                    <span>{selectedExecution.startedAt ? new Date(selectedExecution.startedAt).toLocaleString() : "start pending"}</span>
                                  </div>
                                  <div>
                                    <span>{selectedExecution.finishedAt ? new Date(selectedExecution.finishedAt).toLocaleString() : "finish pending"}</span>
                                  </div>
                                </article>
                                <article className="line-item">
                                  <div>
                                    <strong>stage / job / task</strong>
                                    <span>
                                      {[selectedExecution.stageName, selectedExecution.jobName, selectedExecution.taskName]
                                        .filter(Boolean)
                                        .join(" / ") || "not recorded"}
                                    </span>
                                  </div>
                                  <div>
                                    <span>{selectedExecution.staticAnalysisResults.length} analysis results</span>
                                  </div>
                                </article>
                              </div>
                              {selectedExecution.staticAnalysisResults.length > 0 ? (
                                <div className="analysis-result-stack">
                                  {selectedExecution.staticAnalysisResults.map((result) => {
                                    const metricRows = flattenMetrics(result.metricsJson);
                                    return (
                                      <section
                                        key={`${selectedExecution.buildExecutionId}:${result.toolName}`}
                                        className="analysis-result-card"
                                      >
                                        <div className="panel-heading">
                                          <span>{result.toolName}</span>
                                          <strong>{result.status || "unknown"}</strong>
                                        </div>
                                        <p className="analysis-summary">{result.summary || "summary pending"}</p>
                                        {metricRows.length > 0 ? (
                                          <div className="metrics-table-wrap">
                                            <table className="metrics-table">
                                              <thead>
                                                <tr>
                                                  <th>metric</th>
                                                  <th>value</th>
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {metricRows.map((metric) => (
                                                  <tr key={`${result.toolName}:${metric.key}`}>
                                                    <td>{metric.key}</td>
                                                    <td>{metric.value}</td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          </div>
                                        ) : (
                                          <div className="detail-placeholder compact-placeholder">
                                            metrics 없음
                                          </div>
                                        )}
                                      </section>
                                    );
                                  })}
                                </div>
                              ) : null}
                            </>
                          ) : (
                            <div className="detail-placeholder compact-placeholder">선택된 execution이 없습니다.</div>
                          )}
                        </section>
                      </div>
                    </section>

                    <div className="detail-grid detail-grid-asymmetric detail-section">
                      <section>
                        <div className="panel-heading">
                          <span>stages</span>
                          <strong>{bambooPlanDetail?.stages.length ?? 0}</strong>
                        </div>
                        <div className="line-list">
                          {(bambooPlanDetail?.stages ?? []).map((stage) => (
                            <article key={stage.name} className="line-item">
                              <div>
                                <strong>{stage.name}</strong>
                                <span>{stage.description || `${stage.jobs.length} jobs`}</span>
                              </div>
                              <div>
                                <span>{stage.jobs.map((job) => job.name).join(", ") || "jobs pending"}</span>
                              </div>
                            </article>
                          ))}
                        </div>
                      </section>

                      <section>
                        <div className="panel-heading">
                          <span>publish history</span>
                          <strong>{bambooPlanDetail?.recentPublishExecutions.length ?? 0}</strong>
                        </div>
                        <div className="line-list">
                          {(bambooPlanDetail?.recentPublishExecutions.length ?? 0) > 0 ? (
                            bambooPlanDetail?.recentPublishExecutions.map((execution) => (
                              <article key={execution.publishExecutionId} className="line-item">
                                <div>
                                  <strong>{execution.status}</strong>
                                  <span>{execution.message}</span>
                                </div>
                                <div>
                                  <span>{new Date(execution.createdAt).toLocaleString()}</span>
                                  <span>{execution.returnCode ?? "-"}</span>
                                </div>
                              </article>
                            ))
                          ) : (
                            <div className="detail-placeholder compact-placeholder">아직 publish 이력이 없습니다.</div>
                          )}
                        </div>
                      </section>
                    </div>

                  </>
                ) : (
                  <div className="detail-placeholder">표시할 빌드 플랜이 없습니다.</div>
                )}
              </div>
            </>
          ) : workspace === "modules" ? (
            <>
              <div className="project-list-panel reveal reveal-2">
                <div className="panel-heading">
                  <span>module assets</span>
                  <strong>{filteredModules.length} visible</strong>
                </div>
                <div className="project-list">
                  {filteredModules.map((module, index) => (
                    <button
                      key={module.assetId}
                      type="button"
                      className={`project-row build-plan-row ${module.assetId === selectedModuleId ? "is-selected" : ""}`}
                      onClick={() => setSelectedModuleId(module.assetId)}
                      style={{ animationDelay: `${120 + index * 28}ms` }}
                    >
                      <div className="project-row-head">
                        <strong>{module.moduleId}</strong>
                        <span>{module.providerScope}</span>
                      </div>
                      <p>{module.displayName}</p>
                      <div className="project-row-kpis">
                        <span className={`row-state ${module.status === "active" ? "is-ok" : "is-warn"}`}>
                          {module.status}
                        </span>
                        <span>{module.assetKind}</span>
                        <span>{module.activeVersionId ? "active wired" : "inactive"}</span>
                      </div>
                      <div className="project-row-meta">
                        <span>{module.assetKind}</span>
                        <span>{module.status}</span>
                      </div>
                    </button>
                  ))}
                  {!loading && filteredModules.length === 0 ? (
                    <div className="empty-state">조건에 맞는 모듈이 없습니다.</div>
                  ) : null}
                </div>
              </div>

              <div className="project-detail-panel reveal reveal-3">
                <div className="detail-header">
                  <div>
                    <span className="eyebrow">module registry</span>
                    <h3>{selectedModule?.displayName || "활성 자산과 reload 상태"}</h3>
                    <p className="detail-subcopy">
                      registry snapshot, reload 실패, 선택 자산 버전을 한 패널에서 점검하고 조치합니다.
                    </p>
                  </div>
                  <div className="readiness-badge is-ready">
                    {moduleLoadStatus?.activeAssetCount ?? 0} active
                  </div>
                </div>

                <div className="kpi-strip">
                  <article>
                    <span>active assets</span>
                    <strong>{moduleLoadStatus?.activeAssetCount ?? 0}</strong>
                  </article>
                  <article>
                    <span>loaded</span>
                    <strong>{moduleLoadStatus?.lastSnapshot?.loadedCount ?? 0}</strong>
                  </article>
                  <article>
                    <span>invalid</span>
                    <strong>{moduleLoadStatus?.lastSnapshot?.invalidCount ?? 0}</strong>
                  </article>
                  <article>
                    <span>recent failures</span>
                    <strong>{moduleFailureCount}</strong>
                  </article>
                  <article>
                    <span>selected versions</span>
                    <strong>{selectedModuleVersionCount}</strong>
                  </article>
                </div>

                <div className="detail-grid detail-grid-asymmetric">
                  <section>
                    <div className="panel-heading">
                      <span>registry control</span>
                      <strong>{moduleLoadStatus?.lastSnapshot?.status ?? "unknown"}</strong>
                    </div>
                    <div className="line-list">
                      <article className="line-item">
                        <div>
                          <strong>last snapshot</strong>
                          <span>{moduleLoadStatus?.lastSnapshot?.summaryMessage || "no snapshot"}</span>
                        </div>
                        <div>
                          <span>{moduleLoadStatus?.lastSnapshot?.loadedCount ?? 0} loaded</span>
                          <span>{moduleLoadStatus?.lastSnapshot?.skippedCount ?? 0} skipped</span>
                        </div>
                      </article>
                      <article className="line-item">
                        <div>
                          <strong>selected asset</strong>
                          <span>{selectedModule?.moduleId || "none selected"}</span>
                        </div>
                        <div>
                          <span>{selectedModule?.assetKind || "kind pending"}</span>
                          <span>{selectedModule?.status || "idle"}</span>
                        </div>
                      </article>
                      <article className="line-item">
                        <div>
                          <strong>recent issues</strong>
                          <span>선택 자산에 기록된 최근 오류와 validation 메시지</span>
                        </div>
                        <div>
                          <span>{selectedModuleIssueCount} issues</span>
                          <span>{moduleFailureCount} snapshot failures</span>
                        </div>
                      </article>
                    </div>
                    <div className="form-actions">
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => handleModuleAction("reload")}
                        disabled={moduleActionLoading}
                      >
                        Reload Modules
                      </button>
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => handleModuleAction("deactivate")}
                        disabled={moduleActionLoading || !selectedModule || selectedModule.status !== "active"}
                      >
                        Deactivate
                      </button>
                    </div>
                  </section>

                  <section>
                    <div className="panel-heading">
                      <span>recent failures</span>
                      <strong>{moduleFailureCount}</strong>
                    </div>
                    <div className="line-list">
                      {(moduleLoadStatus?.recentFailures.length ?? 0) > 0 ? (
                        moduleLoadStatus?.recentFailures.slice(0, 4).map((failure) => (
                          <article key={`${failure.moduleId}:${failure.errorCode}:${failure.errorMessage}`} className="line-item">
                            <div>
                              <strong>{failure.moduleId}</strong>
                              <span>{failure.errorCode || failure.status}</span>
                            </div>
                            <div>
                              <span>{failure.errorMessage || "error pending"}</span>
                            </div>
                          </article>
                        ))
                      ) : (
                        <div className="detail-placeholder compact-placeholder">최근 reload 실패 항목이 없습니다.</div>
                      )}
                    </div>
                  </section>
                </div>

                <section className="detail-section section-cluster">
                  <div className="panel-heading">
                    <span>selected module</span>
                    <strong>{selectedModule?.moduleId || "none"}</strong>
                  </div>
                  <p className="section-copy">
                    선택된 자산의 프로필, 업로드 버전, 활성화 액션, preview 내용을 분리해서 보여줍니다.
                  </p>
                  {selectedModule ? (
                    <>
                      <div className="detail-grid detail-grid-asymmetric">
                        <section>
                          <div className="panel-heading">
                            <span>asset profile</span>
                            <strong>{selectedModule.status}</strong>
                          </div>
                          <div className="line-list">
                            <article className="line-item">
                              <div>
                                <strong>kind</strong>
                                <span>{selectedModule.assetKind}</span>
                              </div>
                              <div>
                                <span>{selectedModule.providerScope}</span>
                              </div>
                            </article>
                            <article className="line-item">
                              <div>
                                <strong>preview</strong>
                                <span>{selectedModule.previewLanguage}</span>
                              </div>
                              <div>
                                <span>{selectedModule.selectedVersionId || "version pending"}</span>
                              </div>
                            </article>
                            <article className="line-item">
                              <div>
                                <strong>recent issues</strong>
                                <span>
                                  {selectedModule.recentIssues.length > 0
                                    ? selectedModule.recentIssues[0]?.errorMessage || "issue recorded"
                                    : "최근 이슈 없음"}
                                </span>
                              </div>
                              <div>
                                <span>{selectedModule.recentIssues.length} issues</span>
                              </div>
                            </article>
                          </div>
                        </section>

                        <section>
                          <div className="panel-heading">
                            <span>version timeline</span>
                            <strong>{selectedModule.versions.length}</strong>
                          </div>
                          <div className="line-list">
                            {selectedModule.versions.map((version) => (
                              <article key={version.versionId} className="line-item">
                                <div>
                                  <strong>v{version.versionNumber}</strong>
                                  <span>{version.sourceFilename}</span>
                                </div>
                                <div className="version-actions">
                                  <span>{version.validationStatus}</span>
                                  <button
                                    type="button"
                                    className="ghost-button"
                                    onClick={() => handleModuleAction("activate", version.versionId)}
                                    disabled={moduleActionLoading || version.isActive}
                                  >
                                    {version.isActive ? "Active" : "Activate"}
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                        </section>
                      </div>
                      <section className="detail-section module-preview-section">
                        <div className="panel-heading">
                          <span>preview surface</span>
                          <strong>{selectedModule.previewLanguage}</strong>
                        </div>
                        <pre className="module-preview">{selectedModule.previewContent}</pre>
                      </section>
                    </>
                  ) : (
                    <div className="detail-placeholder">표시할 모듈을 선택해 주세요.</div>
                  )}
                </section>

              </div>
            </>
          ) : workspace === "settings" ? (
            <>
              <div className="project-list-panel reveal reveal-2">
                <div className="panel-heading">
                  <span>system map</span>
                  <strong>{ciSystemItems.length + scmSystemItems.length + analysisSystemItems.length} targets</strong>
                </div>
                <section className="subform-section settings-group-section">
                  <div className="panel-heading">
                    <span>ci tools</span>
                    <strong>{ciSystemItems.length}</strong>
                  </div>
                  <div className="project-list settings-target-list">
                    {ciSystemItems.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`project-row settings-target-row ${selectedSettingsTarget === item.id ? "is-selected" : ""}`}
                        onClick={() => setSelectedSettingsTarget(item.id)}
                      >
                        <div className="project-row-head">
                          <strong>{item.label}</strong>
                          <span>{item.status}</span>
                        </div>
                        <p>{item.description}</p>
                      </button>
                    ))}
                  </div>
                </section>
                <section className="subform-section settings-group-section">
                  <div className="panel-heading">
                    <span>source control tools</span>
                    <strong>{scmSystemItems.length}</strong>
                  </div>
                  <div className="project-list settings-target-list">
                    {scmSystemItems.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`project-row settings-target-row ${selectedSettingsTarget === item.id ? "is-selected" : ""}`}
                        onClick={() => setSelectedSettingsTarget(item.id)}
                      >
                        <div className="project-row-head">
                          <strong>{item.label}</strong>
                          <span>{item.status}</span>
                        </div>
                        <p>{item.description}</p>
                      </button>
                    ))}
                  </div>
                </section>
                <section className="subform-section settings-group-section">
                  <div className="panel-heading">
                    <span>static analysis tools</span>
                    <strong>{analysisSystemItems.length}</strong>
                  </div>
                  <div className="project-list settings-target-list">
                    {analysisSystemItems.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`project-row settings-target-row ${selectedSettingsTarget === item.id ? "is-selected" : ""}`}
                        onClick={() => setSelectedSettingsTarget(item.id)}
                      >
                        <div className="project-row-head">
                          <strong>{item.label}</strong>
                          <span>{item.status}</span>
                        </div>
                        <p>{item.description}</p>
                      </button>
                    ))}
                  </div>
                </section>
              </div>

              <div className="project-detail-panel reveal reveal-3">
                <div className="detail-header">
                  <div>
                    <span className="eyebrow">{currentSettingsMeta.eyebrow}</span>
                    <h3>{currentSettingsMeta.title}</h3>
                    <p className="detail-subcopy">
                      외부 시스템 연결 상태를 운영 기준선 관점에서 확인하고, 선택한 시스템 설정만 오른쪽에서 편집합니다.
                    </p>
                  </div>
                  <div className={`readiness-badge ${settingsReadinessClass}`}>
                    {currentSettingsMeta.status}
                  </div>
                </div>

                {selectedSettingsTarget === "coverity" ? (
                  <section className="detail-section section-cluster">
                    <div className="panel-heading">
                      <span>coverity settings</span>
                      <strong>{coveritySettings?.connectUrl ? "configured" : "missing"}</strong>
                    </div>
                    <p className="section-copy">
                      정적분석 서버 연결과 저장소 매핑 정책을 관리합니다. 이 값은 prepare-context와 build metadata 생성 흐름 전반에 공통으로 사용됩니다.
                    </p>
                    <div className="detail-grid detail-grid-asymmetric">
                      <section>
                        <div className="panel-heading">
                          <span>connection baseline</span>
                          <strong>{coverityForm.connectUrl ? "linked" : "pending"}</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>connect endpoint</strong>
                              <span>{coverityForm.connectUrl || "not configured"}</span>
                            </div>
                            <div>
                              <span>{coverityForm.commitEnabled ? "commit enabled" : "commit disabled"}</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>repository linkage</strong>
                              <span>{coverityForm.repositoryLinkageMode || "mode pending"}</span>
                            </div>
                            <div>
                              <span>{coverityForm.onNewCert || "certificate policy pending"}</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>operational use</strong>
                              <span>prepare-context와 정적분석 결과 매핑에서 공통으로 참조됩니다.</span>
                            </div>
                          </article>
                        </div>
                      </section>
                      <section>
                        <div className="panel-heading">
                          <span>policy editor</span>
                          <strong>write enabled</strong>
                        </div>
                        <div className="editor-form settings-form">
                          <label>
                            <span>coverity connect url</span>
                            <input
                              value={coverityForm.connectUrl}
                              onChange={(event) => handleCoverityFormChange("connectUrl", event.target.value)}
                            />
                          </label>
                          <label>
                            <span>linkage mode</span>
                            <input
                              value={coverityForm.repositoryLinkageMode}
                              onChange={(event) => handleCoverityFormChange("repositoryLinkageMode", event.target.value)}
                            />
                          </label>
                          <label>
                            <span>certificate policy</span>
                            <input
                              value={coverityForm.onNewCert}
                              onChange={(event) => handleCoverityFormChange("onNewCert", event.target.value)}
                            />
                          </label>
                          <label className="checkbox-field">
                            <span>commit enabled</span>
                            <input
                              type="checkbox"
                              checked={coverityForm.commitEnabled}
                              onChange={(event) => handleCoverityFormChange("commitEnabled", event.target.checked)}
                            />
                          </label>
                        </div>
                      </section>
                    </div>
                    <div className="form-actions">
                      <button
                        type="button"
                        className="primary-button"
                        onClick={handleSettingsSave}
                        disabled={savingSettings}
                      >
                        {savingSettings ? "Saving..." : "Save Settings"}
                      </button>
                    </div>
                  </section>
                ) : null}

                {selectedSettingsTarget === "bamboo" ? (
                  <section className="detail-section section-cluster">
                    <div className="panel-heading">
                      <span>bamboo settings</span>
                      <strong>{bambooSettings?.serverUrl ? "configured" : "missing"}</strong>
                    </div>
                    <p className="section-copy">
                      Bamboo는 server URL과 auth token을 별도로 저장합니다. publish/queue 동작은 이 설정을 기준으로 연결됩니다.
                    </p>
                    <div className="detail-grid detail-grid-asymmetric">
                      <section>
                        <div className="panel-heading">
                          <span>runtime baseline</span>
                          <strong>test env</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>active endpoint</strong>
                              <span>{bambooForm.serverUrl || "not configured"}</span>
                            </div>
                            <div>
                              <span>{bambooUrlNeedsContextPath(bambooForm.serverUrl) ? "context missing" : "context ok"}</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>local test endpoint</strong>
                              <span>{TEST_ENV.bambooUrl}</span>
                            </div>
                            <div>
                              <span>context path required</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>auth status</strong>
                              <span>{bambooSettings?.tokenConfigured ? `configured: ${bambooSettings.tokenMasked || "token set"}` : "token not configured"}</span>
                            </div>
                          </article>
                        </div>
                      </section>
                      <section>
                        <div className="panel-heading">
                          <span>endpoint editor</span>
                          <strong>write enabled</strong>
                        </div>
                        <div className="editor-form settings-form">
                          <label>
                            <span>bamboo server url</span>
                            <input
                              value={bambooForm.serverUrl}
                              onChange={(event) => handleBambooFormChange("serverUrl", event.target.value)}
                            />
                          </label>
                          <label className="span-two">
                            <span>auth token (optional update)</span>
                            <input
                              value={bambooForm.token}
                              onChange={(event) => handleBambooFormChange("token", event.target.value)}
                              placeholder={bambooSettings?.tokenMasked ? `configured: ${bambooSettings.tokenMasked}` : "new token"}
                            />
                          </label>
                        </div>
                      </section>
                    </div>
                    {bambooUrlNeedsContextPath(bambooForm.serverUrl) ? (
                      <div className="inline-hint">
                        Bamboo 컨테이너는 context path를 사용합니다. 예: `http://127.0.0.1:8085/bamboo`
                      </div>
                    ) : null}
                    <div className="form-actions">
                      <button
                        type="button"
                        className="primary-button"
                        onClick={handleBambooSettingsSave}
                        disabled={savingSettings}
                      >
                        {savingSettings ? "Saving..." : "Save Bamboo Settings"}
                      </button>
                    </div>
                  </section>
                ) : null}

                {selectedSettingsTarget === "jenkins" ? (
                  <section className="detail-section section-cluster">
                    <div className="panel-heading">
                      <span>jenkins integration</span>
                      <strong>{jenkinsSettings?.serverUrl ? "configured" : "missing"}</strong>
                    </div>
                    <p className="section-copy">
                      Jenkins controller endpoint와 인증 정보를 편집합니다. token은 보안상 마스킹되며, 새 값 입력 시에만 갱신됩니다.
                    </p>
                    <div className="detail-grid detail-grid-asymmetric">
                      <section>
                        <div className="panel-heading">
                          <span>local test environment</span>
                          <strong>{TEST_ENV.jenkinsUrl}</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>http endpoint</strong>
                              <span>{TEST_ENV.jenkinsUrl}</span>
                            </div>
                            <div>
                              <span>controller</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>agent port</strong>
                              <span>{TEST_ENV.jenkinsAgentPort}</span>
                            </div>
                            <div>
                              <span>inbound agent</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>operational path</strong>
                              <span>job configure, trigger, status 조회는 Jenkins Jobs API에서 처리됩니다.</span>
                            </div>
                          </article>
                        </div>
                      </section>
                      <section>
                        <div className="panel-heading">
                          <span>settings editor</span>
                          <strong>write enabled</strong>
                        </div>
                        <div className="editor-form settings-form">
                          <label>
                            <span>jenkins server url</span>
                            <input
                              value={jenkinsForm.serverUrl}
                              onChange={(event) => handleJenkinsFormChange("serverUrl", event.target.value)}
                              placeholder={TEST_ENV.jenkinsUrl}
                            />
                          </label>
                          <label>
                            <span>username</span>
                            <input
                              value={jenkinsForm.username}
                              onChange={(event) => handleJenkinsFormChange("username", event.target.value)}
                              placeholder="jenkins admin"
                            />
                          </label>
                          <label className="span-two">
                            <span>token (optional update)</span>
                            <input
                              value={jenkinsForm.token}
                              onChange={(event) => handleJenkinsFormChange("token", event.target.value)}
                              placeholder={jenkinsSettings?.tokenMasked ? `configured: ${jenkinsSettings.tokenMasked}` : "new token"}
                            />
                          </label>
                        </div>
                        <div className="form-actions">
                          <button
                            type="button"
                            className="primary-button"
                            onClick={handleJenkinsSettingsSave}
                            disabled={savingSettings}
                          >
                            {savingSettings ? "Saving..." : "Save Jenkins Settings"}
                          </button>
                        </div>
                      </section>
                    </div>
                  </section>
                ) : null}

                {selectedSettingsTarget === "github" ? (
                  <section className="detail-section section-cluster">
                    <div className="panel-heading">
                      <span>github integration</span>
                      <strong>{githubSettings?.serverUrl ? "configured" : "optional"}</strong>
                    </div>
                    <p className="section-copy">
                      GitHub 연결에 필요한 server URL과 auth token을 설정합니다.
                    </p>
                    <div className="detail-grid detail-grid-asymmetric">
                      <section>
                        <div className="panel-heading">
                          <span>usage model</span>
                          <strong>optional cloud scm</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>hosting</strong>
                              <span>GitHub Cloud or Enterprise</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>current state</strong>
                              <span>server URL과 auth token이 저장되면 API 연동 기준값으로 사용됩니다.</span>
                            </div>
                          </article>
                        </div>
                      </section>
                      <section>
                        <div className="panel-heading">
                          <span>settings editor</span>
                          <strong>write enabled</strong>
                        </div>
                        <div className="editor-form settings-form">
                          <label>
                            <span>github server url</span>
                            <input
                              value={githubForm.serverUrl}
                              onChange={(event) => handleGithubFormChange("serverUrl", event.target.value)}
                              placeholder="https://github.com"
                            />
                          </label>
                          <label className="span-two">
                            <span>token (optional update)</span>
                            <input
                              value={githubForm.token}
                              onChange={(event) => handleGithubFormChange("token", event.target.value)}
                              placeholder={githubSettings?.tokenMasked ? `configured: ${githubSettings.tokenMasked}` : "new token"}
                            />
                          </label>
                        </div>
                        <div className="form-actions">
                          <button
                            type="button"
                            className="primary-button"
                            onClick={handleGithubSettingsSave}
                            disabled={savingSettings}
                          >
                            {savingSettings ? "Saving..." : "Save GitHub Settings"}
                          </button>
                        </div>
                      </section>
                    </div>
                  </section>
                ) : null}

                {selectedSettingsTarget === "bitbucket" ? (
                  <section className="detail-section section-cluster">
                    <div className="panel-heading">
                      <span>bitbucket integration</span>
                      <strong>{bitbucketSettings?.serverUrl ? "configured" : "optional"}</strong>
                    </div>
                    <p className="section-copy">
                      Bitbucket 연결에 필요한 server URL과 auth token을 설정합니다.
                    </p>
                    <div className="detail-grid detail-grid-asymmetric">
                      <section>
                        <div className="panel-heading">
                          <span>current usage</span>
                          <strong>project metadata driven</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>project linkage</strong>
                              <span>project create/update 폼의 bitbucket project key와 함께 사용됩니다.</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>settings state</strong>
                              <span>server URL과 auth token 저장값을 기준으로 연결합니다.</span>
                            </div>
                          </article>
                        </div>
                      </section>
                      <section>
                        <div className="panel-heading">
                          <span>settings editor</span>
                          <strong>write enabled</strong>
                        </div>
                        <div className="editor-form settings-form">
                          <label>
                            <span>bitbucket server url</span>
                            <input
                              value={bitbucketForm.serverUrl}
                              onChange={(event) => handleBitbucketFormChange("serverUrl", event.target.value)}
                              placeholder="https://bitbucket.org"
                            />
                          </label>
                          <label className="span-two">
                            <span>token (optional update)</span>
                            <input
                              value={bitbucketForm.token}
                              onChange={(event) => handleBitbucketFormChange("token", event.target.value)}
                              placeholder={bitbucketSettings?.tokenMasked ? `configured: ${bitbucketSettings.tokenMasked}` : "new token"}
                            />
                          </label>
                        </div>
                        <div className="form-actions">
                          <button
                            type="button"
                            className="primary-button"
                            onClick={handleBitbucketSettingsSave}
                            disabled={savingSettings}
                          >
                            {savingSettings ? "Saving..." : "Save Bitbucket Settings"}
                          </button>
                        </div>
                      </section>
                    </div>
                  </section>
                ) : null}

                {selectedSettingsTarget === "gitea" ? (
                  <section className="detail-section section-cluster">
                    <div className="panel-heading">
                      <span>gitea integration</span>
                      <strong>{giteaSettings?.serverUrl ? "configured" : "optional"}</strong>
                    </div>
                    <p className="section-copy">
                      Gitea 연결에 필요한 server URL과 auth token을 설정합니다.
                    </p>
                    <div className="detail-grid detail-grid-asymmetric">
                      <section>
                        <div className="panel-heading">
                          <span>local test environment</span>
                          <strong>{TEST_ENV.giteaUrl}</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>http endpoint</strong>
                              <span>{TEST_ENV.giteaUrl}</span>
                            </div>
                            <div>
                              <span>web ui / api</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>auth mode</strong>
                              <span>token-based auth</span>
                            </div>
                          </article>
                        </div>
                      </section>
                      <section>
                        <div className="panel-heading">
                          <span>settings editor</span>
                          <strong>write enabled</strong>
                        </div>
                        <div className="editor-form settings-form">
                          <label>
                            <span>gitea server url</span>
                            <input
                              value={giteaForm.serverUrl}
                              onChange={(event) => handleGiteaFormChange("serverUrl", event.target.value)}
                              placeholder={TEST_ENV.giteaUrl}
                            />
                          </label>
                          <label className="span-two">
                            <span>token (optional update)</span>
                            <input
                              value={giteaForm.token}
                              onChange={(event) => handleGiteaFormChange("token", event.target.value)}
                              placeholder={giteaSettings?.tokenMasked ? `configured: ${giteaSettings.tokenMasked}` : "new token"}
                            />
                          </label>
                        </div>
                        <div className="form-actions">
                          <button
                            type="button"
                            className="primary-button"
                            onClick={handleGiteaSettingsSave}
                            disabled={savingSettings}
                          >
                            {savingSettings ? "Saving..." : "Save Gitea Settings"}
                          </button>
                        </div>
                      </section>
                    </div>
                  </section>
                ) : null}

              </div>
            </>
          ) : (
            <>
              <div className="project-list-panel reveal reveal-2">
                <div className="panel-heading">
                  <span>admin operations</span>
                  <strong>{adminItems.length} targets</strong>
                </div>
                <div className="project-list settings-target-list">
                  {adminItems.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`project-row settings-target-row ${selectedAdminTarget === item.id ? "is-selected" : ""}`}
                      onClick={() => setSelectedAdminTarget(item.id)}
                    >
                      <div className="project-row-head">
                        <strong>{item.label}</strong>
                        <span>{item.status}</span>
                      </div>
                      <p>{item.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="project-detail-panel reveal reveal-3">
                <div className="detail-header">
                  <div>
                    <span className="eyebrow">operations admin</span>
                    <h3>{selectedAdminTarget === "drafts" ? "Specs Drafts" : "Module Snapshot"}</h3>
                    <p className="detail-subcopy">
                      외부 시스템 설정이 아니라 내부 운영 작업을 모아둔 작업면입니다. 위험도가 있는 관리 액션은 이곳에서만 실행합니다.
                    </p>
                  </div>
                  <div className={`readiness-badge ${selectedAdminTarget === "module-snapshot" && moduleFailureCount === 0 ? "is-ready" : ""}`}>
                    {selectedAdminTarget === "drafts"
                      ? initializingDrafts
                        ? "running"
                        : "ready"
                      : moduleLoadStatus?.lastSnapshot?.status ?? "unknown"}
                  </div>
                </div>

                {selectedAdminTarget === "drafts" ? (
                  <section className="detail-section section-cluster">
                    <div className="panel-heading">
                      <span>draft initialization</span>
                      <strong>{buildPlans.length} plans</strong>
                    </div>
                    <p className="section-copy">
                      현재 메타데이터를 기준으로 BuildInfo drafts를 다시 생성하거나 정규화합니다. 기존 draft를 정리한 뒤 초기화하는 관리 작업입니다.
                    </p>
                    <div className="detail-grid detail-grid-asymmetric">
                      <section>
                        <div className="panel-heading">
                          <span>operation scope</span>
                          <strong>metadata refresh</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>affected plans</strong>
                              <span>{buildPlans.length} build plans in current registry</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>reset behavior</strong>
                              <span>기존 draft를 초기화하고 현재 저장된 메타데이터 기준으로 다시 채웁니다.</span>
                            </div>
                          </article>
                        </div>
                      </section>
                      <section>
                        <div className="panel-heading">
                          <span>run action</span>
                          <strong>{initializingDrafts ? "running" : "ready"}</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>execution note</strong>
                              <span>초기화 후 build plans와 관련 prepare-context 데이터가 다시 로드됩니다.</span>
                            </div>
                          </article>
                        </div>
                        <div className="form-actions">
                          <button
                            type="button"
                            className="primary-button"
                            onClick={() => void handleInitializeDrafts()}
                            disabled={initializingDrafts}
                          >
                            {initializingDrafts ? "Initializing..." : "Initialize Drafts"}
                          </button>
                        </div>
                      </section>
                    </div>
                  </section>
                ) : (
                  <section className="detail-section section-cluster">
                    <div className="panel-heading">
                      <span>module snapshot</span>
                      <strong>{moduleLoadStatus?.lastSnapshot?.status ?? "unknown"}</strong>
                    </div>
                    <p className="section-copy">
                      최근 module registry snapshot과 reload 실패를 점검하는 관리 영역입니다. 설정 변경이 아니라 현재 운영 상태를 진단하는 용도입니다.
                    </p>
                    <div className="kpi-strip compact-kpi-strip">
                      <article>
                        <span>active assets</span>
                        <strong>{moduleLoadStatus?.activeAssetCount ?? 0}</strong>
                      </article>
                      <article>
                        <span>loaded</span>
                        <strong>{moduleLoadStatus?.lastSnapshot?.loadedCount ?? 0}</strong>
                      </article>
                      <article>
                        <span>failures</span>
                        <strong>{moduleFailureCount}</strong>
                      </article>
                    </div>
                    <div className="detail-grid detail-grid-asymmetric">
                      <section>
                        <div className="panel-heading">
                          <span>snapshot summary</span>
                          <strong>{moduleLoadStatus?.lastSnapshot?.snapshotId?.slice(0, 8) ?? "no snapshot"}</strong>
                        </div>
                        <div className="line-list">
                          <article className="line-item">
                            <div>
                              <strong>summary</strong>
                              <span>{moduleLoadStatus?.lastSnapshot?.summaryMessage || "snapshot pending"}</span>
                            </div>
                          </article>
                          <article className="line-item">
                            <div>
                              <strong>skipped / invalid</strong>
                              <span>{moduleLoadStatus?.lastSnapshot?.skippedCount ?? 0} skipped / {moduleLoadStatus?.lastSnapshot?.invalidCount ?? 0} invalid</span>
                            </div>
                          </article>
                        </div>
                      </section>
                      <section>
                        <div className="panel-heading">
                          <span>recent failures</span>
                          <strong>{moduleFailureCount}</strong>
                        </div>
                        <div className="line-list">
                          {(moduleLoadStatus?.recentFailures.length ?? 0) > 0 ? (
                            moduleLoadStatus?.recentFailures.slice(0, 5).map((failure) => (
                              <article key={`${failure.moduleId}:${failure.errorCode}:${failure.errorMessage}`} className="line-item">
                                <div>
                                  <strong>{failure.moduleId}</strong>
                                  <span>{failure.errorCode || failure.status}</span>
                                </div>
                                <div>
                                  <span>{failure.errorMessage || "error pending"}</span>
                                </div>
                              </article>
                            ))
                          ) : (
                            <div className="detail-placeholder compact-placeholder">최근 module failure가 없습니다.</div>
                          )}
                        </div>
                      </section>
                    </div>
                  </section>
                )}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
