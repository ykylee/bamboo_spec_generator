# Design: Bamboo Publish, Live Plan 조회, 수동 실행, 실행 피드백

## 요약

운영 콘솔의 빌드 상세 화면에 Bamboo publish, 실제 Bamboo plan 상태 조회, 실제 plan 구성 조회, 수동 실행 액션을 추가한다. 또한 생성되는 Bamboo task 스크립트는 `buildKey`를 포함한 실행 시작/종료 피드백을 시스템으로 다시 전송하도록 보강한다.

## 배경

- 현재 시스템은 등록 정보 기반의 예상 Bamboo Preview와 Specs export 초안은 제공하지만, 실제 Bamboo 서버 상태와 직접 연결된 운영 액션은 없다.
- 생성된 Python task 스크립트에는 실행 시작/종료 피드백 로직이 일부 포함돼 있으나 `buildKey` 전달이 빠져 있어 다건 `BuildInfo` 환경에서 실행 결과를 정확히 구분하기 어렵다.
- 운영자는 Preview와 실제 Bamboo 구성 차이를 같은 화면 흐름 안에서 확인하고, publish 및 수동 실행까지 웹에서 마무리하길 원한다.

## 목표

- 웹에서 단건 Bamboo Specs publish 실행
- 실제 Bamboo plan 존재 여부와 최신 상태 표시
- 실제 Bamboo plan 구조를 조회하는 별도 페이지 제공
- Bamboo 수동 실행 버튼 제공
- 생성 스크립트의 실행 피드백에 `buildKey` 포함

## 비목표

- Bamboo 권한 모델/감사 로그 설계
- Bamboo 배포 이력의 장기 영속화/대시보드화
- Bamboo plan 수정 기능 전체를 REST로 역편집하는 기능

## 설계안

### 1. Bamboo 연결 설정

- `SystemSetting`에 Bamboo 서버 URL 키를 추가한다.
- Bamboo 인증 토큰은 DB가 아니라 서버 환경 변수 `BAMBOO_SERVER_TOKEN`으로 읽는다.
- UI 설정 화면에서는 Bamboo 서버 URL과 토큰 감지 여부만 보여준다.

### 2. Bamboo 서비스 계층

- `apps.buildmeta.services.bamboo` 모듈을 추가한다.
- 책임:
  - Bamboo REST GET/POST 래핑
  - plan 존재 여부/상태 조회
  - plan 상세 조회
  - 수동 queue 실행
  - publish용 임시 Specs 프로젝트 생성 및 Maven publish 실행
- publish는 다음 순서로 처리한다.
  1. `plan_key` 기준 등록 정보와 prepare context 조회
  2. 임시 디렉터리에 Specs 프로젝트 생성
  3. 환경변수 `BAMBOO_URL`, `BAMBOO_TOKEN_FILE`을 주입해 `mvn -q exec:java` 실행
  4. 결과 메시지를 UI에 반환

### 3. Bamboo 상태 조회

- 빌드 상세 진입 시 live status selector를 호출한다.
- plan 식별자는 현재 생성 규칙과 동일하게 `project.bitbucket_project_key + plan.plan_key`를 조합한다.
- 표시 항목:
  - plan 존재 여부
  - enabled 여부
  - building 여부
  - latest result state / build number
  - Bamboo plan 링크

### 4. 실제 Bamboo plan 구성 페이지

- 경로: `/projects/{jira}/builds/{planKey}/bamboo/`
- 표시 항목:
  - plan 기본 정보
  - stage/job 구조
  - branch 목록
  - variable context 및 actions 중 조회 가능한 필드
- Bamboo API 확장값이 일부 비어 있으면 빈 섹션 대신 "제공되지 않음" 상태로 표시한다.

### 5. 수동 실행

- 빌드 상세 화면에서 `Run Bamboo Plan` 액션을 제공한다.
- POST 시 Bamboo queue REST를 호출한다.
- 응답에서 queue/result 식별자를 추출해 사용자에게 보여준다.

### 6. 실행 피드백 task 보강

- `execution_support.py`에서 `BUILD_KEY` 상수를 렌더링한다.
- `start_execution_if_configured()` 호출 시 `buildKey`를 함께 전송한다.
- 각 task는 기존처럼 실패 시 즉시 `finish_execution_if_configured()`를 호출하고, 후속 trigger task가 성공 시 최종 성공을 기록한다.
- 이 변경으로 같은 plan 안의 다건 `BuildInfo` 실행이 정확히 분리된다.

## 대안

- Bamboo publish를 REST만으로 처리
  - 장점: Maven 의존성 제거
  - 단점: 현재 생성 결과가 Java Specs publish 흐름을 전제로 하고 있어 구현 복잡도가 더 높다.
- publish/queue/status를 비동기 작업 큐로 전환
  - 장점: 응답 지연 감소
  - 단점: 현재 코드베이스에는 작업 큐 기반이 없어 범위를 과도하게 키운다.

## 영향 범위

- `backend/apps/buildmeta/models/core.py`
  - Bamboo URL 설정 키 추가
- `backend/apps/buildmeta/services/system_settings.py`
  - Bamboo 설정 조회 추가
- `backend/apps/buildmeta/services/bamboo.py`
  - 신규 Bamboo 연동 서비스
- `backend/apps/ui/views.py`
  - publish/queue 액션 처리 및 live status 주입
- `backend/apps/ui/templates/ui/build_detail.html`
  - Bamboo 운영 패널 추가
- `backend/apps/ui/templates/ui/bamboo_plan_detail.html`
  - 신규 실제 plan 조회 페이지
- `backend/apps/ui/urls.py`
  - 신규 라우트 추가
- `scripts/plan_tasks/fragments/py/execution_support.py`
  - `buildKey` 피드백 추가
- `src/bamboo_spec_generator/script_renderer.py`
  - `BUILD_KEY` placeholder 렌더링

## 수용 기준

- Bamboo URL과 서버 토큰이 준비된 경우 빌드 상세에서 publish 버튼이 동작한다.
- publish 후 Bamboo에 plan이 존재하면 상세 화면에 live status가 표시된다.
- 실제 Bamboo plan 조회 페이지에서 stage/job 구조를 확인할 수 있다.
- 수동 실행 버튼으로 Bamboo queue 요청을 보낼 수 있다.
- 생성 스크립트가 실행 시작 시 `buildKey`를 포함한 payload를 전송한다.

## 오픈 이슈

- publish 결과를 DB에 저장하지 않고 live 조회만으로 충분한지 운영 검토 필요
- Bamboo REST 응답 스키마 버전 차이를 어디까지 호환할지 검토 필요
- 수동 실행 시 branch/변수 override 요구가 필요한지 추후 검토 필요
