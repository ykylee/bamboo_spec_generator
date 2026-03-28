# Detailed Design: 모듈 레지스트리 백엔드 모델과 관리자 API

## 문서 메타데이터

- 문서 일자: 2026-03-27
- 문서 유형: Detailed Design
- 관련 요구사항: [../../requirements/SRS.md](../../requirements/SRS.md)
- 관련 요구사항: [../../requirements/issues/STORY-34-modular-build-composition-and-tool-specific-tasks.md](../../requirements/issues/STORY-34-modular-build-composition-and-tool-specific-tasks.md)
- 관련 설계: [./modular_build_composition_and_tool_specific_tasks.md](./modular_build_composition_and_tool_specific_tasks.md)
- 관련 결정사항: [./modular_build_composition_decisions.md](./modular_build_composition_decisions.md)

## 요약

이 문서는 선언형 `stage`, `job`, `task` 모듈과 스크립트 자산을 관리하기 위한 운영 백엔드 모델과 관리자 API를 정의한다. 목표는 파일 기반 자동 로딩 구조를 유지하면서도, 업로드 이력, 활성화 상태, 재로드 결과, 오류 보고를 Django 백엔드에서 일관되게 관리하는 것이다.

## 배경

- 모듈 로딩 자체는 파일시스템 스캔 기반이지만, 운영 환경에서는 누가 무엇을 올렸는지와 어떤 로딩 결과가 나왔는지를 추적해야 한다.
- 단순 파일 드롭만으로는 감사 추적, 승인 흐름, 비활성화, 오류 조회가 어렵다.
- 기존 운영 백엔드는 프로젝트/빌드/시스템 설정을 관리하므로 모듈 관리도 같은 운영 콘솔 안에 들어가는 편이 자연스럽다.

## 목표

- 모듈 업로드와 활성화 상태를 DB에서 추적한다.
- 실제 로딩 대상 파일은 관리 디렉터리에 유지한다.
- 관리자 API를 통해 업로드, 활성화, 비활성화, 재로드, 상태 조회를 제공한다.
- 모듈 로딩 실패를 UI와 API에서 명확히 확인할 수 있게 한다.

## 비목표

- 임의 Python 코드 업로드 및 실행
- 일반 사용자 대상 공개 API
- object storage 기반 분산 저장 구현 확정

## 설계 원칙

- 런타임 로더는 파일시스템을 기준으로 동작한다.
- 운영 추적과 승인 상태는 DB를 기준으로 관리한다.
- 업로드와 활성화는 분리한다.
- 로딩 실패는 가능한 한 부분 격리한다.
- provider별 세부 검증은 공통 API 경계가 아니라 로더/validator 계층에서 수행한다.

## 도메인 모델

### 핵심 엔터티

- `ModuleAsset`
  - 선언형 모듈 파일 또는 스크립트 자산 파일 1건
- `ModuleAssetVersion`
  - 업로드된 파일의 개별 버전
- `ModuleActivation`
  - 현재 활성 상태와 활성 경로 정보
- `ModuleLoadSnapshot`
  - 한 번의 재로드 실행 결과
- `ModuleLoadEntry`
  - 재로드 시 파일별 처리 결과

### `ModuleAsset`

- 목적:
  - 같은 논리 모듈의 식별자와 현재 상태를 표현
- 주요 필드:
  - `id`
  - `asset_kind`
    - `stage_module`
    - `job_module`
    - `task_module`
    - `script_template`
  - `provider_scope`
    - `common`
    - `bamboo`
    - `jenkins`
  - `module_id`
  - `display_name`
  - `status`
    - `draft`
    - `active`
    - `inactive`
    - `invalid`
    - `archived`
  - `active_version`
  - `latest_version`

### `ModuleAssetVersion`

- 목적:
  - 실제 업로드된 파일 버전과 파일 메타데이터 추적
- 주요 필드:
  - `id`
  - `asset`
  - `version_number`
  - `source_filename`
  - `storage_path`
  - `content_hash`
  - `schema_version`
  - `uploaded_by`
  - `uploaded_at`
  - `validation_status`
    - `pending`
    - `valid`
    - `invalid`
  - `validation_message`
  - `parsed_metadata_json`

### `ModuleActivation`

- 목적:
  - 어떤 버전이 현재 활성 디렉터리에 반영됐는지 표현
- 주요 필드:
  - `asset`
  - `activated_version`
  - `activation_status`
    - `active`
    - `inactive`
    - `failed`
  - `activated_by`
  - `activated_at`
  - `active_path`

### `ModuleLoadSnapshot`

- 목적:
  - 재로드 1회 실행의 전체 결과
- 주요 필드:
  - `id`
  - `triggered_by`
  - `trigger_source`
    - `startup`
    - `api`
    - `management_command`
  - `started_at`
  - `finished_at`
  - `status`
    - `success`
    - `partial_success`
    - `failed`
  - `loaded_count`
  - `invalid_count`
  - `skipped_count`
  - `summary_message`

### `ModuleLoadEntry`

- 목적:
  - 스냅샷 안에서 파일별 로딩 결과 추적
- 주요 필드:
  - `snapshot`
  - `asset`
  - `asset_version`
  - `module_kind`
  - `module_id`
  - `source_path`
  - `status`
    - `loaded`
    - `invalid`
    - `skipped`
    - `conflict`
  - `error_code`
  - `error_message`

## Django 모델 초안

```python
class ModuleAsset(TimestampedModel):
    KIND_STAGE = "stage_module"
    KIND_JOB = "job_module"
    KIND_TASK = "task_module"
    KIND_TEMPLATE = "script_template"

    SCOPE_COMMON = "common"
    SCOPE_BAMBOO = "bamboo"
    SCOPE_JENKINS = "jenkins"

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_INVALID = "invalid"
    STATUS_ARCHIVED = "archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_kind = models.CharField(max_length=32)
    provider_scope = models.CharField(max_length=32, default=SCOPE_COMMON)
    module_id = models.CharField(max_length=128)
    display_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, default=STATUS_DRAFT)
    active_version = models.ForeignKey(
        "buildmeta.ModuleAssetVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    latest_version = models.ForeignKey(
        "buildmeta.ModuleAssetVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )


class ModuleAssetVersion(TimestampedModel):
    VALIDATION_PENDING = "pending"
    VALIDATION_VALID = "valid"
    VALIDATION_INVALID = "invalid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(ModuleAsset, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    source_filename = models.CharField(max_length=255)
    storage_path = models.TextField()
    content_hash = models.CharField(max_length=128)
    schema_version = models.CharField(max_length=64, blank=True)
    validation_status = models.CharField(max_length=32, default=VALIDATION_PENDING)
    validation_message = models.TextField(blank=True)
    parsed_metadata_json = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)


class ModuleLoadSnapshot(TimestampedModel):
    SOURCE_STARTUP = "startup"
    SOURCE_API = "api"
    SOURCE_COMMAND = "management_command"

    STATUS_SUCCESS = "success"
    STATUS_PARTIAL = "partial_success"
    STATUS_FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trigger_source = models.CharField(max_length=32)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, default=STATUS_SUCCESS)
    loaded_count = models.PositiveIntegerField(default=0)
    invalid_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    summary_message = models.TextField(blank=True)
```

## 파일시스템 경로 정책

### 관리 루트

- 기본 루트:
  - `managed_modules/`

### 하위 경로

- 업로드 보관:
  - `managed_modules/uploads/{kind}/{provider}/{module_id}/{version}/`
- 활성 반영:
  - `managed_modules/active/{kind}/{provider}/`
- 보관 이력:
  - `managed_modules/archive/{year}/{month}/`

### 예시

```text
managed_modules/
  uploads/
    task_module/
      bamboo/
        bamboo-prepare-python/
          v3/
            module.yaml
  active/
    task_module/
      bamboo/
        bamboo-prepare-python.yaml
```

## 관리자 API 설계

### 1. 업로드 API

- `POST /api/v1/admin/modules/uploads`
- 목적:
  - 선언형 파일 또는 템플릿 자산 업로드
- 요청:
  - multipart form
  - `assetKind`
  - `providerScope`
  - `moduleId`
  - `file`
  - `activateAfterUpload`
- 응답:
  - `assetId`
  - `versionId`
  - `validationStatus`
  - `messages`

### 2. 목록 API

- `GET /api/v1/admin/modules`
- 필터:
  - `assetKind`
  - `providerScope`
  - `status`
  - `moduleId`
- 응답:
  - 모듈 요약 목록
  - 현재 활성 버전
  - 최근 검증 결과

### 3. 상세 API

- `GET /api/v1/admin/modules/{assetId}`
- 응답:
  - 모듈 메타데이터
  - 버전 목록
  - 활성 상태
  - 최근 로딩 실패 이력

### 4. 활성화 API

- `POST /api/v1/admin/modules/{assetId}/activate`
- 요청:
  - `versionId`
- 동작:
  - 해당 버전을 active 디렉터리에 반영
  - asset 상태를 `active`로 갱신

### 5. 비활성화 API

- `POST /api/v1/admin/modules/{assetId}/deactivate`
- 동작:
  - active 디렉터리에서 제거
  - asset 상태를 `inactive`로 갱신

### 6. 재로드 API

- `POST /api/v1/admin/modules/reload`
- 요청:
  - 선택적 `providerScope`
  - 선택적 `assetKind`
- 응답:
  - `snapshotId`
  - `status`
  - `loadedCount`
  - `invalidCount`
  - `entries`

### 7. 로딩 상태 API

- `GET /api/v1/admin/modules/load-status`
- 응답:
  - 마지막 스냅샷
  - 최근 실패 항목
  - 현재 활성 모듈 수

## 응답 예시

```json
{
  "assetId": "0c4b6b7b-2a59-4f15-9db0-91d0d777f500",
  "moduleId": "bamboo-prepare-python",
  "assetKind": "task_module",
  "providerScope": "bamboo",
  "status": "active",
  "activeVersion": {
    "versionId": "cf18b0d2-a10a-46dc-bf02-0aee56961be7",
    "versionNumber": 3,
    "validationStatus": "valid",
    "uploadedAt": "2026-03-27T09:20:00Z"
  }
}
```

## 서비스 계층 초안

### `apps.buildmeta.services.module_registry.upload_asset(...)`

- 책임:
  - 파일 저장
  - 해시 계산
  - 기초 스키마 검증
  - version row 생성

### `apps.buildmeta.services.module_registry.activate_asset_version(...)`

- 책임:
  - 활성 대상 경로 계산
  - 기존 active 파일 교체
  - DB 활성 상태 갱신

### `apps.buildmeta.services.module_registry.reload_modules(...)`

- 책임:
  - active 디렉터리 스캔
  - validator/loader 실행
  - snapshot 및 entry 기록
  - 메모리 registry 갱신

### `apps.buildmeta.selectors.module_registry.get_load_status()`

- 책임:
  - 마지막 스냅샷
  - 실패 항목
  - 활성 모듈 요약 반환

## 권한 모델 초안

- `admin`
  - 업로드, 활성화, 비활성화, 재로드 가능
- `operator`
  - 조회 가능
  - 향후 승인형 워크플로우 도입 시 승인 가능 후보
- `viewer`
  - 로딩 상태 조회만 가능

## UI 설계 메모

### 모듈 관리 화면

- 탭:
  - `Stage`
  - `Job`
  - `Task`
  - `Script Template`
- 패널:
  - 업로드 패널
  - 활성 모듈 테이블
  - 최근 재로드 결과 패널
  - 오류 상세 패널

### 주요 액션

- 파일 업로드
- 유효성 검증 결과 확인
- 활성화
- 비활성화
- 재로드 실행

## 데이터 흐름

1. 사용자가 파일을 업로드한다.
2. 백엔드는 `uploads/` 아래에 저장하고 DB version row를 만든다.
3. 검증 성공 시 사용자가 활성화를 요청한다.
4. 활성화 서비스가 `active/` 경로에 반영한다.
5. 재로드 API가 active 경로를 스캔하고 runtime registry를 갱신한다.
6. 결과는 snapshot과 entry로 저장되어 UI에서 조회된다.

## 단계별 구현 제안

1. Django 모델과 migration 초안을 정의한다.
2. 관리 디렉터리 path resolver와 file writer를 작성한다.
3. 업로드 API와 기본 validation을 추가한다.
4. 활성화/비활성화 API를 추가한다.
5. 재로드 API와 snapshot 기록을 추가한다.
6. 관리자 UI를 추가한다.

## 수용 기준

- 업로드, 활성화, 재로드, 로딩 상태 조회를 위한 백엔드 엔터티가 정의된다.
- 파일시스템 경로와 DB 추적 모델의 역할 분리가 정의된다.
- 관리자 API 엔드포인트와 책임이 정의된다.
- 로딩 결과 snapshot/entry 추적 구조가 정의된다.

## 오픈 이슈

- Django Admin으로 먼저 시작할지 별도 운영 UI를 바로 만들지 결정 필요
- 업로드 승인 워크플로우를 1차에 포함할지 결정 필요
- 활성화 시 이전 active 파일을 soft backup으로 남길지 결정 필요
