# UI 테스트 케이스 세트

## 문서 메타데이터

- 문서 일자: 2026-03-24
- 문서 유형: Manual UI Test Case Set
- 대상 범위: 프로젝트 목록, 프로젝트 등록, 프로젝트 상세, 저장소 상세, 빌드 상세, BuildInfo 상세, Bamboo 상세, 운영 설정
- 관련 요구사항: [../requirements/SRS.md](../requirements/SRS.md)
- 관련 설계: [../designs/Design.md](../designs/Design.md), [../designs/SAD.md](../designs/SAD.md)
- 관련 스토리: [../requirements/issues/STORY-21-project-registration.md](../requirements/issues/STORY-21-project-registration.md), [../requirements/issues/STORY-22-project-read-update.md](../requirements/issues/STORY-22-project-read-update.md)

## 요약

이 문서는 현재 구현된 Django/Ninja 운영 UI를 기준으로 한 수동 E2E 테스트 케이스 세트다. 현재 화면 단위로 확인 가능한 조회, 등록, 수정, 설정, Bamboo 미리보기 흐름을 기준으로 정리했으며, 배포/릴리스/권한 관리처럼 아직 UI가 없는 범위는 제외한다.

## 범위

### 포함

- 프로젝트 목록 KPI, 검색, 상태 필터, 페이지네이션
- 프로젝트 등록 패널의 접힘/펼침, 입력 후보 제안, 다중 저장소/다중 빌드 등록
- 프로젝트 상세 조회, 수정, 저장소 상세, 빌드 상세
- BuildInfo 목록/상세, 빌드 플랜 메타데이터 수정, Specs draft 초기화
- Bamboo plan 상태/상세 조회, publish/run 작업, publish 이력
- Coverity/Bamboo 운영 설정 화면

### 제외

- API 단독 검증
- 사용자 권한/인증 관리
- 배포/릴리스 관리
- Bamboo 에이전트/큐 현황 통합 관제
- 브라우저별 스타일 차이, 반응형 세부 레이아웃

## 테스트 데이터 준비 가이드

- 프로젝트는 12건 이상 준비해 페이지네이션을 검증한다.
- 다음 유형이 최소 1건씩 포함되도록 준비한다.
- 생성 준비 완료 프로젝트
- 대표 저장소 미지정 또는 메타데이터 불일치 프로젝트
- 활성 정의 없는 빌드를 가진 프로젝트
- Coverity 정보가 일부 비어 있는 프로젝트
- 최신 빌드 실패 이력이 있는 프로젝트
- Bamboo publish 성공 이력이 있는 프로젝트

## 추적 기준

- FR-12: 프로젝트/저장소 메타데이터 조회
- FR-16: 프로젝트 등록 데이터 기반 생성기 연동 준비
- FR-19: 조회용 프론트엔드
- FR-21: 프로젝트 등록 및 구성 관리
- FR-22: 프로젝트 정보 조회 및 수정
- FR-24: 빌드 현황 조회
- FR-26: 운영 관리 API 우선 원칙
- STORY-21: 프로젝트 등록, 저장소-빌드 연결, 생성 준비도 식별
- STORY-22: 조회/수정, 접힘형 등록 UI, 입력 후보 제안

## 테스트 케이스

| TC ID | 화면/기능 | 목적 | 사전조건 | 절차 | 기대 결과 | 추적 |
| --- | --- | --- | --- | --- | --- | --- |
| UI-LIST-001 | 프로젝트 목록 초기 진입 | 목록 화면 기본 구성 확인 | 프로젝트 데이터 1건 이상 존재 | 1. `/` 진입 | KPI 카드, 프로젝트 리스트, 주의 필요 프로젝트, 최근 실패 빌드 패널이 표시되고 등록 패널은 기본적으로 접혀 있다. | FR-19, STORY-22 |
| UI-LIST-002 | 프로젝트 목록 빈 상태 | 데이터가 없을 때 안내 문구 확인 | 프로젝트 데이터 없음 | 1. `/` 진입 | 프로젝트 테이블 대신 빈 상태 메시지가 표시된다. | FR-19 |
| UI-LIST-003 | 검색 | Jira/Bitbucket/대표 저장소 기준 검색 확인 | 검색 가능한 프로젝트 2건 이상 존재 | 1. 검색어에 Jira key 입력 2. Bitbucket key 입력 3. 대표 저장소 slug 입력 | 각 입력에 대해 해당 프로젝트만 남고, 일치하지 않으면 결과가 비거나 제외된다. | FR-19 |
| UI-LIST-004 | 상태 필터 `attention` | 주의 필요 프로젝트 필터 확인 | 경고 프로젝트와 정상 프로젝트가 함께 존재 | 1. `status=attention` 적용 | `needsAttention=true` 프로젝트만 목록에 표시된다. | FR-19 |
| UI-LIST-005 | 상태 필터 `healthy` | 정상 프로젝트 필터 확인 | 경고 프로젝트와 정상 프로젝트가 함께 존재 | 1. `status=healthy` 적용 | 경고 태그가 없는 프로젝트만 목록에 표시된다. | FR-19 |
| UI-LIST-006 | 페이지네이션 | 페이지당 10건 및 쿼리 유지 확인 | 프로젝트 11건 이상 존재 | 1. 검색 또는 필터 적용 2. 페이지 2로 이동 | 한 페이지에 최대 10건이 표시되고 페이지 이동 링크에 기존 검색/필터 쿼리가 유지된다. | FR-19 |
| UI-LIST-007 | 경고/준비도 표시 | 프로젝트별 상태 칩 표현 확인 | 준비 완료/미완료 프로젝트가 혼재 | 1. 목록 테이블의 상태 칼럼 확인 | `Specs 생성 가능` 또는 `Specs 준비 필요`가 표시되고 `정의 x/y`, 경고 태그, `정상` 여부가 계산 결과와 일치한다. | FR-16, FR-19 |
| UI-LIST-008 | 최근 실패 빌드 패널 | 실패 빌드 요약 노출 확인 | 최신 실패 실행 데이터 존재 | 1. 메인 화면 우측 패널 확인 | 빌드명, 상태, 프로젝트 키, 플랜 키, 버전, 빌드 번호, 요약 메시지가 표시된다. 실패 데이터가 없으면 빈 상태 문구가 나온다. | FR-19 |
| UI-REG-001 | 등록 패널 기본 접힘 | 메인 등록 UI 기본 상태 확인 | 없음 | 1. `/` 진입 | 등록 패널이 `hidden` 상태로 시작한다. | STORY-22 |
| UI-REG-002 | 등록 패널 펼침 | 버튼으로 등록 패널 열기 확인 | 없음 | 1. `프로젝트 등록` 버튼 클릭 | 등록 패널이 펼쳐지고 버튼 `aria-expanded`가 `true`로 바뀐다. | STORY-22 |
| UI-REG-003 | 입력 후보 제안 | datalist 기반 추천 값 확인 | 기존 프로젝트/저장소/Coverity 데이터 존재 | 1. 등록 폼 입력 필드 포커스 2. 브라우저 추천값 확인 | Jira key, Bitbucket key, 저장소 slug, Coverity project/stream 후보가 표시된다. | STORY-22 |
| UI-REG-004 | 프로젝트 등록 성공 | 다중 저장소/다중 빌드 등록 성공 확인 | 중복 없는 신규 프로젝트 데이터 준비 | 1. 등록 패널 펼침 2. 기본 정보 입력 3. 저장소 2건 입력 4. 빌드 2건 입력 5. 제출 | 프로젝트가 저장되고 `/projects/{jiraProjectKey}/`로 리다이렉트되며 상세 화면에 저장소/빌드가 모두 보인다. | FR-16, FR-21, STORY-21 |
| UI-REG-005 | 저장소 추가 UI | 저장소 반복 입력 블록 추가 확인 | 없음 | 1. 등록 패널 열기 2. `저장소 추가` 클릭 | 저장소 입력 카드가 1개 추가되고 기존 값은 유지된다. | STORY-21, STORY-22 |
| UI-REG-006 | 빌드 추가 UI | 빌드 반복 입력 블록 추가 확인 | 없음 | 1. 등록 패널 열기 2. `빌드 추가` 클릭 | 빌드 입력 카드가 1개 추가되고 기존 값은 유지된다. | STORY-21, STORY-22 |
| UI-REG-007 | 저장소 미입력 검증 | 저장소 최소 1건 규칙 확인 | 없음 | 1. 기본 정보 입력 2. 저장소 행은 비움 3. 빌드만 입력 4. 제출 | 등록 실패, 오류 메시지 `최소 1개 저장소를 입력해 주세요.` 표시, 패널은 열린 상태 유지 | STORY-21 |
| UI-REG-008 | 빌드 미입력 검증 | 빌드 최소 1건 규칙 확인 | 없음 | 1. 기본 정보와 저장소 입력 2. 빌드 행은 비움 3. 제출 | 등록 실패, 오류 메시지 `최소 1개 빌드를 입력해 주세요.` 표시, 패널은 열린 상태 유지 | STORY-21 |
| UI-REG-009 | 대표 저장소 검증 | 대표 저장소가 저장소 목록 내 값인지 확인 | 없음 | 1. 저장소 slug는 `repo-a` 입력 2. 대표 저장소는 `repo-b` 입력 3. 제출 | 등록 실패, 오류 메시지 `대표 저장소는 등록한 저장소 목록 중 하나여야 합니다.` 표시 | STORY-21, STORY-22 |
| UI-REG-010 | 빌드-저장소 연결 검증 | 빌드가 등록된 저장소에만 연결되는지 확인 | 없음 | 1. 저장소 slug는 `repo-a`만 입력 2. 빌드의 연결 저장소 slug는 `repo-b` 입력 3. 제출 | 등록 실패, `빌드 연결 저장소 'repo-b' 가 저장소 목록에 없습니다.` 표시 | STORY-21 |
| UI-REG-011 | 프로젝트 중복 검증 | 중복 Jira project key 등록 차단 확인 | 동일 Jira key 프로젝트 선등록 | 1. 기존 Jira key로 신규 등록 시도 | 등록 실패, 중복 오류가 표시되고 기존 프로젝트 데이터는 변경되지 않는다. | STORY-21 |
| UI-REG-012 | 요청 내 중복 저장소/빌드 검증 | 동일 요청 내 중복 입력 차단 확인 | 없음 | 1. 동일 `repoSlug` 2건 또는 동일 `buildId`/`planKey` 2건으로 제출 | 등록 실패, 중복 항목에 대한 오류 메시지가 표시된다. | STORY-21 |
| UI-DETAIL-001 | 프로젝트 상세 조회 | 상세 기본 정보 표시 확인 | 대상 프로젝트 존재 | 1. `/projects/{jiraProjectKey}/` 진입 | Jira key, Bitbucket key, 대표 저장소, 수정 시각, 저장소 수, 빌드 수, 활성 정의 수가 표시된다. | FR-12, FR-19, STORY-22 |
| UI-DETAIL-002 | 생성 준비도 패널 | 준비도 계산 결과 표시 확인 | 준비 완료/미완료 프로젝트 각각 존재 | 1. 상세 화면의 `Specs 생성 준비도` 패널 확인 | 생성 가능 여부, 활성 정의 연결 수, 준비 이슈가 selector 계산 결과와 일치한다. | FR-16, FR-21 |
| UI-DETAIL-003 | 저장소 패널 | 저장소 메타데이터 표시 확인 | 저장소 1건 이상 존재 | 1. 상세 화면 저장소 패널 확인 | 각 저장소의 slug, Coverity project, Coverity stream이 표시되고 대표 저장소는 별도 칩으로 강조된다. | FR-12, FR-21 |
| UI-DETAIL-004 | 빌드 패널 | 빌드 메타데이터 표시 확인 | 빌드 1건 이상 존재 | 1. 상세 화면 빌드 패널 확인 | 빌드 이름, plan key, 활성 정의 여부, 활성 정의 연도, 최신 버전, build type, runtime stack, build id, 연결 저장소가 표시된다. | FR-12, FR-19 |
| UI-DETAIL-005 | 없는 프로젝트 상세 | 미존재 프로젝트 처리 확인 | 대상 Jira key 없음 | 1. 존재하지 않는 `/projects/{jiraProjectKey}/` 진입 | `프로젝트를 찾을 수 없습니다.` 빈 상태와 목록 복귀 링크가 표시된다. | FR-19 |
| UI-REPO-001 | 저장소 상세 조회 | 저장소 단위 메타데이터 확인 | 대상 프로젝트와 저장소 존재 | 1. `/projects/{jiraProjectKey}/repositories/{repoSlug}/` 진입 | 저장소 상세, Coverity 정보, 연결된 빌드 목록이 표시된다. | FR-12, FR-21 |
| UI-REPO-002 | 저장소 상세 미존재 처리 | 저장소 누락 시 안내 확인 | 대상 프로젝트는 존재하나 저장소는 없음 | 1. 저장소 상세 URL 진입 | 저장소 없음 상태가 표시된다. | FR-19 |
| UI-BUILD-001 | 빌드 상세 조회 | 빌드 메타데이터와 Bamboo 상태 확인 | 대상 프로젝트와 빌드 존재 | 1. `/projects/{jiraProjectKey}/builds/{planKey}/` 진입 | 빌드 메타데이터, BuildInfo 목록, Specs draft, Bamboo 상태, publish/run 패널이 표시된다. | FR-12, FR-19, FR-21, FR-24 |
| UI-BUILD-002 | 빌드 메타데이터 수정 | 플랜 단위 메타데이터 편집 확인 | 대상 빌드 존재 | 1. 빌드 상세에서 메타데이터 편집 2. 정적분석 도구 버전/ Coverity project/ linkage override 변경 3. 제출 | 상세로 돌아오고 변경값이 반영된다. | FR-21, FR-22 |
| UI-BUILD-003 | BuildInfo 추가 | 플랜 아래 상세 빌드 정보 추가 확인 | 대상 빌드 존재 | 1. 빌드 상세에서 BuildInfo 추가 2. `빌드 이름`, `OS`, `명령`, `언어`, `컴파일러`, `subPath` 입력 3. 제출 | BuildInfo가 생성되고 상세 화면 목록에 반영된다. | FR-21, FR-22 |
| UI-BUILD-004 | Specs draft 재초기화 | 플랜 초안 재생성 확인 | 대상 빌드 존재 | 1. 빌드 상세에서 `Specs 초안 다시 채우기` 실행 | 초안이 갱신되거나, 갱신할 데이터가 없으면 안내 메시지가 표시된다. | FR-16, FR-21 |
| UI-BUILD-005 | Bamboo publish | Bamboo Specs publish 수행 확인 | Bamboo 서버 설정과 토큰이 유효 | 1. 빌드 상세에서 publish 실행 | 성공 시 publish 메시지와 snapshot이 저장되고, 실패 시 오류 상세가 표시된다. | FR-19, FR-24 |
| UI-BUILD-006 | Bamboo run | Bamboo plan queue 요청 확인 | Bamboo 서버 설정과 토큰이 유효 | 1. 빌드 상세에서 stage/variables 입력 2. 실행 요청 | 큐 요청 성공 메시지와 전송된 옵션이 표시된다. | FR-24, FR-26 |
| UI-BUILD-007 | Task Inspector | 예상 Bamboo task 구조 확인 | BuildInfo 또는 draft 데이터 존재 | 1. 빌드 상세의 task inspector 영역 확인 | 예상 stage/job/task 구조가 표시된다. | FR-19, FR-21 |
| UI-BUILD-008 | Bamboo 상태/상세 불일치 | Bamboo 미연결 상태 확인 | Bamboo 서버 URL 또는 토큰 미설정 | 1. 빌드 상세/Bamboo 상세 진입 | 설정 누락 상태가 표시되고, 상세 조회가 실패하면 오류 메시지가 나온다. | FR-24, FR-26 |
| UI-BUILD-009 | 빌드 상세 미존재 처리 | 잘못된 plan key 확인 | 존재하지 않는 plan key | 1. 빌드 상세 URL 진입 | 빌드 없음 상태가 표시된다. | FR-19 |
| UI-BUILDINFO-001 | BuildInfo 목록 진입 | BuildInfo 관리 진입 확인 | 대상 빌드 존재 | 1. `/projects/{jiraProjectKey}/builds/{planKey}/infos/` 진입 | BuildInfo 추가 편집 화면으로 이동한다. | FR-21 |
| UI-BUILDINFO-002 | BuildInfo 상세 조회 | 개별 BuildInfo 수정 확인 | 대상 빌드와 BuildInfo 존재 | 1. `/projects/{jiraProjectKey}/builds/{planKey}/infos/{buildKey}/` 진입 | BuildInfo 메타데이터와 수정 폼이 표시된다. | FR-21, FR-22 |
| UI-BUILDINFO-003 | BuildInfo 수정 성공 | 개별 BuildInfo 값 반영 확인 | 대상 BuildInfo 존재 | 1. BuildInfo 일부 필드 변경 2. 제출 | 상세로 리다이렉트되고 변경값이 반영된다. | FR-21, FR-22 |
| UI-BUILDINFO-004 | BuildInfo 수정 실패 | 개별 BuildInfo 오류 처리 확인 | 대상 BuildInfo 존재 | 1. 필수 입력을 비운 상태로 제출 | 오류 메시지가 표시되고 입력값은 유지된다. | FR-21, FR-22 |
| UI-SET-001 | Coverity/Bamboo 설정 조회 | 운영 공통 설정 화면 확인 | 설정 데이터 존재 | 1. `/settings/coverity/` 진입 | Coverity Connect URL, on-new-cert, commit flag, repository linkage mode, git clone URL template, Bamboo server URL이 표시된다. | FR-17, FR-26 |
| UI-SET-002 | 운영 설정 수정 | 시스템 설정 저장 확인 | 설정 편집 가능 | 1. 설정 필드 변경 2. 저장 | 저장 후 페이지에 갱신된 값이 반영된다. | FR-17, FR-26 |
| UI-SET-003 | Specs draft 전체 초기화 | 운영 데이터 초기화 확인 | 샘플/등록 데이터 존재 | 1. 초기화 동작 실행 | 등록된 플랜들의 Specs draft가 현재 기준으로 다시 채워진다. | FR-16, FR-21 |
| UI-PLAN-001 | Bamboo plan 상세 조회 | Bamboo 저장 상태 확인 | Bamboo 서버 연결 가능 | 1. `/projects/{jiraProjectKey}/builds/{planKey}/bamboo/` 진입 | Bamboo plan 상태, stages, branches, actions, variables가 표시된다. | FR-24, FR-26 |
| UI-PLAN-002 | Bamboo plan 상세 실패 | Bamboo 미등록 상태 확인 | Bamboo 서버 미연결 또는 plan 미등록 | 1. Bamboo 상세 진입 | 오류 메시지 또는 미등록 상태가 표시된다. | FR-24 |
| UI-PLAN-003 | publish snapshot task tree | 마지막 publish 기준 task 구조 확인 | 성공 publish snapshot 존재 | 1. Bamboo 상세 화면의 task tree 확인 | stage/job/task 구조가 publish snapshot 기준으로 표시된다. | FR-19, FR-24 |

## 우선 실행 순서

1. UI-LIST-001, UI-REG-001, UI-REG-004, UI-DETAIL-001
2. UI-DETAIL-002, UI-BUILD-001, UI-BUILD-002, UI-BUILDINFO-002
3. UI-SET-001, UI-PLAN-001, UI-REPO-001
4. UI-REG-009, UI-REG-010, UI-EDIT-003, UI-EDIT-004
5. 나머지 보강 케이스

## 현재 구현 기준 메모

- `언어`와 `컴파일러` 입력은 현재 자유 입력 필드이며 선택형 목록은 아직 구현되지 않았다.
- 프로젝트 등록 UI는 접힘/펼침, 입력 후보 제안, 다중 저장소/다중 빌드 입력을 지원한다.
- BuildInfo와 빌드 플랜 메타데이터는 현재 화면에서 수정 가능하지만, 사용자/권한/감사 기록은 없다.
- Bamboo 상세와 publish/run은 설정값과 외부 Bamboo 상태에 의존하므로, 실패 케이스를 함께 검증하는 편이 좋다.
