# API 엔드포인트 매핑: Django → Rust

## 문서 개요

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-03-28 |
| 최종 갱신 | 2026-03-31 |
| 목적 | 현재 Rust 구현 기준으로 Django API 호환 범위와 경로를 기록 |

---

## 1. 기준

- Django 기준 라우트는 `backend/apps/api/router.py`, `backend/apps/api/routers/`이다.
- Rust 기준 라우트는 `backend-rs/src/api/routes/`이다.
- 이 문서는 "계획"이 아니라 현재 구현 상태를 기록한다.
- `구현`은 라우트와 주요 동작이 존재함을 의미한다.
- `부분 구현`은 경로는 존재하지만 일부 쓰기 로직 또는 세부 계약이 남아 있음을 의미한다.

---

## 2. Projects API

| Django | Rust | 상태 | 메모 |
|--------|------|------|------|
| `GET /api/v1/projects/` | `GET /api/v1/projects/` | 구현 | PostgreSQL 실데이터 조회 |
| `POST /api/v1/projects/` | `POST /api/v1/projects/` | 구현 | 프로젝트/저장소/빌드 단위 생성 및 대표 저장소 반영 |
| `GET /api/v1/projects/{project_key}` | `GET /api/v1/projects/{project_key}` | 구현 | Django 기준 상세 구조 반환 |
| `PUT /api/v1/projects/{project_key}` | `PUT /api/v1/projects/{project_key}` | 구현 | 프로젝트/저장소/빌드 단위 갱신 및 제거분 정리 |

주요 참고:

- `ci_provider` 필터 지원
- 생성/수정 포함 계약 테스트 존재
- 프로젝트 build payload와 응답의 기준 용어는 `language`, `compiler`, `runtimeStack`이다.
- `buildType`은 기존 클라이언트 호환을 위한 보조 필드로만 유지한다.

---

## 3. Build Plans API

| Django | Rust | 상태 | 메모 |
|--------|------|------|------|
| `GET /api/v1/build-plans/{plan_key}/active-definition` | 동일 | 구현 | 활성 정의 또는 fallback 정의 반환 |
| `GET /api/v1/build-plans/{plan_key}/prepare-context` | 동일 | 구현 | 저장소/변수/링크 모드 포함 |
| `GET /api/v1/build-plans/{plan_key}/executions` | 동일 | 구현 | 실행 이력과 정적 분석 결과 포함 |

주요 참고:

- `prepare-context`의 `create_if_missing` 규칙 계약 테스트 존재
- `active-definition`은 DB active definition이 없으면 fallback 조합 사용
- build plan summary와 prepare context의 build 메타데이터는 `language`, `compiler`, `runtimeStack` 기준으로 노출한다.

---

## 4. Executions API

| Django | Rust | 상태 | 메모 |
|--------|------|------|------|
| `POST /api/v1/build-plans/{plan_key}/executions/start` | 동일 | 구현 | 버전 계산, 실행 생성 |
| `POST /api/v1/build-executions/{execution_id}/finish` | 동일 | 구현 | 결과/요약/정적분석 저장 |
| `POST /api/v1/build-executions/{execution_id}/static-analysis-results` | 동일 | 구현 | upsert 동작 지원 |

주요 참고:

- 동일 커밋/빌드번호 재사용 규칙 반영
- 계약 테스트 존재

---

## 5. Module Registry API

현재 Rust는 Django와 같은 경로를 사용한다.

| Django | Rust | 상태 | 메모 |
|--------|------|------|------|
| `GET /api/v1/admin/modules/` | 동일 | 구현 | 목록 조회 |
| `GET /api/v1/admin/modules/load-status` | 동일 | 구현 | 로드 상태 조회 |
| `POST /api/v1/admin/modules/uploads` | 동일 | 구현 | 멀티파트 업로드 지원 |
| `POST /api/v1/admin/modules/reload` | 동일 | 구현 | 재로드 지원 |
| `GET /api/v1/admin/modules/{asset_id}` | 동일 | 구현 | 상세 조회 |
| `POST /api/v1/admin/modules/{asset_id}/activate` | 동일 | 구현 | 특정 버전 활성화 |
| `POST /api/v1/admin/modules/{asset_id}/deactivate` | 동일 | 구현 | 비활성화 |

주요 참고:

- 예전 문서의 `/api/v1/modules/*` 경로는 현재 기준과 다르다.
- 활성 파일 확장자 교체 케이스까지 반영됨

---

## 6. System Settings API

현재 Rust는 Django와 같은 경로를 사용한다.

| Django | Rust | 상태 | 메모 |
|--------|------|------|------|
| `GET /api/v1/system-settings/coverity` | 동일 | 구현 | Coverity 설정 조회 |
| `PUT /api/v1/system-settings/coverity` | 동일 | 구현 | Coverity 설정 저장 |
| `GET /api/v1/system-settings/bamboo` | 동일 | 구현 | Bamboo server URL/auth token 설정 조회 |
| `PUT /api/v1/system-settings/bamboo` | 동일 | 구현 | Bamboo server URL/auth token 설정 저장 |
| `GET /api/v1/system-settings/jenkins` | 동일 | 구현 | Jenkins server URL/username/token 설정 조회 |
| `PUT /api/v1/system-settings/jenkins` | 동일 | 구현 | Jenkins 설정 저장 |
| `GET /api/v1/system-settings/github` | 동일 | 구현 | GitHub server URL/auth token 설정 조회 |
| `PUT /api/v1/system-settings/github` | 동일 | 구현 | GitHub 설정 저장 |
| `GET /api/v1/system-settings/bitbucket` | 동일 | 구현 | Bitbucket server URL/auth token 설정 조회 |
| `PUT /api/v1/system-settings/bitbucket` | 동일 | 구현 | Bitbucket 설정 저장 |
| `GET /api/v1/system-settings/gitea` | 동일 | 구현 | Gitea server URL/auth token 설정 조회 |
| `PUT /api/v1/system-settings/gitea` | 동일 | 구현 | Gitea 설정 저장 |
| `POST /api/v1/system-settings/specs-drafts/initialize` | 동일 | 구현 | 전체 초기화 |
| `POST /api/v1/system-settings/specs-drafts/initialize/{planKey}` | 동일 | 구현 | 플랜 단위 초기화 |

주요 참고:

- Bamboo/GitHub/Bitbucket/Gitea는 모두 `serverUrl + token` 형태로 저장한다.
- 민감한 토큰 원문은 응답에 포함하지 않음

---

## 7. Jenkins Jobs API

| Django | Rust | 상태 | 메모 |
|--------|------|------|------|
| `GET /api/v1/jenkins-jobs/` | 동일 | 구현 | 목록 조회 |
| `GET /api/v1/jenkins-jobs/{job_path}/status` | 동일 | 구현 | 실 Jenkins 상태 조회 |
| `GET /api/v1/jenkins-jobs/{job_path}/details` | 동일 | 구현 | 상세/raw payload 조회 |
| `GET /api/v1/jenkins-jobs/{job_path}/executions` | 동일 | 구현 | DB 실행 이력 조회 |
| `POST /api/v1/jenkins-jobs/{job_path}/trigger` | 동일 | 구현 | 실 Jenkins trigger 호출 |
| `POST /api/v1/jenkins-jobs/{job_path}/configure` | 동일 | 구현 | 실 Jenkins pipeline job 생성/수정 |
| `GET /api/v1/jenkins-jobs/{job_path}/builds/{build_number}` | 동일 | 구현 | 실 Jenkins build 조회 |
| `GET /api/v1/jenkins-jobs/system-status` | 동일 | 구현 | node/queue 조회 |

주요 참고:

- `job_path`는 `/` 포함 path parameter 지원
- 실연동 계약 테스트 존재

---

## 8. Bamboo Build Plans API

현재 Rust는 `build-plans` 하위에 Bamboo 운영 경로를 추가했다.

| Django 서비스 | Rust | 상태 | 메모 |
|---------------|------|------|------|
| `get_bamboo_plan_status(plan_key)` | `GET /api/v1/build-plans/{plan_key}/bamboo/status` | 구현 | 실 Bamboo plan/result 조회 |
| `get_bamboo_plan_details(plan_key)` | `GET /api/v1/build-plans/{plan_key}/bamboo/details` | 구현 | stage/job/raw payload 및 publish history 포함 |
| `queue_bamboo_plan_with_options(plan_key, ...)` | `POST /api/v1/build-plans/{plan_key}/bamboo/queue` | 구현 | 실 Bamboo queue 호출, Bamboo 4xx를 그대로 오류 매핑 |
| `publish_bamboo_specs(plan_key)` | `POST /api/v1/build-plans/{plan_key}/bamboo/publish` | 구현 | 생성기 CLI + Maven publish + DB publish 이력 기록 |

주요 참고:

- 테스트 컨테이너 Bamboo 기준 실연동 검증 완료
- `bamboo.server.url`은 context path를 포함한 URL이어야 한다. 예: `http://127.0.0.1:8085/bamboo`
- publish 성공 시 `buildmeta_bamboo_publish_execution` 이력이 저장된다

---

## 9. 인증과 오류 응답

| 항목 | 현재 상태 |
|------|-----------|
| 인증 | `Authorization: Bearer <token>` |
| 기준 env | `BAMBOO_API_TOKEN` |
| 미설정 시 | `500` |
| 불일치 시 | `401` |
| 공통 오류 응답 | `{"error": "..."}` |

주요 참고:

- Django `GeneratorTokenAuth`와 호환되도록 맞춤
- `400/404/500/503` 매핑은 공통 응답 헬퍼 사용

---

## 10. 테스트 기준

현재 Rust 쪽 테스트는 다음 3축으로 구성된다.

1. `api_smoke.rs`
2. `api_contract.rs`
3. `api_golden.rs`

관련 문서:

- [Golden/Snapshot 비교 전략](../testing/golden_snapshot_strategy.md)
- [Django 기준 Rust 이관 체크리스트](../django_to_rust_checklist.md)

---

## 11. 요약표

| 영역 | 상태 |
|------|------|
| Projects 조회 | 구현 |
| Projects 쓰기 | 구현 |
| Build Plans | 구현 |
| Executions | 구현 |
| Module Registry | 구현 |
| System Settings | 구현 |
| Jenkins Jobs | 구현 |
| Bamboo 연동 | 구현 |

---

## 12. 참고

- 기존 Django 라우터: `backend/apps/api/router.py`
- 기존 Django 라우트: `backend/apps/api/routers/`
- Rust 라우트: `backend-rs/src/api/routes/`
