# Detailed Design Review: CI/CD 공통 백엔드 모델 일반화와 Provider 확장 방식 검토

## 문서 메타데이터

- 문서 일자: 2026-03-25
- 문서 유형: Detailed Design Review
- 관련 요구사항: [../../requirements/issues/STORY-32-ci-provider-domain-model.md](../../requirements/issues/STORY-32-ci-provider-domain-model.md)
- 관련 요구사항: [../../requirements/issues/STORY-31-jenkins-project-and-job-registration.md](../../requirements/issues/STORY-31-jenkins-project-and-job-registration.md)
- 관련 설계: [./multi_ci_console_and_provider_model.md](./multi_ci_console_and_provider_model.md)
- 관련 결정사항: [./multi_ci_console_decisions.md](./multi_ci_console_decisions.md)

## 요약

현재 백엔드 모델은 `BuildPlan`을 중심으로 Bamboo 개념에 강하게 결합돼 있다. 따라서 CI/CD 공통 데이터를 일반화하고 Bamboo/Jenkins를 하위 provider로 붙이는 구조는 가능하지만, Django의 다중 테이블 상속을 핵심 패턴으로 삼는 방식은 현재 코드베이스와 맞지 않는다. 현 시점 권장안은 기존 구조 호환을 포기하고 공통 코어 모델 + provider별 상세 모델을 `OneToOneField`로 분리하는 composition 방식으로 재구축하는 것이다.

## 현재 상태 진단

현재 `backend/apps/buildmeta/models/core.py` 기준 주요 결합은 다음과 같다.

- `BuildPlan`
  - 사실상 Bamboo `plan`을 대표하는 코어 엔터티 역할을 하고 있다.
- `BuildPlanBuildInfo`
  - `build_plan` FK를 직접 참조하며 Bamboo 플랜 하위 빌드 정보 구조를 전제로 한다.
- `ProjectBuild`
  - `BuildPlan`에 `OneToOneField`로 연결되어 있다.
- `BuildPlanDefinition`
  - 활성 정의와 정의 이력이 `BuildPlan` 기준으로 설계돼 있다.
- `BuildVersion`, `BuildExecution`
  - 모두 `BuildPlan`을 기준으로 버전과 실행 이력을 저장한다.
- `BambooPublishExecution`
  - Bamboo 전용 이력 모델이 이미 분리돼 있다.

서비스/셀렉터 계층 결합도도 높다.

- `services/projects.py`
  - `buildId + planKey -> BuildPlan` 해석에 직접 결합돼 있다.
- `services/definitions.py`
  - JSON import가 곧 Bamboo 정의 import라는 전제를 둔다.
- `selectors/definitions.py`
  - 활성 정의/prepare context/preview가 모두 Bamboo Specs 생성 payload를 만든다.
- `services/bamboo.py`
  - Bamboo 전용 연동이 `BuildPlan`을 직접 참조한다.

즉, 현재 `BuildPlan`은 이름만 일반 객체가 아니라 실제로는 시스템의 중심 aggregate다.

## 검토 질문

### 1. 공통 모델을 만들고 Bamboo/Jenkins를 상속으로 붙일 수 있는가

- 가능:
  - 기술적으로는 가능하다.
- 단서:
  - Django의 모델 상속 방식에 따라 현실성이 크게 달라진다.

## 상속 방식별 검토

### A. Abstract Base Class

- 방식:
  - 공통 필드를 추상 베이스에 두고 `BambooBuildPlan`, `JenkinsJob` 같은 별도 모델이 상속한다.
- 장점:
  - 테이블 분리가 명확하다.
  - provider별 필드 설계가 자유롭다.
- 단점:
  - 공통 테이블이 없어서 `BuildVersion`, `BuildExecution`, `ProjectBuild` 같은 기존 참조 모델이 하나의 대상에 연결되기 어렵다.
  - 결국 GenericForeignKey나 다중 nullable FK 같은 우회 구조가 필요해진다.
- 판단:
  - 현재 코드베이스에는 부적합하다.

### B. Django Multi-table Inheritance

- 방식:
  - `BuildUnit` 같은 부모 모델을 만들고 `BambooBuildUnit`, `JenkinsBuildUnit`이 상속한다.
- 장점:
  - 공통 PK를 공유할 수 있어 "상속" 모양은 가장 자연스럽다.
  - 공통 FK는 부모 모델 하나만 보면 된다.
- 단점:
  - 조회 시 join 비용이 늘어난다.
  - Django ORM에서 부모/자식 타입 분기가 잦아지면 코드가 빠르게 복잡해진다.
  - 현재 `BuildPlan` 중심 유니크 제약과 selector/service 코드를 대거 수정해야 한다.
  - Admin, serializer, query 최적화가 까다로워진다.
- 판단:
  - 가능은 하지만 1차 마이그레이션 전략으로는 비권장이다.

### C. 공통 코어 모델 + Provider 상세 모델 조합

- 방식:
  - 공통 엔터티를 별도 모델로 두고, Bamboo/Jenkins 상세는 `OneToOneField`로 분리한다.
- 장점:
  - 새 구조를 처음부터 명확하게 정의할 수 있다.
  - 공통 FK는 코어 모델 하나만 바라보면 된다.
  - provider별 상세 필드는 명확히 분리할 수 있다.
  - Bamboo 전용 publish/history 같은 모델도 자연스럽게 유지할 수 있다.
- 단점:
  - "진짜 상속"은 아니다.
  - 서비스 계층에서 provider 분기가 필요하다.
- 판단:
  - 현재 코드베이스에 가장 적합한 방법이다.

## 권장안

### 결론

- `상속이 가능한가`: 가능하다.
- `권장하는가`: Django multi-table inheritance 중심 설계는 비권장이다.
- `권장 방식`: 공통 코어 모델 + provider별 상세 모델의 composition 방식
- `전환 정책`: 기존 구조 호환보다 신규 구조 재구축을 우선하고, 기존 데이터는 삭제 가능 대상으로 본다.

### 권장 모델 구조

#### 공통 코어

- `CiProvider`
  - `code`: `bamboo`, `jenkins`
  - `name`
- `Project`
  - 기존 유지 + `ci_provider`
- `BuildUnit`
  - 기존 `BuildPlan`을 대체하는 공통 빌드 단위
  - 권장 필드:
    - `project`
    - `ci_provider`
    - `external_key`
    - `display_name`
    - `lifecycle_status`
    - `latest_version`
- `BuildUnitDefinition`
  - 기존 `BuildPlanDefinition` 일반화
- `BuildVersion`
  - `build_unit` FK
- `BuildExecution`
  - `build_unit` FK
- `ProjectBuild`
  - `build_unit` FK

#### Provider 상세

- `BambooBuildUnit`
  - `build_unit = OneToOneField(BuildUnit)`
  - `plan_key`
  - `build_id`
  - `repository_linkage_mode_override`
  - `static_analysis_tool_version`
  - `coverity_project`
- `BambooBuildInfo`
  - `bamboo_build_unit` FK
  - 기존 `BuildPlanBuildInfo` 성격 유지
- `JenkinsBuildUnit`
  - `build_unit = OneToOneField(BuildUnit)`
  - `job_path`
  - `job_type`
  - `folder_path`
- `BambooPublishExecution`
  - `bamboo_build_unit` 또는 `build_unit` + provider validation 방식으로 유지 가능

## 왜 이 방식이 현재 구조와 맞는가

### 1. Bamboo 중심 Aggregate를 제거할 수 있다.

현재 많은 모델이 `BuildPlan`을 직접 FK로 본다. 이번 전환에서는 이 결합을 유지하지 않고, 공통 `BuildUnit` 중심으로 새 FK 구조를 다시 세우는 편이 더 일관된다.

### 2. Bamboo 전용 모델이 이미 존재한다.

`BambooPublishExecution`처럼 provider 전용 이력이 이미 존재하므로, 공통/전용 분리 전략이 코드베이스와 잘 맞는다.

### 3. Jenkins는 Bamboo와 하위 구조가 다르다.

Bamboo는 plan -> build info / stage / job 쪽으로 확장되어 있고, Jenkins는 job path, folder, node/executor, queue 개념이 중심이다. 강한 상속보다 provider별 상세 테이블 분리가 자연스럽다.

## 권장 재구축 순서

### 1단계

- 기존 `BuildPlan` 중심 모델을 기준으로 한 신규 기능 추가를 중단한다.
- 공통 `Project`, `Repository`, `BuildUnit`, `BuildUnitDefinition`, `BuildVersion`, `BuildExecution` 초안을 먼저 확정한다.

### 2단계

- `BambooBuildUnit`, `BambooBuildInfo`, `JenkinsBuildUnit` 같은 provider 상세 모델을 정의한다.
- 기존 `BuildPlan`, `BuildPlanBuildInfo`, `BuildPlanDefinition`, `ProjectBuild`는 폐기 예정 모델로 본다.

### 3단계

- selector/service/API를 `BuildUnit + provider adapter` 기준으로 다시 작성한다.
- Bamboo 연동 로직도 `BuildPlan` 직접 참조 대신 `BambooBuildUnit`을 기준으로 옮긴다.

### 4단계

- 기존 로컬 개발 DB와 기존 운영 데이터는 마이그레이션 대상이 아니라 삭제 후 신규 스키마 재생성 대상으로 본다.
- 초기 적재가 필요하면 JSON 또는 신규 등록 UI를 통해 다시 적재한다.

## 구현 시 주의점

- `plan_key`, `build_id` 같은 Bamboo 식별자는 공통 키가 아니라 provider 상세로 내려야 한다.
- `jira_project_key == bitbucket_project_key` 같은 현재 import 가정은 Bamboo JSON import 전용 로직으로 분리해야 한다.
- `BuildVersion.branch_kind`는 Jenkins에 그대로 맞지 않을 수 있으므로 공통 규칙인지 provider 규칙인지 재검토가 필요하다.
- `SystemSetting`도 장기적으로는 provider namespace를 두는 편이 낫다.
  - 예: `bamboo.server.url`, `jenkins.server.url`
- 기존 데이터 정합성을 맞추기 위한 호환 필드나 백필 로직은 우선순위에서 제외한다.

## 최종 판단

- 가능 여부:
  - 가능
- 추천 여부:
  - "일반화된 공통 코어 + Bamboo/Jenkins 상속"이라는 목표 자체는 타당
  - 다만 구현 패턴은 Django 상속보다 composition이 더 적합
- 추천안:
  - `BuildUnit` 공통화 + `BambooBuildUnit`/`JenkinsBuildUnit` 상세 분리
  - 기존 `BuildPlan` 계열은 호환 유지 없이 폐기 전제로 교체
  - 상속은 문서/개념 수준으로 두고, 실제 DB 모델은 `OneToOneField` 기반 확장으로 구현

## 오픈 이슈

- `BuildPlanBuildInfo`를 Bamboo 전용 모델로 명확히 재명명할지 결정 필요
- Jenkins에서 버전/실행 이력의 공통 필드를 어디까지 강제할지 결정 필요
