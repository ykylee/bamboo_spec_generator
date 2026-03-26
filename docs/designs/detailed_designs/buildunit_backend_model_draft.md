# Detailed Design: BuildUnit 중심 백엔드 모델 초안

## 문서 메타데이터

- 문서 일자: 2026-03-25
- 문서 유형: Detailed Design
- 관련 요구사항: [../../requirements/SRS.md](../../requirements/SRS.md)
- 관련 요구사항: [../../requirements/issues/STORY-31-jenkins-project-and-job-registration.md](../../requirements/issues/STORY-31-jenkins-project-and-job-registration.md)
- 관련 요구사항: [../../requirements/issues/STORY-32-ci-provider-domain-model.md](../../requirements/issues/STORY-32-ci-provider-domain-model.md)
- 관련 요구사항: [../../requirements/issues/STORY-33-jenkins-system-operations-visibility.md](../../requirements/issues/STORY-33-jenkins-system-operations-visibility.md)
- 관련 설계: [./backend_model_generalization_review.md](./backend_model_generalization_review.md)
- 관련 설계: [./multi_ci_console_and_provider_model.md](./multi_ci_console_and_provider_model.md)

## 요약

이 문서는 기존 `BuildPlan` 중심 구조를 폐기하고, 공통 `BuildUnit` 중심으로 Bamboo/Jenkins를 함께 수용하는 신규 Django 모델 초안을 정의한다. 목표는 공통 코어 모델과 provider 상세 모델을 명확히 분리하고, 이후 API/서비스/UI가 이 구조를 직접 사용하도록 만드는 것이다.

## 설계 원칙

- 공통 개념은 코어 모델에 둔다.
- Bamboo/Jenkins 전용 정보는 상세 모델로 분리한다.
- 기존 `BuildPlan`, `BuildPlanBuildInfo`, `ProjectBuild`, `BuildPlanDefinition` 계열은 신규 구조의 기준이 아니다.
- 기존 데이터 호환보다 신규 스키마의 일관성을 우선한다.
- 초기 구현은 Django ORM 기준 명확한 FK/OneToOne 관계를 사용한다.

## 신규 모델 개요

### 코어 모델

- `Project`
- `Repository`
- `BuildUnit`
- `BuildUnitDefinition`
- `BuildVersion`
- `BuildExecution`
- `ExecutionArtifact`
- `StaticAnalysisResult`
- `DeploymentTarget`
- `DeploymentExecution`
- `SystemStatusSnapshot`
- `AuditEvent`
- `SystemSetting`

### Provider 상세 모델

- `BambooBuildUnit`
- `BambooBuildInfo`
- `BambooPublishExecution`
- `JenkinsBuildUnit`
- `JenkinsNodeSnapshot`
- `JenkinsQueueItemSnapshot`

## Django 모델 초안

아래 코드는 최종 구현이 아니라 필드와 관계를 확정하기 위한 초안이다.

```python
from __future__ import annotations

import uuid
from django.db import models
from django.db.models import Q


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Project(TimestampedModel):
    PROVIDER_BAMBOO = "bamboo"
    PROVIDER_JENKINS = "jenkins"
    PROVIDER_CHOICES = [
        (PROVIDER_BAMBOO, "Bamboo"),
        (PROVIDER_JENKINS, "Jenkins"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "active"),
        (STATUS_INACTIVE, "inactive"),
        (STATUS_ARCHIVED, "archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_key = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner_team = models.CharField(max_length=255, blank=True)
    service_type = models.CharField(max_length=64, blank=True)
    ci_provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    representative_repository = models.ForeignKey(
        "buildmeta.Repository",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ci_provider", "project_key"], name="uq_project_provider_key"),
        ]


class Repository(TimestampedModel):
    TYPE_BITBUCKET = "bitbucket"
    TYPE_GIT = "git"
    TYPE_CHOICES = [
        (TYPE_BITBUCKET, "bitbucket"),
        (TYPE_GIT, "git"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="repositories")
    repo_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_BITBUCKET)
    repo_key = models.CharField(max_length=128, blank=True)
    repo_slug = models.CharField(max_length=255)
    clone_url = models.TextField(blank=True)
    default_branch = models.CharField(max_length=255, blank=True)
    is_representative = models.BooleanField(default=False)
    coverity_project = models.CharField(max_length=255, blank=True)
    coverity_stream = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "repo_slug"], name="uq_repository_project_slug"),
            models.UniqueConstraint(
                fields=["project"],
                condition=Q(is_representative=True),
                name="uq_repository_representative",
            ),
        ]


class BuildUnit(TimestampedModel):
    PROVIDER_BAMBOO = "bamboo"
    PROVIDER_JENKINS = "jenkins"
    PROVIDER_CHOICES = [
        (PROVIDER_BAMBOO, "Bamboo"),
        (PROVIDER_JENKINS, "Jenkins"),
    ]

    TYPE_BUILD = "build"
    TYPE_PIPELINE = "pipeline"
    TYPE_ANALYSIS = "analysis"
    TYPE_DEPLOY = "deploy"
    TYPE_CHOICES = [
        (TYPE_BUILD, "build"),
        (TYPE_PIPELINE, "pipeline"),
        (TYPE_ANALYSIS, "analysis"),
        (TYPE_DEPLOY, "deploy"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_DISABLED = "disabled"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "active"),
        (STATUS_DISABLED, "disabled"),
        (STATUS_ARCHIVED, "archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="build_units")
    repository = models.ForeignKey(
        Repository,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="build_units",
    )
    ci_provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    unit_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_BUILD)
    external_key = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    language = models.CharField(max_length=64, blank=True)
    compiler = models.CharField(max_length=128, blank=True)
    runtime_stack = models.CharField(max_length=128, blank=True)
    lifecycle_status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    is_enabled = models.BooleanField(default=True)
    latest_version = models.ForeignKey(
        "buildmeta.BuildVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ci_provider", "external_key"], name="uq_build_unit_provider_key"),
        ]


class BuildUnitDefinition(TimestampedModel):
    SOURCE_JSON = "json"
    SOURCE_API = "api"
    SOURCE_UI = "ui"
    SOURCE_IMPORT = "import"
    SOURCE_CHOICES = [
        (SOURCE_JSON, "json"),
        (SOURCE_API, "api"),
        (SOURCE_UI, "ui"),
        (SOURCE_IMPORT, "import"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_unit = models.ForeignKey(BuildUnit, on_delete=models.CASCADE, related_name="definitions")
    version = models.PositiveIntegerField(default=1)
    year = models.CharField(max_length=16, blank=True)
    source_kind = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    definition_hash = models.CharField(max_length=128)
    definition_json = models.JSONField()
    is_active = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["build_unit", "definition_hash"], name="uq_build_unit_definition_hash"),
            models.UniqueConstraint(
                fields=["build_unit"],
                condition=Q(is_active=True),
                name="uq_build_unit_definition_active",
            ),
        ]


class BuildVersion(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_unit = models.ForeignKey(BuildUnit, on_delete=models.CASCADE, related_name="versions")
    version_text = models.CharField(max_length=64)
    version_major = models.PositiveIntegerField(default=0)
    version_minor = models.PositiveIntegerField(default=0)
    version_patch = models.PositiveIntegerField(default=0)
    commit_hash = models.CharField(max_length=64, blank=True)
    branch_name = models.CharField(max_length=255, blank=True)
    branch_kind = models.CharField(max_length=64, blank=True)
    is_latest = models.BooleanField(default=False)
    latest_execution = models.ForeignKey(
        "buildmeta.BuildExecution",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    latest_success = models.BooleanField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["build_unit", "version_text"], name="uq_build_version_text"),
            models.UniqueConstraint(
                fields=["build_unit"],
                condition=Q(is_latest=True),
                name="uq_build_version_latest",
            ),
        ]


class BuildExecution(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "queued"),
        (STATUS_RUNNING, "running"),
        (STATUS_SUCCESS, "success"),
        (STATUS_FAILED, "failed"),
        (STATUS_CANCELED, "canceled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_unit = models.ForeignKey(BuildUnit, on_delete=models.CASCADE, related_name="executions")
    build_version = models.ForeignKey(
        BuildVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="executions",
    )
    execution_number = models.CharField(max_length=64)
    external_execution_key = models.CharField(max_length=255, blank=True)
    trigger_type = models.CharField(max_length=64, blank=True)
    trigger_actor = models.CharField(max_length=255, blank=True)
    branch_name = models.CharField(max_length=255, blank=True)
    commit_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    summary = models.TextField(blank=True)
    stage_name = models.CharField(max_length=255, blank=True)
    job_name = models.CharField(max_length=255, blank=True)
    task_name = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["build_unit", "execution_number"], name="uq_build_execution_number"),
        ]


class ExecutionArtifact(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_execution = models.ForeignKey(BuildExecution, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    path = models.TextField(blank=True)
    download_url = models.TextField(blank=True)
    checksum = models.CharField(max_length=128, blank=True)


class StaticAnalysisResult(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_execution = models.ForeignKey(BuildExecution, on_delete=models.CASCADE, related_name="static_analysis_results")
    tool_name = models.CharField(max_length=64)
    status = models.CharField(max_length=64)
    summary = models.TextField(blank=True)
    metrics_json = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["build_execution", "tool_name"], name="uq_static_analysis_tool"),
        ]


class DeploymentTarget(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64, unique=True)
    target_type = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32, default="active")
    approval_required = models.BooleanField(default=False)


class DeploymentExecution(TimestampedModel):
    STATUS_REQUESTED = "requested"
    STATUS_APPROVED = "approved"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_ROLLED_BACK = "rolled_back"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_version = models.ForeignKey(BuildVersion, on_delete=models.CASCADE, related_name="deployments")
    deployment_target = models.ForeignKey(DeploymentTarget, on_delete=models.PROTECT, related_name="deployments")
    status = models.CharField(max_length=32)
    requested_by = models.CharField(max_length=255, blank=True)
    approved_by = models.CharField(max_length=255, blank=True)
    rollback_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rollback_executions",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)


class SystemStatusSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ci_provider = models.CharField(max_length=32)
    resource_type = models.CharField(max_length=64)
    resource_name = models.CharField(max_length=255)
    status = models.CharField(max_length=64)
    online = models.BooleanField(default=False)
    busy = models.BooleanField(default=False)
    queue_size = models.PositiveIntegerField(default=0)
    labels_json = models.JSONField(null=True, blank=True)
    payload_json = models.JSONField(null=True, blank=True)
    captured_at = models.DateTimeField()


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.CharField(max_length=255, blank=True)
    event_type = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64)
    target_id = models.CharField(max_length=64)
    payload_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SystemSetting(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=128, unique=True)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)


class BambooBuildUnit(TimestampedModel):
    LINKED = "linked"
    CREATE_IF_MISSING = "create_if_missing"

    build_unit = models.OneToOneField(BuildUnit, on_delete=models.CASCADE, primary_key=True, related_name="bamboo")
    bamboo_project_key = models.CharField(max_length=64, blank=True)
    plan_key = models.CharField(max_length=64, unique=True)
    build_id = models.CharField(max_length=255, unique=True)
    repository_linkage_mode = models.CharField(max_length=32, blank=True)
    application_link = models.CharField(max_length=255, blank=True)
    static_analysis_tool_version = models.CharField(max_length=128, blank=True)
    coverity_project = models.CharField(max_length=255, blank=True)


class BambooBuildInfo(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bamboo_build_unit = models.ForeignKey(BambooBuildUnit, on_delete=models.CASCADE, related_name="build_infos")
    build_key = models.CharField(max_length=128)
    operating_system = models.CharField(max_length=64, blank=True)
    pre_process = models.TextField(blank=True)
    build_command = models.TextField(blank=True)
    clean_command = models.TextField(blank=True)
    language = models.CharField(max_length=64, blank=True)
    compiler = models.CharField(max_length=128, blank=True)
    analysis_excluded_files = models.TextField(blank=True)
    coverity_stream = models.CharField(max_length=255, blank=True)
    build_sub_path = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["bamboo_build_unit", "build_key"], name="uq_bamboo_build_info_key"),
        ]


class BambooPublishExecution(TimestampedModel):
    build_unit = models.ForeignKey(BuildUnit, on_delete=models.CASCADE, related_name="bamboo_publish_executions")
    status = models.CharField(max_length=32)
    message = models.TextField(blank=True)
    output = models.TextField(blank=True)
    snapshot_preview_json = models.JSONField(null=True, blank=True)
    snapshot_export_draft_json = models.JSONField(null=True, blank=True)
    return_code = models.IntegerField(null=True, blank=True)


class JenkinsBuildUnit(TimestampedModel):
    JOB_FREESTYLE = "freestyle"
    JOB_PIPELINE = "pipeline"

    build_unit = models.OneToOneField(BuildUnit, on_delete=models.CASCADE, primary_key=True, related_name="jenkins")
    job_path = models.CharField(max_length=255, unique=True)
    job_type = models.CharField(max_length=64, blank=True)
    folder_path = models.CharField(max_length=255, blank=True)
    pipeline_kind = models.CharField(max_length=64, blank=True)


class JenkinsNodeSnapshot(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource_name = models.CharField(max_length=255)
    labels_json = models.JSONField(null=True, blank=True)
    executor_count = models.PositiveIntegerField(default=0)
    busy_executors = models.PositiveIntegerField(default=0)
    offline_reason = models.TextField(blank=True)
    captured_at = models.DateTimeField()


class JenkinsQueueItemSnapshot(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    queue_item_key = models.CharField(max_length=128)
    job_path = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=64, blank=True)
    waiting_reason = models.TextField(blank=True)
    in_queue_since = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField()
```

## 모델별 역할 정리

### `Project`

- 운영 콘솔 최상위 식별 단위
- Bamboo/Jenkins 중 어느 provider에 속하는지 명확히 구분
- 권한, 소유 팀, 운영 상태의 기준점

### `Repository`

- 프로젝트에 연결된 소스 저장소
- build unit과 느슨하게 연결하되, 대표 저장소 개념을 유지
- Coverity 같은 저장소 수준 메타데이터 포함

### `BuildUnit`

- 신규 코어 aggregate
- Bamboo `plan`, Jenkins `job`을 공통적으로 표현
- 공통 목록/상세/API는 이 모델을 기준으로 조회

### `BuildUnitDefinition`

- JSON, UI 등록, API 등록 등 다양한 입력 원천을 수용
- 활성 정의 1건 규칙 유지
- provider별 definition payload도 `definition_json`에 담되 공통 스키마로 정규화

### `BuildExecution`

- 실행 이력의 공통 표준
- provider 전용 build number, queue key는 `execution_number`, `external_execution_key`에 수용
- 실패 위치는 `stage_name`, `job_name`, `task_name`으로 분리

### `BuildVersion`

- 버전 포인터와 최신 상태 추적
- Bamboo branch kind 규칙은 초기 구현에 유지 가능하지만, 장기적으로는 provider 독립 규칙으로 재정리

### `BambooBuildUnit` / `BambooBuildInfo`

- 현재 Bamboo 구조의 주요 필드를 보존하되 공통 코어 밖으로 이동
- `BuildInfo`는 Bamboo 전용 상세로 명확히 위치시킴

### `JenkinsBuildUnit`

- Jenkins job path와 타입을 표현
- folder를 별도 엔터티로 두지 않고 1차는 경로 기반 식별

## 1차 구현 범위

다음 모델만 먼저 구현해도 신규 구조의 핵심은 성립한다.

- `Project`
- `Repository`
- `BuildUnit`
- `BuildUnitDefinition`
- `BuildVersion`
- `BuildExecution`
- `StaticAnalysisResult`
- `SystemSetting`
- `BambooBuildUnit`
- `BambooBuildInfo`
- `BambooPublishExecution`
- `JenkinsBuildUnit`
- `SystemStatusSnapshot`
- `AuditEvent`

다음 모델은 2차 범위로 둔다.

- `ExecutionArtifact`
- `DeploymentTarget`
- `DeploymentExecution`
- `JenkinsNodeSnapshot`
- `JenkinsQueueItemSnapshot`

## 서비스 재작성 기준

기존 서비스는 다음 기준으로 다시 써야 한다.

- `services/projects.py`
  - `Project + Repository + BuildUnit` 기준으로 재작성
- `services/definitions.py`
  - `BuildUnitDefinition` 기준으로 재작성
- `selectors/definitions.py`
  - `BuildUnit` 기준 공통 정의 응답 + provider adapter 구조로 재작성
- `services/bamboo.py`
  - `BambooBuildUnit` 기준으로 재작성
- 신규 `services/jenkins.py`
  - `JenkinsBuildUnit` 기준으로 작성

## 마이그레이션/데이터 정책

- 기존 DB 스키마는 유지 대상이 아니다.
- 기존 개발 데이터는 백필하지 않는다.
- 신규 구조 적용 시 DB 초기화 후 신규 migration 기준으로 시작한다.
- 초기 데이터는 JSON import 또는 신규 등록 UI/API로 다시 적재한다.

## 수용 기준

- 신규 코어 모델과 provider 상세 모델 경계가 명확하다.
- `BuildPlan` 없이도 Bamboo/Jenkins를 공통 모델로 표현할 수 있다.
- Bamboo 전용 필드가 코어 모델 밖으로 분리된다.
- Jenkins job 등록에 필요한 필드가 코어 + 상세 모델 조합으로 표현된다.
- 실행/버전/정의 이력이 `BuildUnit` 기준으로 연결된다.

## 오픈 이슈

- `project_key`를 provider별 유일키로 둘지 글로벌 유일키로 둘지 결정 필요
- `BuildVersion`의 버전 규칙을 provider 공통으로 강제할지 결정 필요
- `SystemStatusSnapshot`만으로 충분한지, provider별 별도 snapshot 테이블을 초기에 도입할지 결정 필요
- `ExecutionArtifact`를 1차 범위에 포함할지 결정 필요
