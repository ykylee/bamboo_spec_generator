# TODO

## 현재 상태

- 브랜치: `codex/bamboo-integration`
- 최근 작업으로 웹에서 Bamboo publish, 실제 Bamboo plan 상태 조회, 실제 Bamboo plan 상세 페이지, Bamboo 수동 실행, `buildKey` 포함 실행 피드백 task까지 반영된 상태다.
- 운영 설정 페이지는 시스템 설정 페이지로 사용되며, Coverity 설정은 그 하위 항목으로 관리한다.
- 문서 갱신:
  - `docs/requirements/issues/STORY-28-build-plan-dashboard-and-build-info-management.md`
  - `docs/designs/detailed_designs/bamboo_publish_and_runtime_feedback.md`

## 이번 스레드에서 정리된 완료 항목

1. 웹에서 Bamboo publish 실행
- 완료
- 빌드 상세에서 Bamboo Specs publish 버튼 제공
- 서버에서 임시 Specs 프로젝트 생성 후 `mvn -q exec:java`로 publish 수행

2. publish 후 Bamboo 상태 표시
- 완료
- 빌드 상세에서 등록 여부, enabled/building, 최신 결과, 최신 빌드 번호 표시

3. 실제 Bamboo plan 구성 조회 페이지
- 완료
- `/projects/{jira}/builds/{planKey}/bamboo/` 페이지 추가
- stage/job, branch, variable 일부 표시

4. Bamboo 실행 결과 시스템 피드백 task
- 완료
- 생성 task script가 실행 시작 시 `buildKey` 포함
- 실행 종료 및 정적 분석 결과를 기존 execution API로 피드백

5. 웹에서 Bamboo plan 수동 실행
- 완료
- 빌드 상세에서 수동 실행 버튼 제공
- Bamboo queue API 호출 결과 메시지 표시

## 다음 스레드에서 이어갈 작업

1. Bamboo publish 이력 영속화
- 1차 완료
- `BambooPublishExecution` 모델로 publish 성공/실패, 시각, return code, 메시지, output, trigger source를 저장한다.
- 빌드 상세 화면에서 최근 publish 이력을 조회할 수 있다.
- 실행자 식별과 감사 로그 연동은 아직 남아 있다.

2. Bamboo 수동 실행 파라미터 확장
- 1차 완료
- 수동 실행 폼에서 `stage`, `execute all stages`, `custom revision`, `variables` 입력을 지원한다.
- 변수는 `key=value` 형식으로 입력해 Bamboo queue query parameter로 전달한다.
- 별도 branch selector UI와 buildKey 단위 실행 제어는 아직 남아 있다.

3. Bamboo REST 응답 호환성 보강
- 신규
- Bamboo 버전별 plan/result 응답 차이를 더 안전하게 흡수한다.
- stage/job/branch/action/variable 누락 시 fallback 정책을 정리한다.

4. Bamboo publish/실행 실패 UX 개선
- 1차 완료
- publish/run 결과를 요약 메시지와 세부 정보로 분리해 화면에 노출한다.
- publish 로그와 queue 요청 파라미터를 operator 확인용 detail 영역에서 볼 수 있다.
- 이후에는 실패 유형별 분류, 하이라이트, 민감정보 마스킹이 더 필요하다.

5. Bamboo end-to-end 실환경 검증
- 신규
- 실제 Bamboo 서버 대상으로 publish, 상태 조회, 수동 실행, execution feedback까지 재검증한다.
- linked / create_if_missing 두 모드를 모두 확인한다.

6. 권한 및 감사 로그
- 신규
- publish와 수동 실행을 누가 수행했는지 기록하는 정책이 필요하다.
- 운영 권한 범위를 어디까지 열지 정리한다.

7. buildKey 기반 결과 집계 화면 고도화
- 신규
- 현재는 execution API와 기본 연결만 되어 있다.
- buildKey별 결과 집계, plan 수준 종합 상태, 정적 분석 요약 화면을 확장한다.

8. 단위테스트 보강과 커버리지 개선
- 신규
- 현재 전체 Python 커버리지는 약 `62%` 수준이며, 생성기 코어보다 Django 운영 계층의 미검증 조합 로직이 병목이다.
- 우선순위는 `backend/apps/buildmeta/selectors/definitions.py`, `backend/apps/ui/views.py`, `backend/apps/buildmeta/services/bamboo.py`, `backend/apps/buildmeta/services/projects.py`, `backend/apps/buildmeta/services/specs_drafts.py` 순으로 둔다.
- 특히 preview/export draft 조합, view POST 분기와 오류 복원, Bamboo API mocking, 프로젝트 등록/수정 검증 조합, specs draft 보정 로직을 추가 테스트 대상으로 잡는다.
- 목표는 selector/service/view 계층을 우선 보강해 커버리지를 `70%+`로 끌어올리는 것이다.

## 남은 이슈

1. publish 결과 저장 범위
- 현재는 output 전체 문자열을 저장한다.
- 장기적으로 원문 보존, 길이 제한, 민감정보 마스킹 정책을 정해야 한다.

2. Bamboo 수동 실행 입력 범위
- 현재는 `customRevision`과 임의 변수 override를 지원한다.
- branch selector를 별도 필드로 분리할지, `customRevision` 입력 하나로 유지할지 결정 필요

3. Bamboo 실제 응답 스키마 차이
- 현재 구현은 최신 REST 응답을 가정한 최소 파싱이다.
- 운영 Bamboo 버전에서 expand 필드가 일부 다를 수 있다.

4. 권한/감사 로그 정책
- 운영 UI에서 publish와 run 액션을 누구에게 허용할지 아직 미정이다.

5. 커버리지 병목 구간
- `backend/apps/ui/views.py`, `backend/apps/buildmeta/selectors/definitions.py`, `backend/apps/buildmeta/services/bamboo.py` 쪽 커버리지가 특히 낮다.
- 기능 구현 부족보다는 테스트 부족이 원인이라, 신규 기능보다 회귀 테스트 확대를 우선하는 편이 효율적이다.

## 참고 파일

- `backend/apps/buildmeta/services/bamboo.py`
- `backend/apps/buildmeta/services/system_settings.py`
- `backend/apps/ui/templates/ui/build_detail.html`
- `backend/apps/ui/templates/ui/bamboo_plan_detail.html`
- `backend/apps/ui/templates/ui/coverity_settings.html`
- `backend/apps/ui/views.py`
- `scripts/plan_tasks/fragments/py/execution_support.py`
- `src/bamboo_spec_generator/script_renderer.py`
- `src/bamboo_spec_generator/parser.py`
- `backend/apps/ui/tests.py`
- `backend/apps/buildmeta/tests.py`
- `tests/test_cli.py`
- `tests/test_api_client.py`
- `tests/test_coverity.py`
- `tests/test_parser_validator.py`
- `tests/test_script_renderer.py`
- `tests/test_generator.py`
