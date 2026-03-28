# OpenCode 세션 전환 가이드

## 현재 상태

| 항목 | 상태 |
|------|------|
| **브랜치** | `opencode/refactoring_work` |
| **마지막 커밋** | `4540fc1` - feat: add Rust backend scaffolding and documentation |
| **원격** | `origin/opencode/refactoring_work` (푸시됨) |

---

## 진행 상황

### ✅ 완료된 작업

1. **Rust 백엔드 스캐폴딩** (47개 파일)
   - API 라우트: projects, build_plans, modules, settings
   - 도메인 레이어: entities + services
   - 인프라 레이어: database (sqlx), repositories, external clients
   - 워커: BuildCollector

2. **문서화**
   - `docs/opencode_summary/` - 프로젝트 분석 요약
   - `docs/refactoring/` - Rust 백엔드 아키텍처
   - `AGENTS.md` - Rust 백엔드 가이드라인 업데이트

3. **Git 설정**
   - `.gitignore` - Rust/OpenCode artifacts 추가

---

## 다음 작업 (해야 할 것)

### 1. Rust 빌드 검증 (로컬 환경)

```bash
# Ubuntu 24.04 또는 Rust 설치된 환경에서

cd backend-rs

# 빌드
cargo build

# 실행
cargo run
```

### 2. 실제 비지니스 로직 구현

현재 API들은 스텁(Stub) 상태입니다. 실제 구현 필요:

| 파일 | 현재 상태 | 필요한 작업 |
|------|----------|------------|
| `src/api/routes/projects.rs` | Stub | 실제 DB 연동 |
| `src/api/routes/build_plans.rs` | Stub | 활성 정의 조회 구현 |
| `src/infrastructure/repositories/` | 기본 구조 | SQL 쿼리 구현 |
| `src/domain/*/services.rs` | Stub | 비지니스 로직 구현 |

### 3. 데이터베이스 연동

- PostgreSQL 연결 설정
- 기존 Django 스키마 기반 테이블 생성
- 마이그레이션 파일 작성

---

## 프로젝트 구조

```
backend-rs/
├── Cargo.toml              # 의존성 (actix-web, sqlx, tokio, etc.)
├── .env.example           # 환경 변수 예시
├── README.md              # 프로젝트 문서
└── src/
    ├── main.rs            # 진입점
    ├── lib.rs
    ├── api/
    │   ├── routes/        # HTTP 엔드포인트
    │   │   ├── projects.rs
    │   │   ├── build_plans.rs
    │   │   ├── modules.rs
    │   │   └── settings.rs
    │   ├── models/        # DTO
    │   └── middleware/     # 인증
    ├── domain/            # 도메인 레이어
    │   ├── projects/
    │   ├── build_plans/
    │   ├── executions/
    │   ├── modules/
    │   └── settings/
    ├── infrastructure/    # 인프라 레이어
    │   ├── database/      # sqlx DB pool
    │   ├── repositories/  # 데이터 접근
    │   └── external/      # Bamboo/Jenkins API 클라이언트
    └── workers/           # 백그라운드 워커
```

---

## 키 파일 참조

### 기존 Django 백엔드 (참고용)

| 파일 | 설명 |
|------|------|
| `backend/apps/api/router.py` | 기존 API 라우터 |
| `backend/apps/buildmeta/models/` | 기존 ORM 모델 |
| `backend/apps/buildmeta/services/` | 기존 서비스 로직 |
| `backend/apps/api/schemas/` | 기존 스키마 |

### 문서

| 파일 | 설명 |
|------|------|
| `docs/refactoring/README.md` | Rust 아키텍처 설계 |
| `docs/refactoring/api/endpoints.md` | API 매핑 |
| `AGENTS.md` | Rust 개발 가이드라인 |

---

## 환경 설정

### Ubuntu 24.04에서 빌드

```bash
# 1. 필수 도구 설치
sudo apt update
sudo apt install build-essential pkg-config libssl-dev

# 2. Rust 설치
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# 3. 프로젝트 빌드
cd backend-rs
cargo build
```

### .env 설정

```bash
cp .env.example .env
# DATABASE_URL, API_TOKEN, BAMBOO_URL, JENKINS_URL 등 설정
```

---

## 검증 명령어

```bash
# 빌드
cargo build

# 테스트
cargo test

# 린트
cargo clippy
cargo fmt

# 실행
cargo run
# 서버: http://127.0.0.1:8080
```

---

## 브랜치 상태 확인

```bash
git status
git log --oneline -5
git pull origin opencode/refactoring_work
```

---

## 참고 사항

1. **NixOS**: 현재 환경에서 빌드 불가 (OpenSSL 설정 복잡)
2. **Ubuntu 24.04**: 권장 개발 환경
3. **Rust 1.94.1**: 설치됨
4. **PostgreSQL**: 기존 Django DB 재사용 가능

---

*마지막 업데이트: 2026-03-28*
