# Detailed Design: BuildUnit 중심 백엔드 모델 ERD

## 문서 메타데이터

- 문서 일자: 2026-03-25
- 문서 유형: Detailed Design
- 관련 설계: [./buildunit_backend_model_draft.md](./buildunit_backend_model_draft.md)
- 관련 설계: [./backend_model_generalization_review.md](./backend_model_generalization_review.md)

## 요약

이 문서는 `BuildUnit` 중심 신규 백엔드 모델 초안을 ERD 관점에서 정리한다. 구현 재구성은 본 ERD를 기준 관계 모델로 사용한다.

## ERD

```mermaid
erDiagram
    Project ||--o{ Repository : has
    Project ||--o{ BuildUnit : has
    Repository ||--o{ BuildUnit : scopes
    BuildUnit ||--o{ BuildUnitDefinition : versions
    BuildUnit ||--o{ BuildVersion : has
    BuildUnit ||--o{ BuildExecution : records
    BuildExecution ||--o{ ExecutionArtifact : produces
    BuildExecution ||--o{ StaticAnalysisResult : includes
    BuildVersion ||--o{ DeploymentExecution : deploys
    DeploymentTarget ||--o{ DeploymentExecution : receives
    BuildUnit ||--o{ BambooPublishExecution : publishes
    BuildUnit ||--|| BambooBuildUnit : bamboo_detail
    BambooBuildUnit ||--o{ BambooBuildInfo : has
    BuildUnit ||--|| JenkinsBuildUnit : jenkins_detail

    Project {
        uuid id PK
        string project_key
        string name
        string ci_provider
        string status
        uuid representative_repository_id FK
    }

    Repository {
        uuid id PK
        uuid project_id FK
        string repo_type
        string repo_slug
        string clone_url
        string default_branch
        boolean is_representative
    }

    BuildUnit {
        uuid id PK
        uuid project_id FK
        uuid repository_id FK
        string ci_provider
        string unit_type
        string external_key
        string display_name
        string language
        string compiler
        string lifecycle_status
        boolean is_enabled
        uuid latest_version_id FK
    }

    BuildUnitDefinition {
        uuid id PK
        uuid build_unit_id FK
        int version
        string year
        string source_kind
        string definition_hash
        boolean is_active
    }

    BuildVersion {
        uuid id PK
        uuid build_unit_id FK
        string version_text
        int version_major
        int version_minor
        int version_patch
        string commit_hash
        string branch_name
        string branch_kind
        boolean is_latest
        uuid latest_execution_id FK
    }

    BuildExecution {
        uuid id PK
        uuid build_unit_id FK
        uuid build_version_id FK
        string execution_number
        string external_execution_key
        string trigger_type
        string branch_name
        string commit_hash
        string status
        string stage_name
        string job_name
        string task_name
        datetime queued_at
        datetime started_at
        datetime finished_at
    }

    ExecutionArtifact {
        uuid id PK
        uuid build_execution_id FK
        string artifact_type
        string name
        string path
        string download_url
    }

    StaticAnalysisResult {
        uuid id PK
        uuid build_execution_id FK
        string tool_name
        string status
        string summary
    }

    DeploymentTarget {
        uuid id PK
        string name
        string target_type
        string status
        boolean approval_required
    }

    DeploymentExecution {
        uuid id PK
        uuid build_version_id FK
        uuid deployment_target_id FK
        string status
        string requested_by
        string approved_by
        uuid rollback_of_id FK
        datetime started_at
        datetime finished_at
    }

    BambooBuildUnit {
        uuid build_unit_id PK, FK
        string bamboo_project_key
        string plan_key
        string build_id
        string repository_linkage_mode
        string application_link
        string static_analysis_tool_version
        string coverity_project
    }

    BambooBuildInfo {
        uuid id PK
        uuid bamboo_build_unit_id FK
        string build_key
        string operating_system
        string language
        string compiler
        string pre_process
        string build_command
        string clean_command
        string coverity_stream
        string build_sub_path
    }

    BambooPublishExecution {
        uuid id PK
        uuid build_unit_id FK
        string status
        string message
        int return_code
    }

    JenkinsBuildUnit {
        uuid build_unit_id PK, FK
        string job_path
        string job_type
        string folder_path
        string pipeline_kind
    }
```

## 관계 해설

- `Project -> Repository`
  - 프로젝트는 여러 저장소를 가질 수 있다.
- `Project -> BuildUnit`
  - 프로젝트는 여러 build unit을 가질 수 있다.
- `Repository -> BuildUnit`
  - 하나의 저장소 아래 여러 build unit이 연결될 수 있다.
- `BuildUnit -> BuildUnitDefinition`
  - 정의 스냅샷은 build unit 단위로 누적된다.
- `BuildUnit -> BuildVersion -> BuildExecution`
  - 버전과 실행 이력의 기준 단위를 `BuildUnit`으로 통일한다.
- `BuildUnit -> BambooBuildUnit` / `BuildUnit -> JenkinsBuildUnit`
  - provider 전용 상세는 코어 모델과 1:1로 분리한다.
- `BambooBuildUnit -> BambooBuildInfo`
  - Bamboo에서만 필요한 세부 build key 구조를 별도 모델로 유지한다.

## 1차 구현 시 필수 관계

- `Project -> Repository`
- `Project -> BuildUnit`
- `BuildUnit -> BuildUnitDefinition`
- `BuildUnit -> BuildVersion`
- `BuildUnit -> BuildExecution`
- `BuildUnit -> BambooBuildUnit`
- `BambooBuildUnit -> BambooBuildInfo`
- `BuildUnit -> JenkinsBuildUnit`

## 2차 구현 시 확장 관계

- `BuildExecution -> ExecutionArtifact`
- `BuildVersion -> DeploymentExecution -> DeploymentTarget`
- `BuildExecution -> StaticAnalysisResult`
- `BuildUnit -> BambooPublishExecution`

## 메모

- 본 ERD는 신규 스키마 기준이다.
- 기존 `BuildPlan`, `BuildPlanBuildInfo`, `ProjectBuild`, `BuildPlanDefinition` 계열은 이 ERD에 포함하지 않는다.
- provider별 시스템 운영 현황 스냅샷은 코어 `SystemStatusSnapshot` 또는 provider별 상세 snapshot으로 후속 확장 가능하다.
