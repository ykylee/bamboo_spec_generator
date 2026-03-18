# bamboo_spec_generator 이슈 분해

## 개요

현재 통합 요구사항을 Jira 등록 가능한 단위로 분해한 초안이다. 현재는 생성기 본체 범위의 Epic 1건과 빌드 메타데이터 DB 확장 범위의 Epic 1건으로 나뉜다.

## 전체 구현 상태

- 현재 코드로 부분 구현된 범위:
  - EPIC-01
- 현재 코드로 부분 구현된 범위:
  - EPIC-02

## 전체 추천 구현 순서

1. STORY-08 저장소 연결 미등록 저장소 대응 보강
2. STORY-09 브랜치별 연결 및 트리거 구성 생성
3. STORY-04 산출물 구조와 저장소 연결 보조 메타데이터 정합성 보강
4. STORY-13 빌드 정의 DB 스키마 및 저장 모델 정의
5. STORY-19 Django 운영 백엔드 및 Admin 기반 관리 구조 도입
6. STORY-17 생성기의 DB 조회 전환 전략 수립
7. STORY-18 준비 스테이지 DB 변수 조회 및 프로젝트 메타데이터 모델 구현
8. STORY-20 Ninja API 및 조회용 프론트엔드 도입
9. STORY-14 JSON 적재 및 동기화 경로 구현
10. STORY-15 빌드 실행 결과 저장 모델 구현
11. STORY-16 버전 및 변경 이력 추적 구현

## EPIC-01 생성기 본체

### 개요

현재 통합 CRS를 Jira 등록 가능한 단위로 분해한 초안이다. 상위 에픽 1건과 하위 스토리 11건으로 구성한다.

### 구현 상태

- 현재 구현 완료에 가까운 범위:
  - STORY-01
  - STORY-02
  - STORY-03
  - STORY-04
  - STORY-06
  - STORY-07
  - STORY-10
  - STORY-11
  - STORY-12
- 현재 문서화 또는 부분 반영 수준:
  - STORY-08
- 현재 미구현:
  - STORY-09

### 우선순위

- `유지`: STORY-01, STORY-02, STORY-03, STORY-06, STORY-07, STORY-10, STORY-11, STORY-12
- `보강 필요`: STORY-04, STORY-08
- `신규 구현 필요`: STORY-09

### 추천 구현 순서

1. STORY-08 저장소 연결 미등록 저장소 대응 보강
2. STORY-09 브랜치별 연결 및 트리거 구성 생성
3. STORY-04 산출물 구조와 저장소 연결 보조 메타데이터 정합성 보강

### 이슈 목록

- [EPIC-01 Bamboo Specs 기반 플랜 생성기 구축](./EPIC-01-bamboo-spec-generator.md)
- [STORY-01 타겟 빌드 JSON 스키마 및 연도별 관리 구조 정의](./STORY-01-json-schema-and-yearly-structure.md)
- [STORY-02 다중 JSON 입력 로딩 및 빌드 정의 식별 기능 구현](./STORY-02-multi-json-loading.md)
- [STORY-03 Bamboo Specs Java 코드 생성 기능 구현](./STORY-03-bamboo-specs-code-generation.md)
- [STORY-04 빌드별 산출물 분리 및 등록 단위 구조 설계](./STORY-04-output-structure.md)
- [STORY-05 Atlassian Base 코드 확보 및 저장소 관리 체계 정의](./STORY-05-base-code-management.md)
- [STORY-06 공통 워크플로우 템플릿 및 빌드 상세 입력 구조 정의](./STORY-06-workflow-template-and-build-details.md)
- [STORY-07 저장소 연결용 JSON 필드 및 검증 규칙 정의](./STORY-07-repository-json-fields.md)
- [STORY-08 Bitbucket 저장소 연결 및 미등록 저장소 대응 설계](./STORY-08-bitbucket-linking-and-fallback.md)
- [STORY-09 브랜치별 연결 및 트리거 구성 생성](./STORY-09-branch-trigger-mapping.md)
- [STORY-10 MSBuild 플랜용 Directory.Build.targets 사전 생성 지원](./STORY-10-msbuild-directory-build-targets-override.md)
- [STORY-11 빌드 작업 하위 경로 지정 지원](./STORY-11-build-working-subpath-support.md)
- [STORY-12 플랜 스크립트 자산 분리 및 환경별 커스터마이징 관리](./STORY-12-plan-script-asset-management.md)

## EPIC-02 빌드 메타데이터 DB 확장

### 개요

빌드 정의를 JSON 파일 중심으로 관리하던 구조를 DB 중심 구조로 전환하고, 운영 백엔드/API/조회 UI까지 포함하기 위한 Jira 초안이다. 상위 에픽 1건과 하위 스토리 8건으로 구성한다.

### 구현 상태

- 현재 부분 구현:
  - STORY-13
  - STORY-17
  - STORY-19
  - STORY-20
- 현재 요구사항/설계 단계:
  - STORY-14
  - STORY-15
  - STORY-16
  - STORY-18

### 우선순위

- `높음`: STORY-18, STORY-14, STORY-15
- `유지/보강`: STORY-13, STORY-17, STORY-19, STORY-20
- `중간`: STORY-20
- `중간`: STORY-15, STORY-16

### 추천 구현 순서

1. STORY-18 준비 스테이지 DB 변수 조회 및 프로젝트 메타데이터 연동 완성
2. STORY-14 JSON 적재 및 동기화 경로 구현
3. STORY-15 빌드 실행 결과 저장 모델을 실제 연동까지 확장
4. STORY-16 버전 및 변경 이력 추적을 실제 운영 흐름에 맞게 보강
5. STORY-17 생성기 API 입력 경로를 정식 입력 모드로 확장
6. STORY-20 조회 UI와 API 응답 범위 보강

### 이슈 목록

- [EPIC-02 빌드 메타데이터 및 실행 이력의 DB 관리 전환](./EPIC-02-build-metadata-db-management.md)
- [STORY-13 빌드 정의 DB 스키마 및 저장 모델 정의](./STORY-13-build-metadata-schema-and-storage.md)
- [STORY-14 기존 JSON 빌드 정의의 DB 적재 및 동기화 경로 마련](./STORY-14-json-to-db-ingestion-and-sync.md)
- [STORY-15 빌드 실행 결과 저장 및 조회 모델 정의](./STORY-15-build-result-persistence.md)
- [STORY-16 빌드 버전 정보 및 변경 이력 추적 체계 정의](./STORY-16-version-and-history-tracking.md)
- [STORY-17 생성기의 DB 조회 전환 및 마이그레이션 전략 수립](./STORY-17-generator-db-integration-and-migration.md)
- [STORY-18 준비 스테이지 DB 변수 조회 및 프로젝트 메타데이터 확장](./STORY-18-prepare-stage-db-context-and-project-metadata.md)
- [STORY-19 Django 운영 백엔드 및 Admin 기반 관리 구조 도입](./STORY-19-django-backend-and-admin.md)
- [STORY-20 Ninja API 및 조회용 프론트엔드 도입](./STORY-20-ninja-api-and-readonly-frontend.md)
