# Detailed Design: 프로젝트 등록 및 Specs 생성 준비도

## 문서 메타데이터

- 문서 일자: 2026-03-19
- 문서 유형: Detailed Design
- 관련 요구사항: [../../requirements/issues/STORY-21-project-registration.md](../../requirements/issues/STORY-21-project-registration.md)
- 관련 요구사항: [../../requirements/issues/STORY-22-project-read-update.md](../../requirements/issues/STORY-22-project-read-update.md)
- 관련 요구사항: [../../requirements/issues/STORY-26-operations-api-standardization.md](../../requirements/issues/STORY-26-operations-api-standardization.md)

## 요약

이 문서는 프로젝트 등록/수정 API와 프로젝트별 Specs 생성 준비도 계산 로직의 함수 단위 설계를 정리한다. 현재 설계 목표는 별도 스키마 마이그레이션 없이 기존 `Project`, `ProjectRepository`, `ProjectBuild`, `BuildPlan`, `BuildPlanDefinition` 모델 위에서 운영 입력과 생성기 연계 가능 여부를 계산하는 것이다.

## 배경

- 새 요구사항은 등록된 프로젝트가 충분한 메타데이터를 갖추면 Specs 생성기와 연동될 수 있어야 한다.
- 현재 구현은 조회 중심이며, 프로젝트 등록/수정과 생성 가능 상태 판정이 부족했다.
- 빠른 검증을 위해 기존 DB 구조를 유지하면서 서비스 계층과 selector 계층에서 계산을 보강한다.

## 목표

- 프로젝트 등록/수정 요청을 단일 서비스 계층에서 검증하고 저장한다.
- 저장 직후 상세 응답을 재조회해 API/UI가 동일한 응답 구조를 사용하게 한다.
- 프로젝트/빌드 단위의 Specs 생성 준비도를 selector에서 계산한다.

## 비목표

- 실제 Specs 생성기 호출
- Bamboo 플랜 등록 실행
- 사용자 권한 검사 상세 구현

## 함수 설계

### `apps.buildmeta.services.projects.create_project(payload)`

- 책임: 신규 프로젝트 등록 요청을 검증하고 저장한다.
- 입력: `jiraProjectKey`, `bitbucketProjectKey`, `representativeRepoSlug`, `repositories[]`, `builds[]`
- 출력: `get_project_detail(...)` 기반 상세 딕셔너리
- 주요 단계:
  1. payload를 dict로 정규화한다.
  2. `jiraProjectKey` 존재와 중복 여부를 확인한다.
  3. 저장소/빌드 입력의 중복과 필수값을 검증한다.
  4. `_save_project(None, data)`를 호출한다.
- 실패 조건:
  - 프로젝트 키 누락
  - 기존 프로젝트와 키 충돌
  - 저장소 대표 플래그 중복
  - 빌드 `buildId`/`planKey` 중복

### `apps.buildmeta.services.projects.update_project(jira_project_key, payload)`

- 책임: 기존 프로젝트의 메타데이터와 연결 정보를 갱신한다.
- 출력: 성공 시 상세 딕셔너리, 미존재 시 `None`
- 주요 단계:
  1. 대상 프로젝트 존재 여부를 확인한다.
  2. `_save_project(existing_key, data)`를 호출한다.
- 설계 이유:
  - 생성/수정 로직의 공통 저장 동작은 `_save_project` 하나로 통합한다.

### `apps.buildmeta.services.projects._save_project(existing_jira_project_key, data)`

- 책임: 프로젝트, 저장소, 빌드 연결을 트랜잭션 안에서 저장한다.
- 주요 단계:
  1. 저장소/빌드 검증 함수를 먼저 호출한다.
  2. `Project.get_or_create(...)`로 프로젝트를 확보한다.
  3. 대표 저장소 slug를 `_resolve_representative_repo_slug(...)`로 계산한다.
  4. `_upsert_repositories(...)`로 저장소 메타데이터를 반영한다.
  5. `_upsert_builds(...)`로 `BuildPlan`, `ProjectBuild`를 반영한다.
  6. `get_project_detail(...)`로 재조회해 응답을 통일한다.
- 트랜잭션 경계:
  - 프로젝트/저장소/빌드 연결은 모두 한 번에 성공하거나 실패해야 한다.

### `apps.buildmeta.services.projects._validate_repositories(repositories)`

- 책임: 저장소 입력 검증
- 검증 규칙:
  - `repoSlug` 필수
  - 동일 요청 내 중복 `repoSlug` 금지
  - `isRepresentative=True`는 최대 1건

### `apps.buildmeta.services.projects._validate_builds(builds)`

- 책임: 빌드 입력 검증
- 검증 규칙:
  - `buildName`, `buildId`, `planKey` 필수
  - 동일 요청 내 `buildId` 중복 금지
  - 동일 요청 내 `planKey` 중복 금지

### `apps.buildmeta.services.projects._upsert_builds(project, builds)`

- 책임: 요청 빌드 목록을 `BuildPlan`과 `ProjectBuild`에 반영한다.
- 핵심 제약:
  - 기존 `planKey`가 다른 `buildId`와 연결돼 있으면 오류
  - 기존 `BuildPlan`이 다른 프로젝트에 연결돼 있으면 오류
- 이유:
  - 한 플랜이 여러 프로젝트에 중복 소속되는 상태를 막아야 한다.

### `apps.buildmeta.selectors.projects.list_project_summaries()`

- 책임: 프로젝트 목록 화면/API에 필요한 요약 정보를 계산한다.
- 추가 계산 항목:
  - `generationReady`
  - `generationReadinessIssues`
  - `activeDefinitionCount`
  - `readyBuildCount`
- 구현 방식:
  - 활성 정의만 prefetch 해서 계산 비용을 줄인다.
  - 기존 경고 태그와 생성 준비도 이슈를 합쳐 `warningTags`를 구성한다.

### `apps.buildmeta.selectors.projects.get_project_detail(jira_project_key)`

- 책임: 프로젝트 상세 화면/API에 필요한 메타데이터와 준비도를 반환한다.
- 빌드별 추가 필드:
  - `buildId`
  - `generationReady`
  - `activeDefinitionYear`
  - `latestVersion`
  - `latestSuccess`

### `apps.buildmeta.selectors.projects._build_generation_status(project, repositories, builds)`

- 책임: 프로젝트 단위 Specs 생성 준비도를 계산한다.
- 현재 준비 완료 기준:
  - 저장소 1개 이상 존재
  - 빌드 1개 이상 존재
  - 대표 저장소 slug가 존재하고 실제 저장소 메타데이터와 일치
  - 모든 연결 빌드가 활성 정의를 1개 이상 가짐
- 반환 구조:
  - `generationReady`
  - `generationReadinessIssues`
  - `readyBuildCount`
  - `activeDefinitionCount`
  - `totalBuildCount`

## 데이터 흐름

1. API router가 입력 스키마를 검증한다.
2. service 계층이 프로젝트/저장소/빌드 데이터를 저장한다.
3. selector 계층이 활성 정의 연결 상태를 포함한 상세 응답을 계산한다.
4. API와 UI는 같은 selector 결과를 사용한다.

## 수용 기준

- 프로젝트 등록과 수정이 API로 가능하다.
- 프로젝트 목록/상세에서 생성 준비도를 볼 수 있다.
- 활성 정의가 없는 프로젝트는 준비 필요 상태로 식별된다.
- 대표 저장소 불일치 같은 메타데이터 문제를 준비도 이슈로 노출할 수 있다.

## 오픈 이슈

- 생성 준비 완료 시 실제 Specs 생성기를 동기 호출할지 비동기 작업으로 분리할지 결정 필요
- 준비도 기준에 `buildCommand`, `runtimeRequirements` 같은 정의 내부 필수값까지 포함할지 결정 필요
