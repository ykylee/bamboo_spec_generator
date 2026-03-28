# OpenCode 분석 문서 색인

## 📁 문서 위치

```
docs/opencode_summary/
├── README.md          # 종합 분석 요약 (본 문서)
└── INDEX.md           # 문서 색인 (현재 파일)
```

---

## 📚 주요 문서 참조

### 요구사항 (Requirements)

| 문서 | 경로 | 설명 |
|------|------|------|
| CRS | `../requirements/CRS.md` | 고객 요구사항 명세 (전체 요구사항) |
| SRS | `../requirements/SRS.md` | 시스템 요구사항 명세 (기능 단위) |
| BREAKDOWN | `../requirements/issues/BREAKDOWN.md` | Epic/Story 분해 (Jira 단위) |
| 인프라 요구사항 | `../requirements/infrastructure_settings_requirements.md` | 인프라 설정 요구사항 |

### 설계 (Designs)

| 문서 | 경로 | 설명 |
|------|------|------|
| SAD | `../designs/SAD.md` | 소프트웨어 아키텍처 설계 |
| Design | `../designs/Design.md` | 상세 설계 (입력, 저장소, 스크립트, DB, API, UI) |
| 저장소 연결 | `../designs/repository_connection_support.md` | 저장소 연결 지원 방식 |

### 상세 설계 (Detailed Designs)

| 문서 | 경로 |
|------|------|
| 프로젝트 등록 및 Specs 생성 준비도 | `../designs/detailed_designs/project_registration_and_generation_readiness.md` |
| 다중 CI 콘솔 모드 전환 | `../designs/detailed_designs/multi_ci_console_and_provider_model.md` |
| 모듈형 빌드 구성 | `../designs/detailed_designs/modular_build_composition_and_tool_specific_tasks.md` |
| 모듈 레지스트리 백엔드 | `../designs/detailed_designs/module_registry_backend_and_api.md` |
| BuildUnit 중심 모델 초안 | `../designs/detailed_designs/buildunit_backend_model_draft.md` |
| BuildUnit 중심 ERD | `../designs/detailed_designs/buildunit_backend_model_erd.md` |
| 빌드 플랜/빌드 정보 관리 | `../designs/detailed_designs/build_plan_build_info_management.md` |
| 다중 CI 콘솔 결정사항 | `../designs/detailed_designs/multi_ci_console_decisions.md` |
| 모듈형 빌드 결정사항 | `../designs/detailed_designs/modular_build_composition_decisions.md` |

### 테스트 (Tests)

| 문서 | 경로 |
|------|------|
| E2E 테스트 케이스 | `../tests/e2e_test_case_set.md` |
| UI 테스트 케이스 | `../tests/ui_test_case_set.md` |
| API 테스트 케이스 | `../tests/api_test_case_set.md` |
| 테스트 실행 보고서 | `../tests/test_execution_report_2026-03-24.md` |

---

## 🎯 빠른 참조

### 현재 구현 상태 요약

```
✅ 완료:     EPIC-01 (대부분), STORY-13~22 (부분)
⚠️ 부분:    Bamboo 연동, 버전 관리, 프로젝트 관리
❌ 미구현:  사용자 권한, Jenkins 통합, 배포/릴리스
```

### 다음 권장 작업

1. **단기**: STORY-09 (브랜치별 트리거), Bamboo 연동 완성
2. **중기**: 프로젝트 관리 고도화, API 표준화
3. **장기**: Jenkins 통합, 다중 CI 콘솔

---

## 📊 프로젝트 메트릭스

| 항목 | 값 |
|------|-----|
| 총 Story 수 | 34개 |
| 완료 | ~15개 |
| 부분 구현 | ~10개 |
| 미구현 | ~9개 |
| 총 문서 수 | 60개+ (md 파일) |

---

*최종 업데이트: 2026-03-28*
