# Rust 백엔드 리팩토링 아키텍처

## 문서 개요

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-03-28 |
| 상태 | 초안 |
| 대상 | bamboo_spec_generator Rust 백엔드 |

---

## 1. 개요

### 1.1 목적

기존 Django/Ninja 기반 백엔드를 Rust 기반으로 리팩토링하여:
- 성능 향상
- 메모리 사용량 절감
- 동시 처리 능력 강화
- 마이크로서비스 아키텍처 기반 확장성 확보

### 1.2 목표

1. 기존 Django API와 100% 호환 (기능적으로 동등)
2. PostgreSQL 스키마 유지 (데이터 마이그레이션 최소화)
3. 문서와 가이드를 구현과 함께 작성
4. 단계적 마이그레이션 지원

---

## 2. 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                     React + TypeScript                       │
│                        (Frontend)                            │
└─────────────────────────────┬───────────────────────────────┘
                              │ HTTP API
┌─────────────────────────────▼───────────────────────────────┐
│                     Rust Backend                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 API Layer (Actix-web)                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │   │
│  │  │ Projects │ │BuildPlans│ │ Modules  │ │ Settings│ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │   │
│  └─────────────────────────────┬───────────────────────┘   │
│                                │                            │
│  ┌─────────────────────────────▼───────────────────────┐   │
│  │               Domain Layer (Services)                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │   │
│  │  │ Projects │ │BuildPlans│ │ Modules  │ │  CI    │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │   │
│  └─────────────────────────────┬───────────────────────┘   │
│                                │                            │
│  ┌─────────────────────────────▼───────────────────────┐   │
│  │           Infrastructure Layer                       │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────┐   │   │
│  │  │ Database   │ │ Repository │ │ External APIs  │   │   │
│  │  │ (sqlx)     │ │            │ │(Bamboo/Jenkins)│   │   │
│  │  └────────────┘ └────────────┘ └────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    PostgreSQL Database                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 계층 설명

| 계층 | 책임 | 주요 모듈 |
|------|------|----------|
| **API Layer** | HTTP 요청/응답, 라우팅 | `api/routes/*` |
| **Domain Layer** | 비지니스 로직 | `domain/*` |
| **Infrastructure Layer** | DB 접근, 외부 API | `infrastructure/*` |

---

## 3. 디렉터리 구조

### 3.1 Proposed Structure

```
backend-rs/
├── src/
│   ├── main.rs                 # 애플리케이션 진입점
│   ├── lib.rs                  # 라이브러리 루트
│   │
│   ├── api/                    # API 레이어
│   │   ├── mod.rs
│   │   ├── routes/             # HTTP 엔드포인트
│   │   │   ├── mod.rs
│   │   │   ├── projects.rs
│   │   │   ├── build_plans.rs
│   │   │   ├── executions.rs
│   │   │   ├── modules.rs
│   │   │   └── settings.rs
│   │   ├── models/             # Request/Response DTO
│   │   │   ├── mod.rs
│   │   │   ├── projects.rs
│   │   │   └── common.rs
│   │   └── middleware/         # 인증, 로깅 등
│   │       ├── mod.rs
│   │       └── auth.rs
│   │
│   ├── domain/                 # 도메인 레이어
│   │   ├── mod.rs
│   │   ├── projects/           # 프로젝트 도메인
│   │   │   ├── mod.rs
│   │   │   ├── entities.rs    # 도메인 엔터티
│   │   │   └── services.rs    # 비지니스 로직
│   │   ├── build_plans/       # 빌드 플랜 도메인
│   │   │   ├── mod.rs
│   │   │   ├── entities.rs
│   │   │   └── services.rs
│   │   ├── executions/         # 실행 이력 도메인
│   │   ├── modules/            # 모듈 레지스트리 도메인
│   │   └── settings/          # 시스템 설정 도메인
│   │
│   ├── infrastructure/         # 인프라 레이어
│   │   ├── mod.rs
│   │   ├── database/           # DB 연결 관리
│   │   │   ├── mod.rs
│   │   │   ├── pool.rs
│   │   │   └── migrations/
│   │   ├── repositories/       # 데이터 접근 객체
│   │   │   ├── mod.rs
│   │   │   ├── project_repo.rs
│   │   │   └── build_plan_repo.rs
│   │   └── external/           # 외부 API 클라이언트
│   │       ├── mod.rs
│   │       ├── bamboo_client.rs
│   │       └── jenkins_client.rs
│   │
│   └── workers/                # 백그라운드 워커
│       ├── mod.rs
│       └── build_collector/    # 빌드 결과 수집
│
├── Cargo.toml
├── .env.example
└── README.md
```

### 3.2 Layer Responsibilities

| 디렉터리 | 책임 | 기존 Django 대응 |
|---------|------|-----------------|
| `api/routes/` | HTTP 핸들러 | `routers/*.py` |
| `api/models/` | DTO/스키마 | `schemas/*.py` |
| `domain/*/entities.rs` | 도메인 엔터티 | `models/*.py` |
| `domain/*/services.rs` | 비지니스 로직 | `services/*.py` |
| `infrastructure/repositories/` | 데이터 접근 | Django ORM |
| `infrastructure/external/` | 외부 API | `api_client.py` |

---

## 4. API 엔드포인트 매핑

### 4.1 Projects

| Django | Rust | 메서드 |
|--------|------|--------|
| `GET /api/v1/projects/` | `GET /api/v1/projects/` | 목록 조회 |
| `POST /api/v1/projects/` | `POST /api/v1/projects/` | 프로젝트 생성 |
| `GET /api/v1/projects/{key}` | `GET /api/v1/projects/{key}` | 상세 조회 |
| `PUT /api/v1/projects/{key}` | `PUT /api/v1/projects/{key}` | 프로젝트 수정 |

### 4.2 Build Plans

| Django | Rust | 메서드 |
|--------|------|--------|
| `GET /api/v1/build-plans/{plan_key}/active-definition` | 同 | 활성 정의 조회 |
| `GET /api/v1/build-plans/{plan_key}/prepare-context` | 同 | 준비 컨텍스트 조회 |
| `GET /api/v1/build-plans/{plan_key}/executions` | 同 | 실행 이력 조회 |

### 4.3 Modules

| Django | Rust | 메서드 |
|--------|------|--------|
| `GET /api/v1/admin/modules/` | `GET /api/v1/modules/` | 목록 조회 |
| `POST /api/v1/admin/modules/uploads` | `POST /api/v1/modules/upload` | 업로드 |
| `POST /api/v1/admin/modules/reload` | `POST /api/v1/modules/reload` | 재로드 |
| `GET /api/v1/admin/modules/load-status` | `GET /api/v1/modules/load-status` | 상태 조회 |

### 4.4 Settings

| Django | Rust | 메서드 |
|--------|------|--------|
| `GET /api/v1/system-settings/` | `GET /api/v1/settings/` | 설정 조회 |
| `PUT /api/v1/system-settings/{key}` | `PUT /api/v1/settings/{key}` | 설정 수정 |

---

## 5. 데이터베이스

### 5.1 기존 스키마 유지

기존 Django의 PostgreSQL 스키마를 그대로 사용합니다.

### 5.2 ORM/DAL

`sqlx`를 사용한 Raw SQL 또는 쿼리 빌더 패턴:

```rust
// 예시: 프로젝트 조회
sqlx::query_as!(
    Project,
    r#"SELECT id, jira_project_key, bitbucket_project_key, ... FROM project"#
)
.fetch_all(&pool)
.await
```

### 5.3 마이그레이션

- `sqlx migrate` 명령 사용
- 마이그레이션 파일: `infrastructure/database/migrations/`
- 기존 Django 마이그레이션에서 SQL 추출

---

## 6. 외부 API 연동

### 6.1 Bamboo Client

```rust
// 예시: 플랜 정의 조회
pub async fn get_plan_definition(
    &self,
    plan_key: &str,
) -> Result<PlanDefinition, BambooError>;
```

### 6.2 Jenkins Client

```rust
// 예시: 빌드 정보 조회
pub async fn get_build_info(
    &self,
    job_name: &str,
    build_number: u32,
) -> Result<BuildInfo, JenkinsError>;
```

---

## 7. 인증

### 7.1 Bearer Token 인증

기존 Django의 `GeneratorTokenAuth`를 Rust로 포팅:

```rust
// 미들웨어 예시
async fn auth_middleware(
    req: ServiceRequest,
    next: NextService,
) -> Result<ServiceResponse, ActixWebError> {
    // 토큰 검증 로직
    next(req).await
}
```

---

## 8. 구현 순서

### Phase 1: 기반 구조

1. [ ] 프로젝트 스캐폴딩 (Cargo.toml, 기본 구조)
2. [ ] 데이터베이스 연결 설정 (sqlx)
3. [ ] 로깅 및 에러 처리 기본 구조
4. [ ] 인증 미들웨어

### Phase 2: 핵심 API

5. [ ] 프로젝트 CRUD API
6. [ ] 빌드 플랜 API
7. [ ] 실행 이력 API

### Phase 3: 확장 기능

8. [ ] 모듈 레지스트리 API
9. [ ] 시스템 설정 API
10. [ ] Bamboo/Jenkins 연동

### Phase 4: 워커

11. [ ] 빌드 결과 수집 워커
12. [ ] 스케줄러 통합

---

## 9. 문서화 체크리스트

| 구현 단계 | 문서 |
|----------|------|
| API 엔드포인트 | `docs/refactoring/api/{도메인}.md` |
| 도메인 로직 | `docs/refactoring/domain/{도메인}.md` |
| 아키텍처 결정 | `docs/refactoring/adrs/adr-001-{제목}.md` |
| 코드 주석 | Rust doc comments (`///`) |

---

## 10. 참고

- 기존 Django 코드: `backend/apps/`
- 문서 템플릿: `AGENTS.md`의 "Rust 문서화 규칙" 참조
- 테스트: `cargo test` 명령 사용
