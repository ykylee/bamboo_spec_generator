# Django 기준 Rust 이관 체크리스트

## 문서 개요

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-03-30 |
| 상태 | 작업 기준선 |
| 목적 | Django/Ninja 구현을 기준으로 Rust 백엔드 이관 범위와 완료 조건을 정리 |

---

## 1. 원칙

이 문서는 Rust 백엔드 구현의 기준선을 문서가 아니라 현재 Django 구현에 두기 위해 작성한다.

- 기능 기준선은 `backend/apps/api/`와 `backend/apps/buildmeta/`의 현재 동작이다.
- Rust 구현은 Django와 동일하거나 호환 가능한 API 계약을 먼저 맞춘다.
- React 전환은 Rust API가 최소 기능 호환 수준에 도달한 뒤 시작한다.
- 새로운 Rust API 경로를 도입하더라도, 전환 완료 전에는 Django 경로와의 호환 전략을 문서화해야 한다.
- Django에서 아직 부분 구현인 기능은 Rust에서도 동일하게 부분 구현으로 표시하되, 축소 구현을 더하지 않는다.

---

## 2. 현재 기준선

### 2.1 기준 구현

- API 기준: `backend/apps/api/router.py`
- 라우트 기준: `backend/apps/api/routers/`
- 도메인/비즈니스 로직 기준: `backend/apps/buildmeta/services/`, `backend/apps/buildmeta/selectors/`
- 데이터 모델 기준: `backend/apps/buildmeta/models/`
- 인증 기준: `apps.api.auth.GeneratorTokenAuth`

### 2.2 Rust 현재 상태

- 위치: `backend-rs/`
- 상태: 라우트/도메인/인프라 스캐폴딩 완료
- 한계: 다수 엔드포인트가 stub 또는 placeholder 응답
- 검증 상태: 현재 작업 환경에서 `cargo` 미설치로 빌드 미검증

---

## 3. API 이관 체크리스트

## 3.1 Projects

기준 Django 라우트: [backend/apps/api/routers/projects.py](../../backend/apps/api/routers/projects.py)

### 필수 엔드포인트

- [ ] `GET /api/v1/projects/`
- [ ] `POST /api/v1/projects/`
- [ ] `GET /api/v1/projects/{project_key}`
- [ ] `PUT /api/v1/projects/{project_key}`

### 완료 조건

- [ ] `ci_provider` 필터 동작이 Django와 동일하다.
- [ ] 존재하지 않는 프로젝트 조회/수정 시 404를 반환한다.
- [ ] 잘못된 입력 시 400과 오류 메시지를 반환한다.
- [ ] 응답 필드 이름과 구조가 Django와 호환된다.
- [x] Django 테스트에 대응되는 Rust API 계약 테스트가 있다.

### 메모

- Rust 스캐폴딩은 존재하지만 실제 DB 조회/저장 구현이 필요하다.
- `display_name` 중심의 단순 응답이 아니라 Django 상세 구조 전체를 맞춰야 한다.

## 3.2 Build Plans

기준 Django 라우트: [backend/apps/api/routers/build_plans.py](../../backend/apps/api/routers/build_plans.py)

### 필수 엔드포인트

- [ ] `GET /api/v1/build-plans/{plan_key}/active-definition`
- [ ] `GET /api/v1/build-plans/{plan_key}/prepare-context`
- [ ] `GET /api/v1/build-plans/{plan_key}/executions`

### 완료 조건

- [ ] `active-definition` 응답에 `definition`과 별도 `year`가 포함된다.
- [ ] `prepare-context` 응답의 `variables`와 현재 저장소/프로젝트 정보가 Django와 호환된다.
- [ ] 존재하지 않는 플랜에 대해 404를 반환한다.
- [x] Django 기준 빌드 정의/준비 컨텍스트 샘플로 계약 테스트를 작성한다.

### 메모

- 이 영역은 생성기 CLI와 직접 연결되므로 최우선 호환 대상이다.

## 3.3 Executions

기준 Django 라우트: [backend/apps/api/routers/executions.py](../../backend/apps/api/routers/executions.py)

### 필수 엔드포인트

- [ ] `POST /api/v1/build-plans/{plan_key}/executions/start`
- [ ] `POST /api/v1/build-executions/{execution_id}/finish`
- [ ] `POST /api/v1/build-executions/{execution_id}/static-analysis-results`

### 완료 조건

- [ ] 실행 시작 시 버전 계산 및 실행 ID 생성 로직이 Django와 호환된다.
- [ ] 실행 종료 시 상태, 요약, stage/job/task 정보가 저장된다.
- [ ] 정적 분석 결과 upsert 동작이 Django와 호환된다.
- [x] 동일 커밋/빌드번호 처리 규칙을 문서화하고 테스트한다.

### 메모

- Rust 쪽에는 아직 대응 라우트 자체가 없다.
- React 이전과 별개로 운영 적재 경로상 중요도가 높다.

## 3.4 Module Registry

기준 Django 라우트: [backend/apps/api/routers/module_registry.py](../../backend/apps/api/routers/module_registry.py)

### 필수 엔드포인트

- [x] `GET /api/v1/admin/modules/`
- [x] `GET /api/v1/admin/modules/load-status`
- [x] `POST /api/v1/admin/modules/uploads`
- [x] `POST /api/v1/admin/modules/reload`
- [x] `GET /api/v1/admin/modules/{asset_id}`
- [x] `POST /api/v1/admin/modules/{asset_id}/activate`
- [x] `POST /api/v1/admin/modules/{asset_id}/deactivate`

### 완료 조건

- [x] 멀티파트 업로드와 활성화 옵션을 지원한다.
- [x] 버전 상세/비교/최근 오류 조회 모델을 Rust에서도 제공한다.
- [x] Django 경로(`/api/v1/admin/modules/...`) 유지 여부를 결정하고 문서화한다.
- [x] 현재 발견된 활성 파일/확장자 처리 리스크를 반영한 테스트를 추가한다.

### 메모

- 현재 리팩토링 문서의 Rust 경로는 `/api/v1/modules/*`로 되어 있어 경로 비호환이 있다.
- 경로를 바꾸려면 생성기와 UI 소비자 영향 분석이 먼저 필요하다.

## 3.5 System Settings

기준 Django 라우트: [backend/apps/api/routers/system_settings.py](../../backend/apps/api/routers/system_settings.py)

### 필수 엔드포인트

- [x] `GET /api/v1/system-settings/coverity`
- [x] `PUT /api/v1/system-settings/coverity`
- [x] `GET /api/v1/system-settings/bamboo`
- [x] `PUT /api/v1/system-settings/bamboo`
- [x] `GET /api/v1/system-settings/jenkins`
- [x] `PUT /api/v1/system-settings/jenkins`
- [x] `GET /api/v1/system-settings/github`
- [x] `PUT /api/v1/system-settings/github`
- [x] `GET /api/v1/system-settings/bitbucket`
- [x] `PUT /api/v1/system-settings/bitbucket`
- [x] `GET /api/v1/system-settings/gitea`
- [x] `PUT /api/v1/system-settings/gitea`
- [x] `POST /api/v1/system-settings/specs-drafts/initialize`
- [x] `POST /api/v1/system-settings/specs-drafts/initialize/{planKey}`

### 완료 조건

- [x] Coverity 설정 필드와 Bamboo 설정 필드를 분리해 관리한다.
- [x] Bamboo/GitHub/Bitbucket/Gitea는 `serverUrl + token` 구조로 저장한다.
- [x] 저장 시 `repositoryLinkageMode` 보정 규칙이 동일하다.
- [x] Specs draft 초기화 응답 구조가 Django와 호환된다.
- [x] Django smoke fixture 기준 계약 테스트가 있다.

### 메모

- 현재 리팩토링 문서의 Rust 설정 API는 `/api/v1/settings/*`로 되어 있어 경로 비호환이 있다.

## 3.6 Jenkins Jobs

기준 Django 라우트: [backend/apps/api/routers/jenkins_jobs.py](../../backend/apps/api/routers/jenkins_jobs.py)

### 필수 엔드포인트

- [x] `GET /api/v1/jenkins-jobs/`
- [x] `GET /api/v1/jenkins-jobs/{job_path}/status`
- [x] `GET /api/v1/jenkins-jobs/{job_path}/details`
- [x] `GET /api/v1/jenkins-jobs/{job_path}/executions`
- [x] `POST /api/v1/jenkins-jobs/{job_path}/trigger`
- [x] `POST /api/v1/jenkins-jobs/{job_path}/configure`
- [x] `GET /api/v1/jenkins-jobs/{job_path}/builds/{build_number}`
- [x] `GET /api/v1/jenkins-jobs/system-status`

### 완료 조건

- [ ] Jenkins 연결 오류를 Django와 같은 수준의 400/404로 매핑한다.
- [x] job path에 `/`가 포함되는 경로 파라미터를 그대로 처리한다.
- [x] Jenkins 운영 상태 조회와 빌드 상세 조회 계약 테스트를 작성한다.

### 메모

- Rust 스캐폴딩에는 이 영역이 없다.
- Django 기준으로도 외부 시스템 의존도가 높으므로 테스트 전략을 별도 정의해야 한다.

---

## 4. 공통 비기능 체크리스트

## 4.1 인증과 보안

- [x] Django의 `GeneratorTokenAuth`와 동일한 인증 요구사항을 정의한다.
- [x] 인증 실패 응답 코드와 메시지를 호환시킨다.
- [x] 민감 설정값 응답 포함 범위를 재검토한다.

## 4.2 데이터 호환성

- [ ] PostgreSQL 스키마를 실제로 재사용할지 확정한다.
- [ ] Django 마이그레이션 스키마와 Rust SQL 쿼리의 테이블/컬럼명을 대조한다.
- [ ] UUID, JSON, datetime 직렬화 형식을 Django와 맞춘다.

## 4.3 에러 처리

- [x] 400/404/500 매핑 정책을 공통 응답 헬퍼로 정리한다.
- [x] Django의 `ValueError -> 400`, `not found -> 404` 패턴을 Rust에서도 유지한다.

## 4.4 테스트

- [x] Django API 테스트를 기준으로 Rust 계약 테스트 목록을 만든다.
- [x] 동일 픽스처로 Django 응답과 Rust 응답을 비교하는 스냅샷 또는 golden 테스트를 설계한다.
- [x] Rust 단위 테스트와 통합 테스트 실행 명령을 문서화한다.

---

## 5. 권장 구현 순서

1. Projects API를 Django 응답과 호환되게 구현
2. Build Plans API를 구현하고 생성기 경로 검증
3. Executions API를 구현해 적재 경로 완성
4. System Settings API를 이관
5. Module Registry API를 경로 정책 포함해 이관
6. Jenkins Jobs API를 이관
7. 공통 인증/에러 처리/로깅 정리
8. Rust API 계약 테스트 추가
9. 그 뒤 React 프런트엔드 착수

---

## 6. React 착수 전 진입 조건

아래 조건을 만족하기 전에는 React 구현을 시작하지 않는다.

- [ ] Projects API가 Rust에서 실데이터로 동작한다.
- [ ] Build Plans API가 생성기 호출 경로에서 검증됐다.
- [ ] Executions API가 최소 적재 흐름을 제공한다.
- [ ] Settings API가 실운영 설정 저장을 지원한다.
- [ ] 인증과 오류 응답 계약이 고정됐다.
- [ ] Rust 빌드/테스트 명령이 CI 또는 로컬 표준 명령으로 정리됐다.

---

## 7. 오픈 이슈

- 모듈/설정 API 경로를 Django와 동일하게 유지할지, Rust 새 경로로 바꿀지 결정 필요
- Django 템플릿 UI를 언제까지 유지할지 결정 필요
- React가 Django를 직접 호출할지, Rust만 호출할지 결정 필요
- Django와 Rust를 병행 운영하는 과도기 배포 구조가 필요할 수 있음
