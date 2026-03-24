# E2E 테스트 케이스 세트

## 문서 메타데이터

- 문서 일자: 2026-03-24
- 문서 유형: E2E Test Case Set
- 대상 범위: 생성기 CLI, 운영 API, 운영 UI, 메타데이터 적재/조회 흐름
- 관련 요구사항: [../requirements/CRS.md](../requirements/CRS.md), [../requirements/SRS.md](../requirements/SRS.md)
- 관련 설계: [../designs/SAD.md](../designs/SAD.md), [../designs/Design.md](../designs/Design.md)

## 요약

이 문서는 현재 작성된 요구사항/설계 문서를 기준으로, 저장소 내부에서 실제로 이어지는 end-to-end 시나리오를 정리한다. 실제 Bamboo 서버 반영까지 포함하는 시나리오는 아직 완전 자동화되지 않았으므로, 현재 구현 기준에서는 로컬 생성기, Django/Ninja 백엔드, 조회 UI, 데이터 적재/조회 경로를 한 흐름으로 검증하는 것을 우선한다.

## 범위

### 포함

- JSON 입력 -> 생성기 CLI -> Bamboo Specs 산출물 생성
- 운영 API 기반 활성 정의 조회 -> 생성기 CLI 재사용
- 프로젝트 등록 -> Specs 준비도 계산 -> 프로젝트 상세 조회
- 운영 설정 변경 -> prepare context/active definition 반영
- 실행 시작 -> 종료 -> 실행 이력/최신 버전 갱신
- Specs draft 초기화 -> preview/export draft 생성 -> publish 이력 저장
- UI 등록/수정 화면에서 저장된 메타데이터와 API 결과 일치 여부 확인

### 제외

- 실제 Bamboo 서버 배포/반영 성공 여부
- 사용자/권한 세분화 정책
- 외부 CI/CD 도구 연동

## 추적 기준

- CRS: JSON 생성, 저장소 연결, 준비 컨텍스트, 운영 API 우선, 프로젝트 등록/조회, 빌드 현황, Bamboo 운영 현황
- SRS: FR-06, FR-07, FR-12, FR-13, FR-16, FR-17, FR-18, FR-19, FR-21, FR-22, FR-24, FR-26
- Design: 입력 JSON 설계, 저장소 연결 및 브랜치 트리거, 준비 스테이지 변수 조회, 빌드 메타데이터 DB 설계, 운영 흐름
- SAD: 생성기 파이프라인, 운영 백엔드, API 계층, 조회 UI 계층

## 테스트 데이터 준비 가이드

- `build_info_json/2026/` 아래 샘플 정의를 준비한다.
- 운영 백엔드는 테스트용 SQLite 설정을 사용한다.
- API 경로는 인증 토큰 기반 요청 헤더를 포함한다.
- Bamboo publish 관련 케이스는 외부 Bamboo 대신 mock 또는 local fixture 기준으로 수행한다.

## 테스트 케이스

| TC ID | 흐름 | 목적 | 사전조건 | 절차 | 기대 결과 | 추적 |
| --- | --- | --- | --- | --- | --- | --- |
| E2E-CLI-001 | JSON -> CLI -> 출력물 | 입력 JSON으로 생성기 전체 흐름 확인 | `build_info_json/2026/*.json` 존재 | 1. `PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli` 실행 2. 출력 폴더 확인 | `bamboo-specs/` 아래 Java Specs, Coverity 설정, script bundle, manifest, compare report가 생성된다. | CRS, FR-06, FR-08, FR-09, FR-10 |
| E2E-API-001 | API -> CLI -> 출력물 | 운영 API 기반 활성 정의 조회 흐름 확인 | 백엔드 실행, `BAMBOO_API_*` 설정 | 1. `--api-plan-key SAMPAPI`로 CLI 실행 2. output 비교 | API에서 가져온 정의를 재사용해 동일한 생성 산출물이 나온다. | FR-16, FR-18 |
| E2E-OPS-001 | UI -> API -> DB | 프로젝트 등록과 준비도 계산 확인 | 백엔드 실행 | 1. 메인 화면에서 프로젝트 등록 2. 상세 화면 진입 3. API `GET /api/v1/projects/SAMPLE` 호출 | UI와 API가 동일한 프로젝트/저장소/빌드/준비도 결과를 반환한다. | FR-21, FR-22 |
| E2E-OPS-002 | 설정 -> selector -> API | 운영 설정 변경 반영 확인 | 백엔드 실행, system settings 접근 가능 | 1. Coverity/Bamboo 설정 변경 2. `prepare-context` 조회 3. `active-definition` 조회 | `repository.linkageMode`와 `BITBUCKET_CLONE_URL` 계열 값이 설정에 따라 반영된다. | FR-12, FR-16, FR-18 |
| E2E-EXEC-001 | 실행 시작 -> 종료 -> 조회 | 버전/실행 이력 갱신 확인 | 대상 plan 존재 | 1. `POST /executions/start` 2. `POST /build-executions/{id}/finish` 3. `GET /executions` | 동일 커밋 재빌드 규칙이 적용되고 실행 이력이 목록에 남는다. | FR-13, FR-14, FR-15, FR-18 |
| E2E-DRAFT-001 | Specs draft -> publish | draft 생성과 publish 이력 확인 | 대상 plan 존재, Bamboo publish mock 가능 | 1. `POST /specs-drafts/initialize` 2. `publish_bamboo_specs` 호출 | preview/export draft snapshot과 publish execution 이력이 생성된다. | FR-11, FR-17, FR-18 |
| E2E-UI-001 | 목록 -> 상세 -> 수정 | UI와 API 상태 동기화 확인 | 프로젝트/저장소/빌드 데이터 존재 | 1. 프로젝트 목록 조회 2. 프로젝트 상세 조회 3. 프로젝트 수정 후 재조회 | 화면상 메타데이터와 selector/API 결과가 일치한다. | FR-19, FR-21, FR-22 |
| E2E-RUN-001 | 실행 -> 정적분석 결과 | 정적분석 결과 적재 확인 | 실행 중인 buildExecution 존재 | 1. `POST /build-executions/{id}/static-analysis-results` 2. 실행 목록 재조회 | 정적분석 결과가 실행 목록과 backend DB에 반영된다. | FR-13, FR-18 |

## 우선 실행 순서

1. `E2E-CLI-001`
2. `E2E-API-001`
3. `E2E-OPS-001`
4. `E2E-EXEC-001`
5. `E2E-DRAFT-001`
6. `E2E-UI-001`
7. `E2E-RUN-001`

## 현재 구현 기준 메모

- 실제 Bamboo 서버 반영은 아직 별도 검증 단계가 필요하다.
- `E2E-DRAFT-001`과 `E2E-RUN-001`은 외부 시스템 대신 테스트 더블 또는 로컬 백엔드 상태 기준으로 수행한다.
- 프로젝트 등록 화면의 선택형 입력은 아직 완전한 enum 정책이 아니라 자유 입력과 suggestion 조합으로 동작한다.
