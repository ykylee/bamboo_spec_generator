# Detailed Design: 다중 CI 콘솔 모드 전환 및 공통 도메인 모델

## 문서 메타데이터

- 문서 일자: 2026-03-25
- 문서 유형: Detailed Design
- 관련 요구사항: [../../requirements/issues/STORY-29-multi-ci-mode-switching.md](../../requirements/issues/STORY-29-multi-ci-mode-switching.md)
- 관련 요구사항: [../../requirements/issues/STORY-30-ci-theme-and-copy-guidelines.md](../../requirements/issues/STORY-30-ci-theme-and-copy-guidelines.md)
- 관련 요구사항: [../../requirements/issues/STORY-31-jenkins-project-and-job-registration.md](../../requirements/issues/STORY-31-jenkins-project-and-job-registration.md)
- 관련 요구사항: [../../requirements/issues/STORY-32-ci-provider-domain-model.md](../../requirements/issues/STORY-32-ci-provider-domain-model.md)
- 관련 요구사항: [../../requirements/issues/STORY-33-jenkins-system-operations-visibility.md](../../requirements/issues/STORY-33-jenkins-system-operations-visibility.md)

## 요약

이 문서는 Bamboo 중심 운영 콘솔을 Bamboo/Jenkins 공통 CI 콘솔로 확장하기 위한 상세 설계를 정리한다. 핵심은 `ci_provider` 기반 공통 도메인 모델, 상단 모드 전환, 공통 API 응답 구조, Jenkins 프로젝트/잡 등록 구조, 도구별 시스템 운영 현황 조회 구조다.

## 배경

- 현재 프로젝트/빌드/운영 화면은 Bamboo plan 중심으로 구성되어 있다.
- 새 요구사항은 Bamboo 관리와 Jenkins 관리를 하나의 콘솔에서 전환할 수 있어야 한다.
- 공통 구조를 유지하지 않으면 UI와 API가 도구별로 갈라져 유지보수 비용이 급격히 증가한다.

## 목표

- 상단 모드 전환을 중심으로 공통 콘솔 구조를 정의한다.
- Bamboo plan과 Jenkins job을 공통 모델로 수용할 수 있게 한다.
- Jenkins 프로젝트/잡 등록을 기존 프로젝트 등록 흐름에 맞춰 확장한다.
- Bamboo/Jenkins 시스템 운영 현황을 공통 API/화면 패턴으로 표현한다.

## 비목표

- 실제 Jenkins job 생성 자동화
- Jenkins pipeline 스크립트 생성 규칙 확정
- Bamboo/Jenkins 외 추가 CI 도구의 세부 설계

## 설계안

### 1. 상단 모드 전환

- 최상위 네비게이션에 `Bamboo 관리`, `Jenkins 관리` 전환 컨트롤을 둔다.
- 현재 선택된 `ci_provider`는 URL 세그먼트로 표현한다.
  - 예: `/ui/bamboo/projects/`, `/ui/jenkins/projects/`
- 같은 화면 유형은 provider만 바뀌고 경로 패턴은 최대한 유지한다.
- 서버 렌더링 템플릿과 API 클라이언트는 현재 provider를 공통 컨텍스트 값으로 사용한다.

### 2. 공통 도메인 모델

#### 공통 추상 개념

- `Project`
  - 운영 콘솔 상위 식별 단위
- `Repository`
  - 소스 저장소 메타데이터
- `BuildUnit`
  - Bamboo의 `plan`, Jenkins의 `job`을 감싸는 공통 추상 단위
- `SystemStatus`
  - CI 도구 자체의 노드/에이전트/큐 상태

#### 권장 필드

- `Project`
  - `jira_project_key`
  - `display_name`
  - `description`
  - `ci_provider`
  - `status`
- `BuildUnit`
  - `ci_provider`
  - `external_key`
  - `display_name`
  - `repository_slug`
  - `language`
  - `compiler`
  - `lifecycle_status`
- `SystemStatusItem`
  - `ci_provider`
  - `resource_type`
  - `resource_name`
  - `online`
  - `busy`
  - `queue_size`
  - `labels`

### 3. 등록 모델 확장

#### Bamboo 등록

- Bamboo도 공통 `BuildUnit` 위에 provider 상세 모델을 붙이는 구조로 재정의한다.
- provider 값은 `bamboo`로 고정한다.
- Bamboo 전용 필드는 `BambooBuildUnit`, `BambooBuildInfo` 같은 상세 모델로 분리한다.

#### Jenkins 등록

- Jenkins 프로젝트도 기존 `Project` 구조를 재사용한다.
- `BuildUnit` 또는 동등한 모델에서 Jenkins job을 표현한다.
- Jenkins 전용 필드는 우선 확장 속성으로 분리한다.
  - `job_path`
  - `job_type`
  - `folder_path`

#### 등록 입력

- 공통 필드
  - 프로젝트 식별자
  - 표시 이름
  - 저장소 연결 정보
  - 빌드 단위 이름
  - 언어
  - 컴파일러
- Bamboo 전용 필드
  - `planKey`
  - `buildKey`
- Jenkins 전용 필드
  - `jobPath`
  - `jobType`

### 4. API 설계 방향

#### 공통 목록 API

- `GET /api/v1/{provider}/projects/`
- `GET /api/v1/{provider}/projects/{projectKey}/`
- `GET /api/v1/{provider}/build-units/`
- `GET /api/v1/{provider}/build-units/{externalKey}/`

#### 등록 API

- `POST /api/v1/{provider}/projects/`
- `PATCH /api/v1/{provider}/projects/{projectKey}/`
- `POST /api/v1/{provider}/build-units/`
- `PATCH /api/v1/{provider}/build-units/{externalKey}/`

#### 시스템 현황 API

- `GET /api/v1/{provider}/system-status/summary`
- `GET /api/v1/{provider}/system-status/resources`
- `GET /api/v1/{provider}/system-status/queue`

#### 응답 공통 원칙

- 공통 필드는 provider와 무관하게 동일 이름을 사용한다.
- 도구별 상세는 `providerDetails` 하위 객체에 둔다.
- UI는 공통 필드를 기본 표시값으로 사용하고, 필요할 때만 `providerDetails`를 펼친다.

### 5. 시스템 현황 표현

#### Bamboo

- resource type:
  - `agent`
  - `job`
  - `queue_item`
- provider details 예시:
  - `capabilities`
  - `lastHeartbeat`
  - `agentType`

#### Jenkins

- resource type:
  - `node`
  - `executor`
  - `queue_item`
- provider details 예시:
  - `labels`
  - `executors`
  - `offlineCause`

### 6. UI 흐름

#### 프로젝트 목록

- 상단 provider 전환
- 공통 검색/필터
- 공통 KPI 카드
- provider별 빈 상태 문구만 세부 조정

#### 프로젝트 상세

- 공통 메타데이터 패널
- 저장소 패널
- 빌드 단위 패널
- Bamboo면 Plan/Build Info 패널
- Jenkins면 Job Details 패널

#### 시스템 현황 화면

- 상단 summary 카드
- 리소스 테이블
- 큐/대기열 패널
- provider별 세부 컬럼 일부만 교체

## 데이터 흐름

1. 사용자가 상단에서 provider를 선택한다.
2. UI는 provider 포함 경로로 이동한다.
3. 서버는 provider 기준 selector/service를 호출한다.
4. selector는 공통 응답 스키마를 구성한다.
5. provider별 확장 정보는 `providerDetails`로 병합한다.

## 단계별 구현 제안

1. 기존 `BuildPlan` 중심 신규 작업을 중단하고 `BuildUnit` 중심 신규 스키마를 먼저 정의한다.
2. `ci_provider` 필드와 공통 API 경로를 도입한다.
3. 프로젝트 목록/상세 화면에 provider 컨텍스트를 주입한다.
4. Bamboo/Jenkins provider 상세 모델과 selector/service를 새 구조 기준으로 작성한다.
5. Jenkins 프로젝트/잡 등록 API와 UI를 추가한다.
6. Bamboo/Jenkins 시스템 현황 API를 각각 구현한다.
7. 공통 테마 토큰과 문구 정리를 반영한다.

## 수용 기준

- provider 기반 URL/상태 모델이 정의된다.
- Bamboo plan과 Jenkins job의 공통 API 표현이 정의된다.
- Jenkins 등록 필드와 공통 등록 필드의 경계가 정의된다.
- Bamboo/Jenkins 시스템 현황 응답 구조가 정의된다.

## 오픈 이슈

- provider별 권한 모델을 초기에는 공통으로 둘지 분리할지 결정 필요
- Django 템플릿 기반 UI에서 provider 전환을 어느 수준까지 서버 렌더링으로 유지할지 결정 필요
