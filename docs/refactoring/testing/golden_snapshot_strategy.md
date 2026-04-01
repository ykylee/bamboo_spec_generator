# Golden/Snapshot 비교 전략

## 문서 개요

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-03-31 |
| 상태 | 작업 기준선 |
| 목적 | Django 기준 응답을 Rust 응답과 장기적으로 비교하기 위한 golden/snapshot 전략 정의 |

---

## 1. 목표

Rust 계약 테스트는 현재 Django smoke fixture를 기준으로 핵심 필드를 검증하고 있다.  
다음 단계에서는 이 계약을 "필드 일부 확인"에서 "응답 전체 구조 고정"으로 확장해야 한다.

이 문서는 그 기준을 정리한다.

## 2. 범위

우선 golden 비교는 아래 조건을 만족하는 엔드포인트부터 적용한다.

- 응답이 비교적 안정적이다.
- UUID, timestamp, 외부 시스템 상태처럼 매 실행마다 바뀌는 값이 적다.
- Django smoke fixture로 동일 데이터를 쉽게 만들 수 있다.

초기 적용 대상:

1. `GET /api/v1/projects/{project_key}`
2. `GET /api/v1/build-plans/{plan_key}/prepare-context`
3. `GET /api/v1/system-settings/coverity`

후속 적용 대상:

1. `GET /api/v1/build-plans/{plan_key}/active-definition`
2. `GET /api/v1/build-plans/{plan_key}/executions`
3. `GET /api/v1/jenkins-jobs/{job_path}/status`
4. `GET /api/v1/jenkins-jobs/{job_path}/details`

## 3. 비교 원칙

- fixture는 가능하면 Django `ApiSmokeTest`와 동일한 의미를 가진다.
- golden 파일은 실제 Rust 응답 JSON을 저장한다.
- object key 순서는 의미가 없으므로 `serde_json::Value` 비교를 사용한다.
- 동적 값이 있는 엔드포인트는 바로 snapshot으로 고정하지 않는다.
- 동적 값이 불가피하면 placeholder 치환 또는 normalize helper를 먼저 정의한다.

## 4. 저장 위치

- 테스트 코드: `backend-rs/tests/api_golden.rs`
- golden JSON: `backend-rs/tests/golden/*.json`

현재 등록된 golden 파일:

1. `project_detail_sample.json`
2. `prepare_context_sample.json`
3. `coverity_settings.json`

## 5. 갱신 절차

1. fixture를 고정한다.
2. Rust API 응답을 확인한다.
3. 의도된 변경이면 golden JSON을 갱신한다.
4. 의도되지 않은 변경이면 구현을 수정한다.
5. `cargo test --test api_golden`과 `cargo test`를 순차 실행한다.

## 6. 주의점

- Jenkins/Bamboo 실연동 응답은 외부 상태 변화가 커서 즉시 golden 대상에 넣지 않는다.
- 민감한 값은 golden 파일에 저장하지 않는다.
- 현재는 auto-update 스크립트를 두지 않는다.
  명시적으로 JSON 파일을 검토하고 수정하는 방식을 유지한다.

## 7. 다음 확장

다음 단계에서는 아래 둘 중 하나로 확장한다.

1. `active-definition`에 대한 normalize helper 추가
2. Django 응답 캡처본과 Rust 응답을 나란히 비교하는 dual snapshot 도입
