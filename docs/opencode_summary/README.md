# OpenCode 분석 요약: bamboo_spec_generator

## 문서 개요

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-03-28 |
| 작성자 | OpenCode AI Agent |
| 목적 | 코드베이스 목적, 요구사항, 설계, 구현 현황 종합 분석 |

---

## 1. 프로젝트 개요

### 1.1 프로젝트 이름 및 시작점

**프로젝트명**: `bamboo_spec_generator`

**시작점**: 연도별 JSON 빌드 정의를 읽어 Bamboo Specs Java 코드를 생성하는 로컬 실행형 생성기

### 1.2 현재 위치

현재 **Bamboo와 Jenkins를 함께 다루는 CI/CD 운영 시스템**으로 확장 중

- 현재 구현의 중심: **Bamboo Specs 생성** + **Bamboo 운영 백엔드**
- 제품 방향: **다중 CI 도구를 지원하는 공통 운영 콘솔**

### 1.3 저장소 구성 요소

| 구분 | 경로/파일 | 설명 |
|------|-----------|------|
| 생성기 코드 | `src/bamboo_spec_generator/` | Python 기반 Bamboo Specs 생성기 |
| 운영 백엔드 | `backend/` | Django/Ninja 기반 백엔드 |
| 입력 JSON | `build_info_json/<year>/` | 빌드 정의 입력 파일 |
| 스크립트 자산 | `scripts/plan_tasks/` | Task 스크립트 템플릿 |
| 문서 | `docs/` | 요구사항, 설계, 테스트 문서 |
| 테스트 | `tests/`, `backend/apps/*/tests.py` | 단위/통합/E2E 테스트 |

---

## 2. 제품 방향 (Roadmap)

### 2.1 단기 (현재)

- Bamboo Specs 생성
- Bamboo 운영 메타데이터 관리
- Django/Ninja 기반 운영 백엔드

### 2.2 중기

- 프로젝트 등록 기반 생성 흐름 강화
- 운영 API 표준화
- 빌드/배포 메타데이터 고도화

### 2.3 장기

- **Bamboo와 Jenkins를 함께 관리하는 공통 CI/CD 관제 시스템**

### 2.4 UI 방향

- 상단에서 `Bamboo 관리` ↔ `Jenkins 관리` 전환
- 전체 정보 구조는 공통으로 유지
- 테마: Bamboo = 밝은 파란색, Jenkins = 밝은 빨간색

---

## 3. 요구사항 문서 체계

### 3.1 핵심 문서

| 문서 | 경로 | 설명 |
|------|------|------|
| **CRS** | `docs/requirements/CRS.md` | 고객 요구사항 명세 |
| **SRS** | `docs/requirements/SRS.md` | 시스템 요구사항 명세 |
| **SAD** | `docs/designs/SAD.md` | 소프트웨어 아키텍처 설계 |
| **Design** | `docs/designs/Design.md` | 상세 설계 |
| **BREAKDOWN** | `docs/requirements/issues/BREAKDOWN.md` | Epic/Story 분해 |

### 3.2 요구사항分层

```
CRS (고객 요구사항)
    └── SRS (시스템 요구사항)
            └── Epic/Story (Jira 단위 분해)
                    └── Design (상세 설계)
```

---

## 4. Epic/Story 분해 현황

### 4.1 EPIC-01: Bamboo Specs 기반 플랜 생성기 구축

**상태**:大部分実装完了

| Story | 제목 | 상태 |
|-------|------|------|
| STORY-01 | 타겟 빌드 JSON 스키마 및 연도별 관리 구조 정의 | ✅ 완료 |
| STORY-02 | 다중 JSON 입력 로딩 및 빌드 정의 식별 기능 구현 | ✅ 완료 |
| STORY-03 | Bamboo Specs Java 코드 생성 기능 구현 | ✅ 완료 |
| STORY-04 | 빌드별 산출물 분리 및 등록 단위 구조 설계 | ✅ 완료 |
| STORY-05 | Atlassian Base 코드 확보 및 저장소 관리 체계 정의 | ⚠️ 보강 필요 |
| STORY-06 | 공통 워크플로우 템플릿 및 빌드 상세 입력 구조 정의 | ✅ 완료 |
| STORY-07 | 저장소 연결용 JSON 필드 및 검증 규칙 정의 | ✅ 완료 |
| STORY-08 | Bitbucket 저장소 연결 및 미등록 저장소 대응 설계 | ⚠️ 부분 구현 |
| STORY-09 | 브랜치별 연결 및 트리거 구성 생성 | ❌ 미구현 |
| STORY-10 | MSBuild 플랜용 Directory.Build.targets 사전 생성 지원 | ✅ 완료 |
| STORY-11 | 빌드 작업 하위 경로 지정 지원 | ✅ 완료 |
| STORY-12 | 플랜 스크립트 자산 분리 및 환경별 커스터마이징 관리 | ✅ 완료 |
| STORY-34 | 모듈형 빌드 구성과 CI 도구별 Task 확장 | 🆕 신규 요구사항 |

### 4.2 EPIC-02: 빌드 메타데이터 및 실행 이력의 DB 관리 전환

**상태**: 部分実装

| Story | 제목 | 상태 |
|-------|------|------|
| STORY-13 | 빌드 정의 DB 스키마 및 저장 모델 정의 | ✅ 부분 구현 |
| STORY-14 | 기존 JSON 빌드 정의의 DB 적재 및 동기화 경로 마련 | 📋 요구사항 정의 |
| STORY-15 | 빌드 실행 결과 저장 및 조회 모델 정의 | 📋 요구사항 정의 |
| STORY-16 | 빌드 버전 정보 및 변경 이력 추적 체계 정의 | 📋 요구사항 정의 |
| STORY-17 | 생성기의 DB 조회 전환 및 마이그레이션 전략 수립 | ✅ 부분 구현 |
| STORY-18 | 준비 스테이지 DB 변수 조회 및 프로젝트 메타데이터 확장 | ✅ 부분 구현 |
| STORY-19 | Django 운영 백엔드 및 Admin 기반 관리 구조 도입 | ✅ 부분 구현 |
| STORY-20 | Ninja API 및 조회용 프론트엔드 도입 | ✅ 부분 구현 |

### 4.3 EPIC-03: 통합 CI/CD 운영 관리 기능 확장

**상태**: 部分実装

| Story | 제목 | 상태 |
|-------|------|------|
| STORY-21 | 프로젝트 등록 기능 도입 | ✅ 부분 구현 |
| STORY-22 | 프로젝트 정보 조회 및 수정 기능 확장 | ✅ 부분 구현 |
| STORY-23 | 사용자 및 권한 관리 기능 도입 | ❌ 미구현 |
| STORY-24 | 빌드 현황 조회 기능 확장 | ✅ 부분 구현 |
| STORY-25 | Bamboo 시스템 운영 현황 조회 기능 도입 | ❌ 미구현 |
| STORY-26 | 운영 관리 API 표준화 | ✅ 부분 구현 |
| STORY-27 | 빌드 등록 구조 및 지원 언어/컴파일러 선택 방식 정의 | 📋 요구사항 정의 |

### 4.4 EPIC-04: 다중 CI 콘솔 및 Jenkins 운영 확장

**상태**: 新規要求事項

| Story | 제목 | 상태 |
|-------|------|------|
| STORY-29 | 다중 CI 도구 모드 전환 및 공통 상단 네비게이션 도입 | 📋 신규 요구사항 |
| STORY-30 | CI 도구별 테마 컬러와 공통 UI 문구 정비 | 📋 신규 요구사항 |
| STORY-31 | Jenkins 프로젝트 및 빌드 잡 등록 기능 도입 | 📋 신규 요구사항 |
| STORY-32 | CI 도구 공통 도메인/API 모델 확장 | 📋 신규 요구사항 |
| STORY-33 | Jenkins 시스템 운영 현황 조회 기능 도입 | 📋 신규 요구사항 |

---

## 5. 구현 아키텍처

### 5.1 생성기 파이프라인

```
JSON/DB 입력
    ↓
Input Adapter (JsonLoader / DbLoader)
    ↓
Validation / Normalization
    ↓
Unified Domain Model
    ↓
├── Script Asset Resolution / Rendering
├── Repository Linking / Trigger Mapping
├── Build Path / MSBuild Enrichment
    ↓
CI Provider Integrations (Bamboo Specs Generator)
    ↓
Artifact Writer / Summary Reporter
```

### 5.2 핵심 모듈 (src/bamboo_spec_generator/)

| 파일 | 책임 |
|------|------|
| `cli.py` | CLI 실행 진입점 |
| `parser.py` | JSON 입력 탐색 및 파싱 |
| `validator.py` | 입력 검증 |
| `model.py` | 내부 데이터 모델 |
| `script_assets.py` | Task 스크립트 자산 선택 및 로딩 |
| `script_renderer.py` | Task 스크립트 렌더링 |
| `java_assets.py` | OS별 Java wrapper 자산 선택 |
| `generator.py` | Java Specs 코드와 Coverity 설정 생성 |
| `writer.py` | 출력 파일 기록 |
| `api_client.py` | 운영 API 클라이언트 |

### 5.3 백엔드 구조 (backend/)

```
backend/
├── apps/
│   ├── api/           # Ninja REST API
│   │   ├── routers/   # API 엔드포인트
│   │   ├── schemas/  # Pydantic 스키마
│   │   └── auth.py   # 인증
│   ├── buildmeta/    # 빌드 메타데이터 도메인
│   │   ├── models/   # ORM 모델
│   │   ├── services/ # 도메인 서비스
│   │   └── migrations/ # DB 마이그레이션
│   └── ui/           # Django 템플릿 UI
├── config/           # Django 설정
└── manage.py         # Django 관리 명령
```

### 5.4 주요 API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/api/v1/projects/` | GET, POST | 프로젝트 목록/등록 |
| `/api/v1/projects/{key}` | GET, PUT | 프로젝트 상세/수정 |
| `/api/v1/build-plans/{planKey}/active-definition` | GET | 활성 빌드 정의 조회 |
| `/api/v1/build-plans/{planKey}/prepare-context` | GET | 준비 스테이지 변수 조회 |
| `/api/v1/build-plans/{planKey}/executions` | GET | 빌드 실행 이력 조회 |
| `/api/v1/admin/modules/` | GET | 모듈 자산 목록 조회 |
| `/api/v1/admin/modules/uploads` | POST | 모듈 자산 업로드 |
| `/api/v1/admin/modules/reload` | POST | 활성 모듈 재로드 |

---

## 6. 현재 구현 상태

### 6.1 ✅ 구현 완료

1. **생성기 본체**
   - JSON 파싱, 검증, 내부 모델 변환
   - Bamboo Specs Java 코드 생성
   - 스크립트 자산 관리 및 렌더링
   - MSBuild 보정
   - 저장소 연결 및 브랜치 트리거 생성

2. **운영 백엔드**
   - Django/Ninja 스캐폴딩
   - ORM 모델 및 마이그레이션
   - 프로젝트 CRUD API
   - BuildInfo 관리
   - Ninja API 엔드포인트
   - 조회용 웹 UI (Django 템플릿)
   - SQLite/PostgreSQL 전환 지원

3. **모듈 레지스트리**
   - 모듈 업로드/활성화/재로드 API
   - 모듈 관리 UI (`/settings/modules/`)
   - 샘플 데이터 적재 명령

### 6.2 ⚠️ 부분 구현

1. **Bamboo 연동**
   - 활성 정의 조회 → ✅
   - prepare-context 조회 → ✅
   - 실제 Bamboo 준비 스테이지 연동 → ❌
   - 빌드 결과 end-to-end 적재 → ❌

2. **버전 관리**
   - 버전 계산 규칙 → ✅ (초안)
   - 동일 커밋 재빌드 처리 → ✅ (초안)
   - 실제 운영 적용 → ❌

3. **UI**
   - 프로젝트 목록/상세 → ✅
   - 빌드 상세 → ✅
   - Bamboo/Jenkins 모드 전환 → ❌
   - 배포/릴리스 조회 → ❌

### 6.3 ❌ 미구현

1. **사용자 관리**
   - 사용자 계정/역할/권한 관리

2. **Bamboo/Jenkins 운영 현황**
   - 에이전트/노드 상태 조회
   - 실행 중 작업/대기열 조회

3. **Jenkins 통합**
   - Jenkins 프로젝트/잡 등록
   - Jenkins 모드 전환 UI
   - Jenkins 운영 현황 조회

---

## 7. 데이터 모델 (주요 엔터티)

### 7.1 백엔드 ORM 모델

| 모델 | 설명 |
|------|------|
| `Project` | Jira/Bitbucket 기준 상위 프로젝트 |
| `ProjectRepository` | 프로젝트 내 개별 저장소 |
| `BuildUnit` | Bamboo 플랜 또는 Jenkins 잡 기준 공통 빌드 단위 |
| `BambooBuildUnit` | Bamboo 전용 빌드 정보 |
| `JenkinsBuildUnit` | Jenkins 전용 빌드 정보 |
| `BuildUnitDefinition` | 생성기 입력 정의 스냅샷 |
| `BuildVersion` | 버전 대표 상태 |
| `BuildExecution` | 개별 빌드 실행 이력 |
| `StaticAnalysisResult` | 정적분석 결과 |
| `BambooPublishExecution` | Bamboo Specs publish 이력 |
| `SystemSetting` | 운영 공통 설정 (Coverity URL 등) |

### 7.2 입력 JSON 구조

```json
{
  "buildId": "sample-app-api",
  "name": "Sample App API",
  "planKey": "SAMPAPI",
  "language": "java",
  "compiler": "maven",
  "repository": {
    "provider": "bitbucket",
    "projectKey": "SAMPLE",
    "repoSlug": "sample-app-api",
    "linkageMode": "linked",
    "branches": ["dev", "release", "master"]
  },
  "requirements": {
    "os": "linux"
  },
  "build": {
    "subPath": ".",
    "prepareCommand": "mvn -B dependency:go-offline",
    "buildCommand": "mvn -B clean package",
    "runtimeRequirements": {
      "commands": ["mvn", "coverity"],
      "envVars": ["PATH", "JAVA_HOME"]
    }
  }
}
```

---

## 8. 최근 커밋 로그

| 커밋 | 메시지 |
|------|--------|
| `15bc561` | Add module registry management flow |
| `d44df86` | Implement Jenkins auto-config flow and infra settings updates |
| `b0e4bce` | Refactor CI/repository flow and squash buildmeta migrations |
| `8b7eb8e` | fix: use Jenkins job path in detail links |
| `2269987` | fix: stabilize multi-ci navigation and fresh-db setup |
| `70a6c74` | Add unified settings page with CI/Static Analysis/Repository sections |
| `b6ba4c9` | refactor: remove _v2 suffix from DB tables and update docs |
| `558eb87` | fix: resolve externalKey and providerDetails in legacy build payload handling |

---

## 9. 미구현 중요 기능

### 9.1 Bamboo 준비 스테이지 연동

- 현재: 활성 정의 조회, prepare-context 조회 API 구현
- 미구현: 실제 Bamboo 작업에서 변수 주입 연동

### 9.2 빌드 결과 적재

- 현재: API 스키마와 서비스 초안 구현
- 미구현: Bamboo/Jenkins에서 실제 빌드 결과 수집 → API 적재 흐름

### 9.3 배포/릴리스 관리

- 현재: ERD/설계 문서에만 존재
- 미구현: 전체 기능

### 9.4 Jenkins 통합

- 현재: 요구사항/설계 문서
- 미구현: Jenkins 프로젝트 등록, 모드 전환 UI, Jenkins 운영 현황 조회

### 9.5 사용자/권한 관리

- 현재: 문서에만 정의
- 미구현: 전체 기능

---

## 10. 개발 환경

### 10.1 의존성

- Python 3
- Java 17+ (Bamboo Specs 컴파일용)
- Maven 3.9+
- PostgreSQL (운영) / SQLite (개발)
- Django + django-ninja

### 10.2 실행 명령

```bash
# 생성기 실행
PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli

# 백엔드 실행
cd backend
python3 manage.py migrate
python3 manage.py runserver

# 테스트
PYTHONPATH=. python3 -m unittest discover -s tests
cd backend && python3 manage.py test --settings=config.settings.test
```

### 10.3 Docker 서비스

```bash
docker compose --env-file compose.env up -d
# postgres, jenkins, gitea
```

---

## 11. 현재 브랜치 상태

| 항목 | 값 |
|------|-----|
| 현재 브랜치 | `opencode/refactoring_work` |
| 베이스 | `codex/feature-extension-prep` (커밋 15bc561) |
| 원격 동기화 | ✅ 동기화됨 |
| 변경 파일 | 없음 |

---

## 12. 문서 파일 위치

### 12.1 요구사항 문서

- `docs/requirements/CRS.md` - 고객 요구사항
- `docs/requirements/SRS.md` - 시스템 요구사항
- `docs/requirements/issues/BREAKDOWN.md` - Epic/Story 분해
- `docs/requirements/infrastructure_settings_requirements.md` - 인프라 설정 요구사항

### 12.2 설계 문서

- `docs/designs/Design.md` - 상세 설계
- `docs/designs/SAD.md` - 아키텍처 설계
- `docs/designs/repository_connection_support.md` - 저장소 연결 설계
- `docs/designs/detailed_designs/` - 상세 설계 모음

### 12.3 테스트 문서

- `docs/tests/e2e_test_case_set.md`
- `docs/tests/ui_test_case_set.md`
- `docs/tests/api_test_case_set.md`

---

## 13. 결론

`bamboo_spec_generator`는:

1. **완료된 영역**: Bamboo Specs 생성기 본체, 기본 Django/Ninja 백엔드, 프로젝트/BuildInfo 관리, 모듈 레지스트리

2. **진행 중인 영역**: Bamboo 연동 (부분), 버전 관리 (초안), UI 확장

3. **미구현 영역**: 사용자 권한, Jenkins 통합, 배포/릴리스 관리, Bamboo/Jenkins 운영 현황 조회

**다음 단계로 권장**:
- STORY-09 (브랜치별 트리거 생성) 구현
- STORY-18/20 (Bamboo 연동 완성)
- STORY-21/22 (프로젝트 관리 고도화)
- STORY-29~33 (Jenkins 통합 준비)
