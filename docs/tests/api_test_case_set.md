# API 테스트 케이스 세트

## 문서 메타데이터

- 문서 일자: 2026-03-24
- 문서 유형: Manual API Test Case Set
- 대상 범위: 프로젝트, 빌드 플랜, 실행 이력, 운영 설정, Specs draft
- 관련 요구사항: [../requirements/SRS.md](../requirements/SRS.md)
- 관련 설계: [../designs/Design.md](../designs/Design.md), [../designs/SAD.md](../designs/SAD.md)

## 요약

이 문서는 현재 구현된 Ninja API를 기준으로 한 수동 E2E 테스트 케이스 세트다. 생성기와 운영 UI가 실제로 의존하는 조회/적재 경로를 확인하는 데 초점을 두고, 배포/릴리스/사용자 권한처럼 아직 API가 없는 범위는 제외한다.

## 범위

### 포함

- 프로젝트 목록/상세 조회
- 프로젝트 등록/수정
- 활성 정의 조회 및 prepare-context 조회
- 실행 시작/종료/정적분석 결과 적재
- Coverity/Bamboo 운영 설정 조회/수정
- Specs draft 초기화

### 제외

- UI 렌더링 자체 검증
- Bamboo 서버 실연동
- 사용자/권한 관리
- 배포/릴리스 관리
- DB 직접 조회

## 테스트 데이터 준비 가이드

- `Authorization: Bearer <token>` 요청이 가능한 토큰을 준비한다.
- 최소 1개의 프로젝트, 1개의 저장소, 1개의 빌드 플랜, 1개의 BuildInfo를 준비한다.
- 동일 커밋 재빌드와 실패 이력 검증을 위해 같은 플랜에 대해 2회 이상 실행할 데이터를 준비한다.
- `create_if_missing`와 `linked` 동작을 비교하려면 repository linkage mode를 바꿔가며 검증할 수 있는 설정값을 준비한다.

## 추적 기준

- FR-12: 프로젝트/저장소 메타데이터 조회
- FR-16: 생성기 연동
- FR-17: 운영 백엔드
- FR-18: API
- FR-21: 프로젝트 등록 및 구성 관리
- FR-22: 프로젝트 정보 조회 및 수정
- FR-24: 빌드 현황 조회
- FR-26: 운영 관리 API 우선 원칙

## 테스트 케이스

| TC ID | 엔드포인트 | 목적 | 사전조건 | 절차 | 기대 결과 | 추적 |
| --- | --- | --- | --- | --- | --- | --- |
| API-AUTH-001 | 공통 | 인증 헤더 필요성 확인 | 유효한 토큰 없음 | 1. 인증 헤더 없이 임의 엔드포인트 호출 | 인증 실패가 반환된다. | FR-26 |
| API-PROJ-001 | `GET /api/v1/projects/` | 프로젝트 목록 조회 | 프로젝트 데이터 1건 이상 | 1. 목록 호출 | 프로젝트 요약 목록이 반환되고 generation readiness, warning tags, activeDefinitionCount가 포함된다. | FR-12, FR-18, FR-26 |
| API-PROJ-002 | `POST /api/v1/projects/` | 프로젝트 등록 | 신규 프로젝트 payload 준비 | 1. `jiraProjectKey`, `bitbucketProjectKey`, `repositories`, `builds` 포함 payload 제출 | 프로젝트가 생성되고 생성 결과 payload가 반환된다. | FR-21, FR-26 |
| API-PROJ-003 | `GET /api/v1/projects/{jiraProjectKey}` | 프로젝트 상세 조회 | 대상 프로젝트 존재 | 1. 상세 호출 | 프로젝트 메타데이터, repositories, builds, generation readiness 정보가 반환된다. | FR-12, FR-18 |
| API-PROJ-004 | `PUT /api/v1/projects/{jiraProjectKey}` | 프로젝트 수정 | 대상 프로젝트 존재 | 1. Bitbucket key/대표 저장소/repositories/builds 수정 payload 제출 | 수정된 프로젝트가 반환되고 제거된 저장소/빌드는 반영된다. | FR-22, FR-26 |
| API-PROJ-005 | `GET /api/v1/projects/{jiraProjectKey}` | 없는 프로젝트 처리 | 대상 프로젝트 없음 | 1. 존재하지 않는 Jira key로 호출 | 404가 반환된다. | FR-18 |
| API-PLAN-001 | `GET /api/v1/build-plans/{planKey}/active-definition` | 활성 정의 조회 | 대상 빌드 플랜 존재 | 1. 활성 정의 호출 | `planKey`, `buildId`, `year`, `definition`이 반환된다. | FR-16, FR-18 |
| API-PLAN-002 | `GET /api/v1/build-plans/{planKey}/prepare-context` | 준비 컨텍스트 조회 | 대상 프로젝트/빌드 존재 | 1. prepare-context 호출 | project, currentRepository, repositories, variables가 반환된다. | FR-12, FR-16, FR-18 |
| API-PLAN-003 | `GET /api/v1/build-plans/{planKey}/executions` | 실행 이력 조회 | 대상 플랜 실행 이력 존재 | 1. executions 호출 | 실행 목록과 version, resultStatus, staticAnalysisResults가 반환된다. | FR-13, FR-18, FR-24 |
| API-PLAN-004 | `GET /api/v1/build-plans/{planKey}/active-definition` | 없는 플랜 처리 | 대상 플랜 없음 | 1. 존재하지 않는 plan key로 호출 | 404가 반환된다. | FR-18 |
| API-EXEC-001 | `POST /api/v1/build-plans/{planKey}/executions/start` | 실행 시작 적재 | 대상 플랜 존재 | 1. `branchKind`, `commitHash`, `buildNumber`, `buildKey` payload 제출 | `buildVersionId`, `buildExecutionId`, `version`, `reusedExistingVersion`가 반환된다. | FR-13, FR-14, FR-15 |
| API-EXEC-002 | `POST /api/v1/build-plans/{planKey}/executions/start` | 동일 커밋 재빌드 처리 확인 | 같은 plan과 commitHash로 이전 실행이 존재 | 1. 같은 `commitHash`와 다른 `branchKind`로 start 호출 | 기존 버전을 재사용하고 `reusedExistingVersion=true`가 반환된다. | FR-15 |
| API-EXEC-003 | `POST /api/v1/build-executions/{executionId}/finish` | 실행 종료 적재 | start로 생성된 execution 존재 | 1. `success`, `resultStatus`, `stageName`, `jobName`, `taskName`, `staticAnalysisResults` 제출 | 종료 결과가 저장되고 최신 성공/실패 상태가 갱신된다. | FR-13, FR-15 |
| API-EXEC-004 | `POST /api/v1/build-executions/{executionId}/static-analysis-results` | 정적분석 결과 upsert | start로 생성된 execution 존재 | 1. `staticAnalysisResults` 제출 2. 동일 toolName으로 재제출 | toolName 기준으로 결과가 갱신된다. | FR-13 |
| API-SET-001 | `GET /api/v1/system-settings/coverity` | 운영 설정 조회 | 설정값 존재 | 1. coverity settings 호출 | Coverity와 Bamboo 운영 설정이 함께 반환된다. | FR-17, FR-26 |
| API-SET-002 | `PUT /api/v1/system-settings/coverity` | 운영 설정 수정 | 설정 수정 권한 있음 | 1. `connectUrl`, `onNewCert`, `commitEnabled`, `gitCloneUrlTemplate`, `repositoryLinkageMode`, `bambooServerUrl` 제출 | 저장된 운영 설정이 반환되고 repository linkage mode는 `linked` 또는 `create_if_missing`로 정규화된다. | FR-17, FR-26 |
| API-SET-003 | `POST /api/v1/system-settings/specs-drafts/initialize` | Specs draft 전체 초기화 | 프로젝트/플랜 데이터 존재 | 1. `resetExisting=true` 또는 기본값으로 호출 | 초기화 요약이 반환된다. | FR-16, FR-21 |
| API-SET-004 | `POST /api/v1/system-settings/specs-drafts/initialize/{planKey}` | 플랜 단위 Specs draft 초기화 | 대상 플랜 존재 | 1. planKey로 호출 | 해당 플랜의 draft 초기화 요약이 반환된다. | FR-16, FR-21 |
| API-ERR-001 | 공통 | 잘못된 payload 검증 확인 | 잘못된 JSON payload 준비 | 1. 필수 필드 누락 또는 타입 오류 payload 제출 | 400이 반환되고 검증 오류가 메시지로 전달된다. | FR-26 |
| API-ERR-002 | 공통 | 없는 리소스 처리 확인 | 대상 프로젝트/플랜 없음 | 1. 잘못된 project key 또는 plan key로 호출 | 404가 반환된다. | FR-18 |

## 우선 실행 순서

1. API-AUTH-001, API-PROJ-001, API-PROJ-002, API-PROJ-003
2. API-PLAN-001, API-PLAN-002, API-EXEC-001, API-EXEC-003
3. API-SET-001, API-SET-002, API-SET-003, API-SET-004
4. API-EXEC-002, API-EXEC-004, API-ERR-001, API-ERR-002

## 현재 구현 기준 메모

- 실행 시작은 `buildKey`를 생략해도 동작하지만, BuildInfo가 여러 개인 플랜에서는 명시하는 편이 안전하다.
- `repositoryLinkageMode`는 `linked`와 `create_if_missing` 둘 다 허용하되, 그 외 값은 `linked`로 정규화된다.
- prepare-context와 active-definition은 생성기 CLI와 UI가 동시에 사용하는 핵심 경로이므로 회귀 검증 우선순위가 높다.
- 배포/릴리스/사용자 권한 API는 아직 없으므로 이 문서의 범위에서 제외한다.
