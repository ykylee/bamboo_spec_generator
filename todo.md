# TODO

## 현재 상태

- 브랜치: `codex/register-requirement-concept-2026-03-19`
- 최근 작업은 빌드 플랜 상세의 Bamboo preview, build info 확장, stage 구조 정리, 문서 갱신까지 반영된 상태다.
- `Prepare`는 plan 공통 단계, `Build`와 `Analysis`는 build info 단위 반복, `Post Process`는 공통 후속 단계로 정리되어 있다.

## 다음 스레드에서 이어갈 작업

1. `Specs Export 초안` 정리
- 중간 산출물 성격의 JSON 초안은 UI에서 제거한다.
- 환경에 따라 달라지는 실제 실행 파일만 노출한다.
- 후보:
  - `coverity.yaml`
  - build script (`run_build.py` 등)
  - 필요 시 후속 처리용 스크립트

2. `coverity.yaml` 생성 로직 재설계
- Coverity 공식 가이드를 다시 확인한다.
- `coverity scan` 중심으로 commit까지 가능한 형태를 우선 검토한다.
- 가능한 경우 전체 checker를 검사하는 옵션을 반영한다.
- 현재 생성 위치:
  - `src/bamboo_spec_generator/generator.py`
  - `src/bamboo_spec_generator/script_renderer.py`

3. Build/Analysis preview와 export 초안 정합성 점검
- preview stage/task 구조와 export draft가 같은 실행 모델을 설명하는지 다시 맞춘다.
- `Prepare`가 build별로 반복되지 않는지 다시 확인한다.
- `Analysis`가 `Build` 산출물을 받지 않고 checkout부터 다시 시작하는 구성이 export 초안에도 반영되는지 확인한다.

4. 언어별 no-build 예외 재확인
- 현재 기준은 `python`만 no-build 예외다.
- `javascript`, `typescript`, `node.js`는 build 있는 언어로 유지한다.
- 이 판단이 preview, validator, UI 설명에 모두 일치하는지 확인한다.

5. 테스트
- 변경 후 순차 실행:
  - `python3 backend/manage.py test apps.buildmeta.tests`
  - `python3 backend/manage.py test apps.ui.tests`
  - `python3 -m unittest tests.playwright.test_ui_e2e`

6. 서버 재기동
- 검증 후 `python3 backend/manage.py runserver 0.0.0.0:8030 --noreload`
- Tailscale 주소로 실제 화면 확인

## 참고 파일

- `backend/apps/buildmeta/selectors/definitions.py`
- `backend/apps/ui/templates/ui/build_detail.html`
- `backend/apps/ui/views.py`
- `src/bamboo_spec_generator/generator.py`
- `src/bamboo_spec_generator/script_renderer.py`
- `src/bamboo_spec_generator/validator.py`
- `backend/apps/buildmeta/tests.py`
- `backend/apps/ui/tests.py`
- `tests/playwright/test_ui_e2e.py`
