# SAD: bamboo_spec_generator 소프트웨어 아키텍처

## 문서 메타데이터

- 문서 일자: 2026-03-25
- 문서 유형: SAD
- 상태: 초안
- 관련 CRS: [../requirements/CRS.md](../requirements/CRS.md)
- 관련 SRS: [../requirements/SRS.md](../requirements/SRS.md)

## 요약

`bamboo_spec_generator`의 핵심 아키텍처는 입력 어댑터, 검증/모델 변환, 스크립트 자산 렌더링, Bamboo Specs 생성, 산출물 기록, 빌드 메타데이터 저장, 운영 백엔드/API/조회 UI로 분리된다. 장기적으로는 JSON과 DB가 동일 내부 모델로 수렴하고, 생성 파이프라인은 입력 소스와 무관하게 공통 생성 로직을 유지해야 하며, 운영 콘솔은 Bamboo와 Jenkins를 함께 다루는 다중 CI 도구 구조로 확장되어야 한다.

## 현재 구현 기준

- 현재 실제 구현된 입력 어댑터는 JSON loader와 운영 API 기반 활성 정의 조회 경로다.
- 현재 실제 구현된 생성 파이프라인은 `parser -> validator -> script asset/render -> generator -> writer` 흐름이다.
- 운영 API에서 활성 정의와 prepare context를 읽는 생성기 클라이언트와 CLI 진입점이 구현되었다.
- Django 운영 백엔드에는 ORM 모델, migration, Admin, Ninja API, 프로젝트 등록/수정, BuildInfo 관리, 운영 설정 관리, 조회용 UI가 구현되었다.
- 버전 계산, 실행 시작/종료 저장, 정적분석 결과 upsert, 준비 컨텍스트 selector, preview/export draft 생성, Specs draft 초기화, Bamboo publish/run/status/detail 서비스가 백엔드 내부에 부분 구현되었다.
- 로컬 개발 기본 DB는 SQLite이며, 운영 전환용 PostgreSQL 설정 스위치와 초기화 명령이 구현되었다.
- Jenkins 등록/운영 현황/모드 전환 구조는 아직 요구사항 단계이며 구현되지 않았다.

## 배경

- 현재 시스템은 JSON 중심 생성기에서 출발했다.
- 제품 범위가 저장소 연결, 작업 하위 경로, MSBuild 보정, 스크립트 자산, DB 메타데이터 관리까지 확장되었다.
- 기능별 책임 분리가 없으면 입력 소스 변경이나 운영 메타데이터 도입 때 코드 결합도가 급격히 높아진다.
- 다중 CI 도구를 지원하려면 Bamboo 전용 표현을 공통 모델과 도구별 어댑터로 분리해야 한다.

## 목표

- 고수준 컴포넌트와 책임 경계를 명확히 한다.
- JSON 우선 구조에서 DB 우선 구조로의 전환 경로를 정의한다.
- 생성 파이프라인과 운영 메타데이터 관리 파이프라인을 분리한다.
- Bamboo와 Jenkins를 수용할 수 있는 공통 운영 콘솔 경계를 정의한다.

## 비목표

- 클래스 수준 구현 세부사항 확정

## 아키텍처 개요

```text
Input Sources
  |- JSON Files
  |- DB Active Definitions
        |
        v
Input Adapters
  |- JsonLoader
  |- DbLoader
        |
        v
Validation / Normalization
        |
        v
Unified Domain Model
  |- CI Provider Metadata
        |
        +--> Script Asset Resolution / Rendering
        |
        +--> Repository Linking / Trigger Mapping
        |
        +--> Build Path / MSBuild Enrichment
        |
        v
CI Provider Integrations
  |- Bamboo Specs Generator
  |- Jenkins Registration Adapter
        |
        v
Artifact Writer / Summary Reporter

Operations Backend
  |- Django Admin / Internal Views
  |- Ninja API
  |- CI Console Web Frontend

Build Result Sources
  |- Bamboo API / Sync Job / Manual Feed
  |- Jenkins API / Sync Job / Manual Feed
        |
        v
Build Metadata Services
  |- Version Resolver
  |- Execution Recorder
  |- Static Analysis Recorder
  |- Definition History Recorder

Deployment Sources
  |- Bamboo Deployment Events
  |- Release Approval Workflow
        |
        v
Deployment Metadata Services
  |- Release Registry
  |- Environment State Tracker
  |- Deployment Recorder
  |- Rollback Tracker
```

위 다이어그램에서 `Jenkins Registration Adapter`, Jenkins 연동 계층, 배포 메타데이터 영역은 목표 아키텍처다. 현재 구현 범위는 `JSON Files`, 운영 API 기반 입력, `Bamboo Specs Generator`, `Artifact Writer / Summary Reporter`, `Build Metadata Services`, `Operations Backend`의 프로젝트/정의/실행/운영 설정/Bamboo 연동 일부까지 포함한다.

## 주요 컴포넌트

### 1. 입력 어댑터 계층

- JSON 파일 또는 DB 정의를 읽는다.
- 입력 형식 차이를 흡수하고 공통 내부 모델 후보를 만든다.
- 현재 구현은 JSON 파일 직접 로드와 운영 API를 통한 활성 정의 조회를 지원한다.

### 2. 검증 및 정규화 계층

- 필수 필드, 브랜치 정책, 작업 하위 경로, 연결 모드, 버전 규칙 전제 조건을 검증한다.
- 연도, 저장소 식별자, 자산 렌더링 컨텍스트를 정규화한다.

### 3. 공통 도메인 모델 계층

- 생성기와 메타데이터 저장 로직이 공유하는 표준 모델을 유지한다.
- 입력 소스가 JSON인지 DB인지 숨긴다.
- `ci_provider` 같은 식별자를 통해 Bamboo/Jenkins 공통 필드와 도구별 전용 필드를 함께 표현할 수 있어야 한다.

### 4. 자산 및 환경 해석 계층

- 스크립트 자산 선택, 프래그먼트/오버레이 조합, 하위 경로 반영, MSBuild 보정 값을 계산한다.

### 5. CI 도구 통합 계층

- Bamboo 경로에서는 공통 워크플로우를 기준으로 Java Specs를 생성한다.
- Jenkins 경로에서는 프로젝트/잡 등록 메타데이터를 운영 모델과 API에 맞게 구성한다.
- 저장소 연결, 트리거, requirement, 스크립트 inline body 또는 보조 자산 출력은 현재 Bamboo 경로에서 담당한다.

### 6. 산출물 기록 계층

- Java 소스, 스크립트 번들, 요약 문서, 매니페스트를 파일 시스템에 기록한다.

### 7. 빌드 메타데이터 계층

- 빌드 플랜 정의, 버전, 실행 이력, 정적분석 결과, 최신 버전 포인터를 관리한다.
- 동일 커밋 재빌드 시 버전 재사용과 실행 이력 누적을 담당한다.
- 현재 ORM 모델과 서비스 초안이 구현되었지만 외부 빌드 시스템과의 실제 적재 연동은 미구현이다.

### 8. 배포 메타데이터 계층

- 빌드 버전과 배포 대상을 연결하는 릴리스/환경 메타데이터를 관리한다.
- 환경별 현재 배포 버전, 직전 안정 버전, 승인 상태, 롤백 이력을 저장한다.
- 현재 미구현이며 목표 아키텍처 범위다.

### 9. 운영 백엔드 계층

- PostgreSQL을 영속 저장소로 사용하는 Django 기반 운영 백엔드다.
- ORM, 마이그레이션, Admin, 내부 조회 화면의 기반이 된다.
- 현재 부분 구현이다.

### 10. API 계층

- Ninja 기반 HTTP API를 제공한다.
- 준비 스테이지 변수 조회, 프로젝트/플랜/버전/실행 이력 조회, 결과 적재를 담당한다.
- 운영 설정 조회/수정과 Specs draft 초기화도 담당한다.
- 장기적으로 배포 환경 상태 조회, 릴리스 승인/배포 결과 적재를 포함한다.
- 장기적으로 CI 도구 모드 전환, 공통 프로젝트 조회, Bamboo plan과 Jenkins job의 공통 표현도 포함한다.
- 생성기는 보안상 이 API를 통해서만 운영 데이터를 조회한다.
- 현재 활성 정의 조회, 준비 컨텍스트 조회, 실행 시작/종료 적재, 프로젝트 조회의 기본 경로가 구현되었다.

### 11. 조회용 프론트엔드 계층

- 운영 사용자가 프로젝트, 플랜/잡, 버전, 실행 결과를 탐색한다.
- 장기적으로 운영 사용자는 빌드 상태와 이어진 배포 상태, 릴리스 후보, 승인 대기 항목을 같은 콘솔에서 탐색한다.
- 초기 범위는 Django 템플릿 또는 Django 내부 뷰 기반 조회 화면을 우선한다.
- 장기적으로 상단 모드 전환으로 Bamboo 관리와 Jenkins 관리를 오가는 공통 CI 콘솔을 제공한다.
- 현재 프로젝트 목록/상세, 저장소 상세, 빌드 상세, BuildInfo 목록/상세, Coverity/Bamboo 설정, Bamboo plan 상태/상세, publish 이력 화면이 구현되었고 Jenkins 콘솔 범위는 미구현이다.

## 아키텍처 원칙

- 입력 소스와 생성 로직은 분리한다.
- 공통 내부 모델은 하나만 유지한다.
- 도구별 통합은 공통 모델과 도구별 어댑터로 분리한다.
- 스크립트 자산은 코드와 분리된 파일 시스템 자산으로 관리한다.
- 버전 대표 상태와 실행 이력은 분리 저장한다.
- 최신 포인터 갱신은 트랜잭션 경계 안에서 처리하는 방향을 우선한다.
- 운영 백엔드와 생성기는 독립 책임으로 유지한다.
- API는 Django Ninja를 기본 인터페이스로 사용한다.

## 권장 저장소 구조

```text
docs/
  requirements/
    CRS.md
    SRS.md
  designs/
    SAD.md
    Design.md
build_info_json/
scripts/
src/bamboo_spec_generator/
backend/
  manage.py
  config/
  apps/
    buildmeta/
    api/
    ui/
tests/
```

## 주요 데이터 흐름

### 생성 흐름

1. JSON 또는 DB에서 정의 조회
2. 검증 및 정규화
3. 스크립트 자산/저장소/경로/MSBuild 규칙 해석
4. Bamboo Specs 또는 후속 CI 도구용 등록 메타데이터 생성
5. 결과 기록

### 메타데이터 흐름

1. 빌드 시작 이벤트 수신
2. `build_plan + commit_hash` 기준 기존 버전 조회
3. 기존 버전이 있으면 재사용, 없으면 버전 규칙에 따라 신규 생성
4. 실행 종료 후 결과/정적분석/실패 위치 저장
5. 최신 버전 포인터 갱신

### 운영 조회 흐름

1. 운영 사용자가 웹 UI 또는 API 호출
2. Django 백엔드가 PostgreSQL에서 프로젝트/플랜 또는 잡/버전/실행 이력 조회
3. Ninja API 또는 서버 렌더링 뷰로 응답 반환

### 배포 운영 흐름

1. 운영 사용자가 특정 빌드 버전을 릴리스 후보로 선택
2. 시스템이 배포 대상 환경과 승인 상태를 조회
3. 배포 실행 또는 외부 배포 이벤트 수신 시 결과를 저장
4. 환경별 현재 버전, 실패 이력, 롤백 가능 상태를 UI/API에서 조회

### 생성기 API 조회 흐름

1. 생성기가 인증 정보와 대상 식별자(`plan_key`, `build_id`)를 포함해 Ninja API 호출
2. Django 백엔드가 인증/권한 검증
3. API 계층이 활성 빌드 정의 또는 준비 스테이지 변수 컨텍스트 조회
4. 응답을 생성기 내부 공통 모델로 변환
5. 이후 생성 파이프라인은 기존 `validator -> generator -> writer` 흐름 유지

## 전환 전략

### 1단계

- JSON 입력이 기준
- DB는 적재 대상

### 2단계

- JSON과 DB 병행 검증

### 3단계

- DB 우선, JSON fallback

### 4단계

- DB 단일 기준 소스

## 핵심 아키텍처 결정

- 단일 Specs 저장소 모델 유지
- 공통 워크플로우 유지
- 입력 어댑터와 공통 내부 모델 분리
- 스크립트 자산 파일 기반 관리
- 빌드 버전과 실행 이력 분리 저장
- 운영 백엔드는 Django 기반으로 분리
- API는 Ninja 기반으로 구현
- 초기 UI는 조회 전용으로 시작
- 생성기는 운영 데이터 접근 시 Ninja API만 사용

## 리스크

- 입력 모델 확장과 DB 모델 확장이 동시에 진행되면 검증 경계가 흔들릴 수 있다.
- 태스크 단위 실패 위치는 외부 시스템에서 항상 제공되지 않을 수 있다.
- 버전 시작값 정책이 미확정이면 초기 데이터 적재 시 규칙 충돌이 생길 수 있다.
- 생성기가 API를 우회해 DB를 직접 조회하면 보안 경계와 책임 경계가 무너질 수 있다.

## 다음 단계

- [Design](./Design.md)에서 JSON 스키마, 저장소 연결, 스크립트 자산, DB 상세 모델을 구체화한다.
