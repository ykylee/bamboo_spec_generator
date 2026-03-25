# TODO

## 기준

- 작성일: 2026-03-25
- 기준 브랜치 상태: `codex/system-extension`
- 기준 판단:
  - `BuildUnit` 중심 백엔드 재구성 완료
  - 백엔드 테스트 `173 tests` 통과
  - 문서 기준 제품 방향은 Bamboo/Jenkins 공통 CI/CD 관제 시스템

## 최우선

### 1. Jenkins 백엔드 구현

- [ ] `backend/apps/buildmeta/services/jenkins.py` 신규 구현
- [ ] Jenkins 서버 설정 키 추가
  - 예: `jenkins.server.url`, `jenkins.username`, `jenkins.token`
- [ ] Jenkins 프로젝트/잡 등록 서비스 구현
- [ ] Jenkins 잡 상세 selector 구현
- [ ] Jenkins 실행 이력/큐/노드 상태 selector 구현
- [ ] Jenkins API router 추가
  - 프로젝트 등록/수정
  - 잡 상세/목록
  - 운영 현황 조회

### 2. UI 멀티 CI 전환

- [ ] 상단 `Bamboo 관리` / `Jenkins 관리` 모드 스위처 구현
- [ ] URL 기반 provider 모드 전환 반영
  - 예: `/ui/bamboo/...`, `/ui/jenkins/...` 또는 동등한 구조
- [ ] 공통 UI 카피를 CI 일반 표현으로 정리
- [ ] provider별 테마 적용
  - Bamboo: 밝은 파란색
  - Jenkins: 밝은 빨간색
- [ ] Jenkins 화면 추가
  - 프로젝트 목록/상세
  - 잡 상세
  - 시스템 운영 현황

### 3. Jenkins 운영 관제

- [ ] `JenkinsNodeSnapshot`, `JenkinsQueueItemSnapshot` 실제 수집 경로 구현
- [ ] Jenkins 노드/executor/queue 상태 API 구현
- [ ] UI 운영 현황 패널 구현
- [ ] Bamboo agent 관제와 Jenkins node 관제를 공통 레이아웃으로 정리

## 높음

### 4. API 계약 정리

- [ ] 외부 API 네이밍의 provider 중립화 여부 결정
  - 현재 `/api/v1/build-plans/...` 표현이 여전히 남아 있음
- [ ] `build-plans` 경로를 유지할지 `build-units`로 전환할지 결정
- [ ] 응답 필드의 Bamboo 전용 표현 축소
  - `planKey`, `buildId` 중심 응답과 공통 필드 병행 여부 결정
- [ ] Jenkins용 요청/응답 schema 추가

### 5. 테스트 구조 정리

- [ ] `backend/apps/buildmeta/tests_support.py` 제거 계획 수립
- [ ] 테스트도 최종 `Project/Repository/BuildUnit/...` 모델명을 직접 쓰도록 단계적 치환
- [ ] UI 테스트 fixture를 provider별 fixture로 분리
- [ ] Jenkins API/UI 테스트 추가

### 6. 마이그레이션 재정리

- [ ] 현재 `0012_buildunit_v2_models.py` 이후 정리 migration 추가 여부 결정
- [ ] 더 이상 쓰지 않는 구 테이블 제거 migration 작성 여부 결정
- [ ] `db_table` 명에 남아 있는 `_v2` suffix 유지 여부 결정
- [ ] 개발 DB 초기화 기준 문서 재정리

## 중간

### 7. 운영 기능 확장

- [ ] 사용자/권한 관리 구현
- [ ] 배포/릴리스 관리 구현
- [ ] 감사 이력 `AuditEvent` 활용 범위 확대
  - 프로젝트 수정
  - 수동 실행
  - publish
  - Jenkins 등록/수정

### 8. 실행/버전 모델 고도화

- [ ] provider별 실행 번호/외부 실행 키 정책 명확화
- [ ] Jenkins 실행 이력과 `BuildExecution` 연결 구현
- [ ] artifact/deployment entity 실제 적재 경로 구현

### 9. 문서/README 동기화

- [ ] README의 현재 상태를 실제 구현 수준에 맞게 추가 정리
  - Jenkins는 문서 기준 방향이지 구현 완료 아님을 더 명확히 표기
- [ ] API 문서에 신규 공통 모델/제약 추가
- [ ] 상세 설계 문서에 실제 구현 완료/미완료 상태 반영

## 낮음

### 10. 레거시 명칭 최종 청소

- [ ] 테스트 코드 내부에 남아 있는 `BuildPlan`, `ProjectBuild` 등 레거시 테스트 shim 명칭 제거
- [ ] historical migration을 제외한 저장소 전역 레거시 용어 재검색 후 정리
- [ ] selector/helper 내부의 `legacy` 표현 정리
  - 예: `_legacy_result_status`, `_serialize_legacy_build`

## 결정 필요

- [ ] 외부 API와 UI URL에서 `build-plan` 용어를 언제까지 유지할지
- [ ] `db_table`의 `_v2` suffix를 유지할지, 새 migration으로 정리할지
- [ ] detached placeholder 프로젝트 전략을 테스트 전용으로 유지할지
- [ ] Jenkins 1차 등록 단위를 `job`만으로 둘지, `folder + job`를 1급 모델로 올릴지

## 추천 다음 순서

1. Jenkins 백엔드 서비스/selector/API 추가
2. UI 상단 provider 스위치와 테마 분리
3. Jenkins 운영 현황 화면 구현
4. 테스트 shim 제거 및 최종 네이밍 정리
5. migration/db_table 정리 여부 결정
