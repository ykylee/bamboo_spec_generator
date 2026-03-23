# Detailed Design: 빌드 플랜 메타데이터 및 빌드 정보 관리

## 문서 메타데이터

- 문서 일자: 2026-03-23
- 문서 유형: Detailed Design
- 관련 요구사항: [../../requirements/issues/STORY-21-project-registration.md](../../requirements/issues/STORY-21-project-registration.md)
- 관련 요구사항: [../../requirements/issues/STORY-22-project-read-update.md](../../requirements/issues/STORY-22-project-read-update.md)
- 관련 요구사항: [../../requirements/issues/STORY-27-build-registration-structure-and-supported-options.md](../../requirements/issues/STORY-27-build-registration-structure-and-supported-options.md)
- 관련 요구사항: [../../requirements/issues/STORY-28-build-plan-dashboard-and-build-info-management.md](../../requirements/issues/STORY-28-build-plan-dashboard-and-build-info-management.md)

## 요약

이 문서는 운영 콘솔에서 `BuildPlan` 공통 메타데이터와 플랜 하위의 다건 `BuildPlanBuildInfo`를 관리하는 구조를 정리한다. 또한 실행 이력이 앞으로 `buildKey`를 통해 어느 빌드 환경구성에서 발생했는지 구분될 수 있도록 데이터 모델과 API 확장 방향을 설명한다. 추가로, 빌드 플랜 상세에서 등록된 메타데이터를 바탕으로 실제 Bamboo Plan/Job 구성을 미리 보여주고 수정하는 방향을 설계한다.

## 배경

- 기존 `BuildPlan`은 `buildId`, `planKey`, `latestVersion` 정도만 보유하고 있었다.
- 운영 요구상 플랜 공통 메타데이터와 개별 빌드 환경구성은 분리되어야 한다.
- 하나의 Bamboo 플랜에서 여러 빌드가 수행될 수 있으므로, 정적 분석 결과와 실행 결과를 빌드키 단위로 분리해 추적할 수 있어야 한다.
- 요구사항 정리 결과 `BuildPlan` 1개는 Bamboo `Plan` 1개에 대응한다.
- 같은 플랜에 연결된 `BuildPlanBuildInfo` 1개는 운영상 하나의 빌드 단위를 뜻하며, 실제 Bamboo에서는 최소 `Build Job` 1개와 `Analysis Job` 1개로 분리되어야 한다.

## 목표

- `BuildPlan`에 플랜 공통 메타데이터를 저장한다.
- `BuildPlanBuildInfo`로 플랜 하위 다건 빌드 환경구성을 저장한다.
- UI에서 플랜 공통 메타데이터와 빌드 정보를 분리해 관리한다.
- 빌드 플랜 상세에서 실제 생성될 Bamboo Plan/Stage/Job/Task 구성을 미리 보여준다.
- 빌드 정보와 플랜 메타데이터 수정이 Bamboo 구성 미리보기에 직접 반영되게 한다.
- Build 실패와 Analysis 실패를 운영상 분리해서 볼 수 있게 한다.
- 실행 시작 API가 `buildKey`를 받아 빌드 정보와 실행을 연결할 수 있게 한다.
- 메인 대시보드와 상세 페이지가 동일한 운영 콘솔 시각 언어를 유지한다.

## 비목표

- Bamboo 작업 정의의 최종 publish 자동화
- 빌드 정보 삭제 정책
- 빌드 정보별 정적 분석 리포트의 최종 집계 화면

## 데이터 모델 설계

### `BuildPlan`

- 역할: 빌드 플랜의 공통 메타데이터 보관
- 주요 필드:
  - `build_id`
  - `plan_key`
  - `static_analysis_tool_version`
  - `coverity_project`
  - `latest_version`

### `BuildPlanBuildInfo`

- 역할: 플랜 내부 개별 빌드 단위의 환경구성 관리
- 주요 필드:
  - `build_plan`
  - `build_key`
  - `operating_system`
  - `pre_process`
  - `build_command`
  - `clean_command`
  - `language`
  - `compiler`
  - `analysis_excluded_files`
  - `coverity_stream`
  - `build_sub_path`
- 제약:
  - 동일 플랜 내 `build_key` 유일

### 산출물 모델 관점

- `Build Job` 산출물:
  - 배포 가능한 binary package
- `Analysis Job` 산출물:
  - 각 분석 도구 결과를 정리한 report
- 두 산출물은 목적과 실패 원인이 다르므로 분리 취급한다.

### `BuildExecution`

- 기존 역할: 플랜 실행 기록
- 변경점:
  - `build_info` FK 추가
- 의미:
  - 하나의 플랜에서 같은 `build_number`라도 서로 다른 `build_info`에 속한 실행일 수 있다.
- 제약:
  - 유일성은 `(build_plan, build_info, build_number)` 기준

## 서비스 설계

### `apps.buildmeta.services.build_plans.update_build_plan_metadata(...)`

- 책임: 플랜 공통 메타데이터 수정
- 입력:
  - `plan_key`
  - `static_analysis_tool_version`
  - `coverity_project`

### `apps.buildmeta.services.build_info.upsert_build_info(...)`

- 책임: 플랜 하위 빌드 정보 등록/수정
- 입력:
  - `plan_key`
  - `build_key`
  - `operating_system`
  - `pre_process`
  - `build_command`
  - `clean_command`
  - `language`
  - `compiler`
  - `analysis_excluded_files`
  - `coverity_stream`
  - `build_sub_path`
- 동작:
  - `plan_key + build_key` 기준 upsert

### `apps.buildmeta.services.executions.start_execution(...)`

- 변경 입력:
  - 기존 `plan_key`, `branch_kind`, `commit_hash`, `build_number`
  - 추가 `build_key`
- 동작:
  1. `plan_key`로 플랜 조회
  2. `build_key`가 있으면 해당 플랜의 `BuildPlanBuildInfo` 조회
  3. 기존 실행 중복 여부를 `(build_plan, build_info, build_number)` 기준으로 확인
  4. 없으면 새 `BuildExecution` 생성

### `apps.buildmeta.selectors/preview` 또는 동등한 preview service

- 책임: 활성 정의, 플랜 메타데이터, 빌드 정보를 결합해 예상 Bamboo Plan 구성을 생성
- 입력:
  - `plan_key`
- 출력:
  - Plan 레벨 미리보기
  - Stage 목록
  - Job 목록
  - Job별 buildKey, 명령어, 언어, 컴파일러, Coverity 설정
  - Job별 task 목록
  - Job별 산출물 유형
  - 값의 출처 정보
    - 활성 정의
    - 플랜 메타데이터
    - 빌드 정보
- 동작:
  1. 활성 정의 조회
  2. 플랜 메타데이터 조회
  3. 빌드 정보 목록 조회
  4. `Prepare / Build / Analysis / Post Process` 구조와 Build/Analysis 분리 Job 구조 조합
  5. UI 표시용 preview payload 반환

## Selector 설계

### `list_build_plan_summaries()`

- 빌드 플랜 인덱스용 요약 반환
- 포함 필드:
  - 플랜 공통 메타데이터
  - 저장소 slug
  - 최신 버전/성공 여부
  - `buildInfoCount`
  - 상세 링크

### `get_project_detail()`

- 프로젝트 상세의 빌드 항목에 다음 필드 추가
  - `staticAnalysisToolVersion`
  - `coverityProject`
  - `buildInfoCount`

### `_list_build_info_entries(plan_key)`

- 특정 플랜의 빌드 정보 목록 반환

### `_list_execution_groups(plan_key)`

- 실행 이력을 `buildKey` 기준으로 묶어서 미리보기용 집계 생성
- 현재는 UI 미리보기 성격이며, 향후 정식 집계 로직으로 확장 가능

### `get_build_plan_preview(plan_key)`

- 빌드 상세의 Bamboo 구성 미리보기에 필요한 payload 반환
- 포함 필드 예시:
  - `plan`
    - `planKey`
    - `buildId`
    - `staticAnalysisToolVersion`
    - `coverityProject`
  - `repository`
  - `stages`
  - `jobs`
  - `jobs[].buildKey`
  - `jobs[].language`
  - `jobs[].compiler`
  - `jobs[].preProcess`
  - `jobs[].buildCommand`
  - `jobs[].cleanCommand`
  - `jobs[].coverityStream`
  - `jobs[].buildSubPath`
  - `jobs[].analysisExcludedFiles`
  - `jobs[].sourceSummary`
  - `jobs[].tasks`
  - `jobs[].artifactType`

## UI/페이지 흐름 설계

### 메인 대시보드

- 프로젝트 리스트 중심 운영 화면
- 상단 검색은 빈 입력일 때 결과 비노출
- 페이징은 리스트 패널만 부분 갱신
- 등록 패널/사이드 패널/상단 검색 모두 메인 대시보드 스타일과 통일

### 프로젝트 상세

- 프로젝트 메타데이터만 수정
- 저장소 추가/빌드 추가는 같은 페이지 안에서 별도 패널로 관리
- 빌드 목록에는 각 빌드의 `buildInfoCount` 노출

### 빌드 상세

- 플랜 공통 메타데이터 수정 화면
- `BuildPlan` 수준 정보와 등록된 빌드 정보 요약을 함께 노출
- 빌드 정보 등록 패널은 같은 페이지 안에서 접힘/펼침으로 관리
- Bamboo 구성 미리보기 패널을 제공
- 미리보기에서 Plan 1개와 Stage/Job/Task 구조를 시각적으로 확인 가능
- Stage 클릭 시 포함 Job 목록이 펼쳐지고, Job 클릭 시 해당 Task inspector가 표시되도록 설계
- 빌드 정보 수정은 개별 상세 또는 같은 페이지 인라인 액션으로 연결

### 빌드 정보 상세

- 목적: 특정 `buildKey`의 환경구성 수정
- 구성:
  - 빌드키 중심 상세 화면
  - 수정 폼
  - 현재 연결된 실행 집계 미리보기

## API 설계 메모

### 실행 시작 요청

- 엔드포인트: `/api/v1/build-plans/{plan_key}/executions/start`
- 추가 필드:
  - `buildKey`
- 기대 효과:
  - 플랜 내부 빌드 단위를 구분해 실행 기록 저장

### 실행 목록 조회

- `buildKey`를 포함해 반환
- 향후 빌드 정보 상세에서 실행 기록 drill-down에 재사용 가능

## Bamboo 구성 미리보기 설계

### 개념 매핑

- `BuildPlan` 1개 = Bamboo `Plan` 1개
- `BuildPlanBuildInfo` 1개 = Bamboo 상의 빌드 단위 1개
- 빌드 단위 1개 = `Build Job` 1개 + `Analysis Job` 1개
- `BuildPlanBuildInfo` N개 = `Build Job` N개 + `Analysis Job` N개
- Job의 OS는 `BuildPlanBuildInfo.operating_system`에서 관리하고 Bamboo requirement로 반영한다.

### 미리보기 생성 규칙

- Plan 공통 영역은 다음에서 가져온다.
  - `BuildPlan`
  - 활성 `BuildPlanDefinition`
- Job 개별 영역은 다음에서 가져온다.
  - `BuildPlanBuildInfo`
- 원본 정의에 단일 빌드 기준 값이 있더라도, Job 단위로 반복 가능한 항목은 `BuildPlanBuildInfo` 값으로 override 한다.
- `Analysis Job`은 `Build Job`의 workspace나 산출물을 이어받지 않는다.
- `Analysis Job`은 항상 별도 checkout부터 시작한다.

### UI 표시 규칙

- 히어로 아래 별도 패널에서 예상 Bamboo 구성을 노출한다.
- 최소 표시 항목:
  - Plan Key
  - Build ID
  - Repository 연결 정보
  - Stage 이름
  - Job 이름 또는 buildKey
  - Task 목록
  - Pre Process
  - Build Command
  - Clean Command
  - Language
  - Compiler
  - Coverity Stream
  - Build Sub Path
  - 산출물 유형
- 각 값이 어디서 왔는지 보조 정보로 표시할 수 있다.

### Stage 및 Job 구조 규칙

- `Prepare`
  - 새 빌드 시작 등록
  - 버전 갱신
  - 실행 메타데이터 기록
- `Build Job`
  - Build stage에 배치
  - checkout
  - pre process
  - clean
  - build
  - binary package 산출
- `Analysis Job`
  - Analysis stage에 배치
  - checkout
  - coverity 또는 기타 분석 도구 실행
  - report 산출
- `Post Process`
  - 플랜 공통 후속 작업 단계
  - trigger 및 기타 마감 작업 포함 가능

### 수정 전략

- 1차 구현:
  - 플랜 메타데이터 수정은 기존 패널 사용
  - Job 수준 수정은 `BuildPlanBuildInfo` 수정으로 반영
  - 미리보기는 저장된 값 기준 read-only 렌더링
- 2차 확장:
  - 활성 정의 원본과 별도 override를 둬서 미리보기에서 직접 수정
  - sync/import 이후에도 운영자 수정값이 유지되도록 정책 설계

## 테스트 설계

- 서버 테스트:
  - 플랜 메타데이터 수정
  - 빌드 정보 등록/수정
  - 빌드 정보 수만큼 Build/Analysis Job preview 생성
  - 활성 정의와 빌드 정보 조합 결과 preview payload 검증
  - 같은 `buildNumber`라도 `buildKey`가 다르면 별도 실행 생성
- 브라우저 E2E:
  - 빌드 상세에서 플랜 메타데이터 수정
  - 빌드 상세에서 빌드 정보 등록 패널 열기
  - 빌드 정보 등록 후 상세 페이지에서 preview/stage/job/task 구조 확인
  - 개별 빌드 정보 상세 진입 및 수정

## 영향 범위

- Django 모델 및 마이그레이션
- 실행 API 스키마/라우터
- 프로젝트/빌드 selector
- Bamboo preview selector/service
- UI 뷰, 폼, 템플릿, 스타일
- 테스트 코드

## 수용 기준

- 플랜 공통 메타데이터와 빌드 정보가 분리 저장된다.
- 한 플랜 아래 여러 빌드 정보를 등록할 수 있다.
- 한 플랜 아래 등록된 빌드 정보 수만큼 Build/Analysis Job 미리보기가 생성된다.
- 빌드 상세에서 예상 Bamboo Plan/Stage/Job/Task 구성을 확인할 수 있다.
- Analysis Job이 별도 checkout 흐름으로 표시된다.
- Build Job 산출물과 Analysis Job 산출물이 구분되어 표시된다.
- 실행 시작 시 `buildKey`를 전달할 수 있다.
- UI에서 빌드 정보 등록/수정 흐름이 동작한다.
- 빌드키 기준 실행 집계 미리보기가 가능하다.

## 오픈 이슈

- `buildKey` 없는 기존 실행을 어떤 기본 그룹으로 취급할지 결정 필요
- 빌드 정보 삭제 시 기존 실행의 FK 처리 정책 결정 필요
- 빌드 정보별 집계 결과를 플랜 수준 최종 품질지표로 어떻게 승격할지 결정 필요
- 활성 정의 원본과 운영자 수정값이 모두 있을 때 우선순위와 병합 정책 결정 필요
- Build Job과 Analysis Job을 항상 쌍으로 강제할지, 일부 빌드 정보는 analysis 생략을 허용할지 결정 필요
- report 포맷과 저장 위치를 어떤 표준으로 통일할지 결정 필요
