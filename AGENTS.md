# bamboo_spec_generator

이 저장소는 Python 기반 Bamboo Specs 생성기와 Django/Ninja 운영 백엔드를 함께 포함합니다. 루트에는 문서, 입력 샘플, 생성 결과물, 테스트, 백엔드/생성기 코드가 공존합니다.

## 프로젝트 구조

- 생성기 애플리케이션 코드는 `src/bamboo_spec_generator/` 아래에 둡니다.
- 운영 백엔드 코드는 `backend/` 아래에 둡니다.
- 테스트 코드는 기본적으로 `tests/` 또는 각 Django 앱의 `tests.py`에 둡니다.
- 문서는 `docs/` 아래에 두고, 요구사항/설계 문서는 기존 디렉터리 체계를 유지합니다.
- 특정 하위 시스템에만 다른 규칙이 필요할 때만 하위 디렉터리에 더 구체적인 `AGENTS.md`를 추가합니다.

## 작업 방식

- 변경 전에 항상 저장소 상태를 확인합니다. 작업 트리에 사용자 소유 변경사항이 있을 수 있습니다.
- 넓은 범위의 초기 스캐폴딩보다 작고 검토 가능한 변경을 우선합니다.
- 새로운 도구를 도입하면 설정 방법과 실행 명령을 `README.md`에도 함께 문서화합니다.
- 패키지 매니저, 빌드 시스템, CI 워크플로를 추가하면 에이전트가 따라야 할 정확한 명령을 이 파일에 갱신합니다.
- 앞으로 이 저장소에서 반복적으로 따라야 할 작업 지침이나 운영 규칙이 생기면 `AGENTS.md`에 기록하고 유지합니다.
- 새 브랜치를 만들 때는 항상 최신 `dev` 브랜치에서 분기합니다.
- 새 작업은 가능하면 `codex/{브랜치명}` 형식의 브랜치를 생성해 진행합니다.
- 1차 PR은 `dev` 브랜치를 대상으로 생성하고, `dev`에서 검증한 뒤 `main`으로 올리는 흐름을 기본으로 사용합니다.
- 생성, 컴파일, 테스트 같은 실행 작업은 반드시 순차적으로 수행합니다.
- 앞 단계가 끝난 것을 확인하기 전에는 다음 실행 단계를 시작하지 않습니다.
- 지시하는 요구사항은 항상 CRS, SRS, 디자인 설계 등에 반영해야할지 판단합니다.

## 명령어

- 현재 표준 패키징 설정 파일은 없지만, Python 실행과 Django 관리 명령을 기준으로 작업합니다.
- 백엔드와 UI E2E 의존성은 각각 `requirements-backend.txt`, `requirements-playwright.txt`로 관리합니다.
- Install: `python3 -m pip install -r requirements-backend.txt`
- Build: `PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli`
- Lint: `현재 별도 린트 명령 없음`
- Test: `PYTHONPATH=. python3 -m unittest discover -s tests`
- Test: `(cd backend && python3 manage.py test --settings=config.settings.test)`
- Check: `(cd backend && python3 manage.py check)`

## 코드 스타일

- 수정하는 파일에 이미 존재하는 규칙과 관례를 따릅니다.
- 성급한 추상화보다 명확한 이름과 단순한 구조를 우선합니다.
- 주석은 꼭 필요한 경우에만 짧게 추가하고, 코드만으로 의도가 충분히 드러나면 생략합니다.
- 프로젝트 방향상 타당한 이유가 없으면 큰 의존성이나 생성기를 추가하지 않습니다.
- Bamboo 빌드 Task에서 스크립트를 사용할 때는 가능하면 Windows와 Linux에서 모두 호환될 수 있도록 shell 전용 스크립트보다 Python 스크립트 호출 방식을 우선합니다.

## 테스트

- 테스트 프레임워크가 생긴 뒤에는 동작이 바뀌는 변경에 맞춰 테스트를 추가하거나 갱신합니다.
- 자동 테스트 전부가 통과하지 않으면 어떤 명령이 실패했는지 최종 보고에 구체적으로 남깁니다.
- 실행 가능한 테스트 명령이 없거나 일부만 확인했을 때는 충분히 검증되었다고 단정하지 않습니다.

## 보안 및 설정

- 비밀값, 인증 정보, 토큰은 절대 커밋하지 않습니다.
- 런타임 설정이 생기면 민감한 값은 환경 변수로 관리합니다.
- 설정 파일을 추가할 때 필요하면 `.env.example` 같은 안전한 예시 파일도 함께 둡니다.

## 문서화

- `README.md`는 항상 실제 저장소 상태와 맞게 유지합니다.
- 새로운 진입점, 스크립트, 필수 환경 변수는 도입 시점에 바로 문서화합니다.
- 앞으로 이 저장소에서 새로 작성하거나 크게 갱신하는 문서는 가능하면 한글을 기본 언어로 사용합니다.
- 사용자 요청에 `요구사항 등록` 키워드가 포함되면 입력된 내용을 정리해 CRS 형식의 문서로 작성하고 `docs/requirements/` 아래에 기록합니다.
- 요구사항이나 작업 내용을 문서화할 때는 가능하면 Jira 등록 단위의 이슈 문서로 함께 분해해 기록합니다.
- 사용자 요청에 `요구사항 분석` 키워드가 포함되면 기존 문서와 프롬프트를 참고해 요구사항을 분석하고 SRS 형식으로 출력합니다.
- `요구사항 분석` 결과로 초기 디자인이나 설계를 구체화할 수 있으면 관련 문서를 `docs/designs/` 아래에 작성합니다.
- 요구사항 문서와 디자인 문서는 향후 Jira 이슈로 옮기기 쉽도록 작성합니다.
- 요구사항 문서는 가능하면 `요약`, `배경`, `문제`, `범위`, `요구사항`, `수용 기준`, `제약/가정`, `오픈 이슈`, `다음 단계`를 포함합니다.
- 디자인 문서는 가능하면 `요약`, `배경`, `목표`, `비목표`, `설계안`, `대안`, `영향 범위`, `수용 기준`, `오픈 이슈`를 포함합니다.
- 문서 내 링크는 웹 환경에서도 동작할 수 있도록 절대경로 대신 상대경로 마크다운 링크를 사용합니다.



## Rust 백엔드 리팩토링 (Refactoring)

### 개요

기존 Django/Ninja 백엔드를 Rust 기반으로 리팩토링합니다.

- **프론트엔드**: React + TypeScript
- **백엔드**: Rust + Actix-web 또는 Axum
- **데이터베이스**: PostgreSQL (기존 유지)

### 백엔드 구조

```
backend-rs/
├── src/
│   ├── main.rs              # 진입점
│   ├── lib.rs               # 라이브러리 루트
│   ├── api/                 # API 레이어
│   │   ├── mod.rs
│   │   ├── routes/          # API 엔드포인트
│   │   ├── models/          # Request/Response 모델
│   │   └── middleware/      # 인증, 로깅 등
│   ├── domain/              # 도메인 레이어
│   │   ├── mod.rs
│   │   ├── projects/        # 프로젝트 도메인
│   │   ├── build_plans/     # 빌드 플랜 도메인
│   │   ├── executions/      # 실행 이력 도메인
│   │   └── module_registry/ # 모듈 레지스트리
│   ├── infrastructure/      # 인프라 레이어
│   │   ├── mod.rs
│   │   ├── database/        # DB 연결 (sqlx)
│   │   ├── repositories/    # 데이터 접근
│   │   └── external/        # Bamboo/Jenkins API 클라이언트
│   └── workers/             # 백그라운드 워커
│       ├── mod.rs
│       └── build_collector/ # 빌드 결과 수집
├── Cargo.toml
└── .env.example
```

### API 엔드포인트 매핑 (Django → Rust)

| 기존 Django 엔드포인트 | Rust 엔드포인트 | 상태 |
|----------------------|----------------|------|
| `GET /api/v1/projects/` | `GET /api/v1/projects/` | 구현 |
| `POST /api/v1/projects/` | `POST /api/v1/projects/` | 구현 |
| `GET /api/v1/projects/{key}` | `GET /api/v1/projects/{key}` | 구현 |
| `PUT /api/v1/projects/{key}` | `PUT /api/v1/projects/{key}` | 구현 |
| `GET /api/v1/build-plans/{plan_key}/active-definition` | 同 | 구현 |
| `GET /api/v1/build-plans/{plan_key}/prepare-context` | 同 | 구현 |
| `GET /api/v1/build-plans/{plan_key}/executions` | 同 | 구현 |
| `GET /api/v1/admin/modules/` | `GET /api/v1/modules/` | 구현 |
| `POST /api/v1/admin/modules/uploads` | `POST /api/v1/modules/upload` | 구현 |
| `POST /api/v1/admin/modules/reload` | `POST /api/v1/modules/reload` | 구현 |
| `GET /api/v1/system-settings/` | `GET /api/v1/settings/` | 구현 |
| `PUT /api/v1/system-settings/{key}` | `PUT /api/v1/settings/{key}` | 구현 |

### Rust 의존성

```toml
[dependencies]
actix-web = "4"          # 또는 axum = "0.7"
tokio = { version = "1", features = ["full"] }
sqlx = { version = "0.7", features = ["runtime-tokio-native-tls", "postgres"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tracing = "0.1"
tracing-subscriber = "0.3"
thiserror = "1"
anyhow = "1"
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
```

### 빌드 & 실행 명령

```bash
# 빌드
cd backend-rs
cargo build --release

# 개발 모드
cargo run

# 테스트
cargo test

# 린트
cargo clippy
cargo fmt
```

### 데이터베이스 마이그레이션

- 기존 PostgreSQL 스키마 유지
- `sqlx`의 offline mode로 마이그레이션 관리
- 마이그레이션 파일: `migrations/` 디렉토리

---

## Rust 문서화 규칙

### 구현 시 문서 필수 작성

Rust 모듈/함수를 구현할 때 반드시 다음 문서를 함께 작성합니다:

| 단계 | 문서 | 위치 |
|------|------|------|
| 1 | API 엔드포인트 설명 | 코드 주석 (`///`) 또는 `docs/api/` |
| 2 | 도메인 로직 설명 | `docs/refactoring/domain/` |
| 3 | 데이터 모델 변경 | `docs/refactoring/models/` |
| 4 | 아키텍처 결정 (ADR) | `docs/refactoring/adrs/` |

### 문서 템플릿

#### 1. API 엔드포인트 문서 (`docs/refactoring/api/{도메인}.md`)

```markdown
# {도메인} API

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | /api/v1/{resource} | 목록 조회 |
| POST | /api/v1/{resource} | 생성 |
| GET | /api/v1/{resource}/{{id}} | 상세 조회 |
| PUT | /api/v1/{resource}/{{id}} | 수정 |

## 요청/응답 예시

### GET /api/v1/projects

**Request:**
```http
GET /api/v1/projects
Authorization: Bearer {token}
```

**Response:**
```json
{
  "projects": [...]
}
```
```

#### 2. 도메인 문서 (`docs/refactoring/domain/{도메인}.md`)

```markdown
# {도메인} 도메인

## 개요

{도메인의 목적과 책임에 대한 설명}

## 주요 개념

- **Concept A**: 설명
- **Concept B**: 설명

##业务流程

1. 사용자 요청 수신
2. 검증
3. 도메인 로직 실행
4. 응답 반환

## 기존 Django 코드 대응

| Django | Rust |
|--------|------|
| `models.py` | `domain/{도메인}.rs` |
| `services.py` | `domain/{도메인}/services.rs` |
| `selectors.py` | `infrastructure/repositories/` |
```

#### 3. ADR (Architecture Decision Record) (`docs/refactoring/adrs/adr-001-{제목}.md`)

```markdown
# ADR-{序号}: {제목}

## 상태

- 제안됨 / 수락됨 / 폐기됨

## 배경

{결정이 필요한 상황 설명}

## 결정 사항

{採择한 결정}

## 대안

### 대안 1: {제목}
- 장점: ...
- 단점: ...

### 대안 2: {제목}
- 장점: ...
- 단점: ...

## 결과

### 긍정적 효과
- ...

### 부정적 효과
- ...

## 참고

- 관련 이슈/PR
```

### 코드 주석 규칙

```rust
/// 프로젝트 목록 조회
///
/// # Arguments
/// * `ci_provider` - 선택적 CI 제공자 필터 (bamboo 또는 jenkins)
///
/// # Errors
/// - 401: 인증 실패
/// - 500: 서버 오류
///
/// # Example
/// ```rust
/// let projects = list_projects(pool, None).await?;
/// ```
async fn list_projects(
    State(pool): State<PgPool>,
    Query(params): Query<ListProjectsQuery>,
) -> Result<Json<ListProjectsResponse>, AppError> {
    // ...
}
```

### 가이드라인

1. **구현 전**: 기존 Django 코드를 분석하고 문서화
2. **구현 중**: 코드와 함께 주석 작성
3. **구현 후**: `docs/refactoring/`에 종합 문서 업데이트
4. **변경 시**: changelog 또는 ADR에 기록

---

## 기존 Django 백엔드 참조

기존 Django/Ninja 백엔드는 `backend/`에 위치하며, Rust로의 마이그레이션 완료 후 비활성화합니다.

### 참고 파일

- API 라우터: `backend/apps/api/router.py`
- 도메인 모델: `backend/apps/buildmeta/models/`
- 서비스 로직: `backend/apps/buildmeta/services/`
- API 스키마: `backend/apps/api/schemas/`

### 마이그레이션 체크리스트

- [ ] 프로젝트 CRUD API
- [ ] 빌드 플랜 API
- [ ] 실행 이력 API
- [ ] 모듈 레지스트리 API
- [ ] 시스템 설정 API
- [ ] Jenkins 연동 API
- [ ] Bamboo 연동 API
- [ ] 인증/인가 레이어
- [ ] 데이터 마이그레이션 스크립트