# 테스트 실행 보고서

## 문서 메타데이터

- 문서 일자: 2026-03-24
- 문서 유형: Test Execution Report
- 대상 프로젝트: `bamboo_spec_generator`
- 관련 문서:
  - [README](../../README.md)
  - [E2E 테스트 케이스 세트](./e2e_test_case_set.md)
  - [UI 테스트 케이스 세트](./ui_test_case_set.md)
  - [API 테스트 케이스 세트](./api_test_case_set.md)

## 요약

이번 작업에서는 현재 구현 범위에 맞게 README와 테스트 문서를 동기화했고, 문서 기반 수동 E2E 테스트 케이스를 정리했으며, 생성기/운영 API/운영 서비스 회귀를 위한 단위테스트와 Playwright 기반 UI E2E를 실행했다. 자동 실행은 생성기 테스트, Django 백엔드 테스트, Playwright UI E2E에 대해 수행했고, 전체 Python 커버리지는 `62%`로 측정되었다.

## 반영 내용

- README에 현재 구현 범위, 운영 UI/API 엔드포인트, 테스트/커버리지 실행 방법을 반영했다.
- 문서 기반 수동 E2E 테스트 케이스를 다음 문서로 정리했다.
  - [E2E 테스트 케이스 세트](./e2e_test_case_set.md)
  - [UI 테스트 케이스 세트](./ui_test_case_set.md)
  - [API 테스트 케이스 세트](./api_test_case_set.md)
- 단위테스트는 다음 파일 기준으로 보강했다.
  - [tests/test_cli.py](../../tests/test_cli.py)
  - [tests/test_api_client.py](../../tests/test_api_client.py)
  - [backend/apps/buildmeta/tests.py](../../backend/apps/buildmeta/tests.py)
  - [tests/test_coverity.py](../../tests/test_coverity.py)
  - [tests/test_parser_validator.py](../../tests/test_parser_validator.py)
  - [tests/test_script_renderer.py](../../tests/test_script_renderer.py)

## 단위테스트 추가 범위

- `--db-check` 분기에서 `PostgresConfig.from_env()`와 `check_connection()` 호출 경로 검증
- `--db-init-schema` 분기에서 `apply_schema()` 호출 경로 검증
- `--api-plan-key` 성공 경로에서 API 클라이언트, prepare context, `write_specs_project()` 호출 검증
- `--api-plan-key` 실패 경로에서 `OperationsApiError` 처리 검증
- 입력 파일 없음과 `ValidationError` 발생 시 `main()`이 `1`을 반환하는지 검증
- API 클라이언트의 HTTP/URL 오류 감싸기, 비정상 응답 처리 검증
- 정의 import 정렬/해시, 준비 컨텍스트 fallback, repository linkage mode 정규화 같은 서비스/selector 회귀 검증
- Coverity YAML 렌더링, parser/validator 기본 규칙, script renderer placeholder 오류 검증

## 실행 명령과 결과

1. `python3 -m pip install --break-system-packages coverage`
   - 결과: 성공
   - 비고: 시스템 Python의 PEP 668 제한 때문에 `--break-system-packages` 옵션을 사용했다.
2. `PYTHONPATH=. python3 -m coverage run -m unittest discover -s tests`
   - 결과: 성공
   - 실행 테스트 수: `44`
3. `cd backend && PYTHONPATH=.. python3 -m coverage run --append manage.py test --settings=config.settings.test`
   - 결과: 성공
   - 실행 테스트 수: `117`
4. `python3 -m coverage report -m`
   - 결과: 성공
   - 전체 커버리지: `62%`
5. `PYTHONPATH=. python3 -m unittest discover -s tests/playwright -p 'test_*.py'`
   - 결과: 성공
   - 실행 테스트 수: `10`
   - 비고: build detail preview/task inspector DOM 구조에 맞게 Playwright 기대치를 정렬한 뒤 재실행해 통과했다.

자동 실행된 테스트 수 합계는 `171`건이다.

## 커버리지 요약

### 높은 커버리지 영역

- 생성기 입력/출력 계층
  - [tests/test_generator.py](../../tests/test_generator.py)
  - [tests/test_api_client.py](../../tests/test_api_client.py)
  - [tests/test_parser_validator.py](../../tests/test_parser_validator.py)
  - [tests/test_postgres.py](../../tests/test_postgres.py)
- 주요 생성기 모듈
  - `src/bamboo_spec_generator/generator.py`: `99%`
  - `src/bamboo_spec_generator/writer.py`: `91%`
  - `src/bamboo_spec_generator/api_client.py`: `98%`
  - `src/bamboo_spec_generator/postgres.py`: `92%`

### 상대적으로 낮은 커버리지 영역

- Django selector/service/view 계층
  - `backend/apps/buildmeta/selectors/definitions.py`: `16%`
  - `backend/apps/buildmeta/services/bamboo.py`: `19%`
  - `backend/apps/buildmeta/services/projects.py`: `13%`
  - `backend/apps/ui/views.py`: `11%`

이 영역은 UI/외부 Bamboo 연동/조합 로직이 많아 회귀 위험이 높으므로 다음 테스트 보강 우선순위로 본다.

## 미실행 항목과 한계

- 이번 턴의 E2E 산출물에는 수동 검증용 테스트 케이스 문서와 Playwright 자동 UI E2E가 함께 포함된다.
- Bamboo 실서버 연동, 배포/릴리스 관리, 사용자/권한 관리 범위는 여전히 자동 검증 대상에서 제외되어 있다.

## 다음 권장 작업

1. `backend/apps/buildmeta/selectors/definitions.py`의 preview/export draft 조합 로직 테스트를 추가한다.
2. `backend/apps/buildmeta/services/bamboo.py`에 대해 네트워크 mocking 기반 단위테스트를 늘린다.
3. `backend/apps/ui/views.py`의 폼 제출 분기와 오류 복원 흐름을 response 테스트로 더 촘촘히 보강한다.
4. 문서로 정리한 [API 테스트 케이스 세트](./api_test_case_set.md) 중 핵심 시나리오를 점진적으로 자동화한다.
