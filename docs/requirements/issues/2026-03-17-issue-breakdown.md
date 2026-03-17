# Bamboo Spec Generator 이슈 분해

## 개요

현재 통합 CRS를 Jira 등록 가능한 단위로 분해한 초안이다. 상위 에픽 1건과 하위 스토리 11건으로 구성한다.

## 이슈 목록

- [EPIC-01 Bamboo Specs 기반 플랜 생성기 구축](./EPIC-01-bamboo-spec-generator.md)
- [STORY-01 타겟 빌드 JSON 스키마 및 연도별 관리 구조 정의](./STORY-01-json-schema-and-yearly-structure.md)
- [STORY-02 다중 JSON 입력 로딩 및 빌드 정의 식별 기능 구현](./STORY-02-multi-json-loading.md)
- [STORY-03 Bamboo Specs Java 코드 생성 기능 구현](./STORY-03-bamboo-specs-code-generation.md)
- [STORY-04 빌드별 산출물 분리 및 등록 단위 구조 설계](./STORY-04-output-structure.md)
- [STORY-05 Atlassian Base 코드 확보 및 저장소 관리 체계 정의](./STORY-05-base-code-management.md)
- [STORY-06 공통 워크플로우 템플릿 및 빌드 상세 입력 구조 정의](./STORY-06-workflow-template-and-build-details.md)
- [STORY-07 저장소 연결용 JSON 필드 및 검증 규칙 정의](./STORY-07-repository-json-fields.md)
- [STORY-08 Bitbucket 저장소 연결 및 미등록 저장소 대응 설계](./STORY-08-bitbucket-linking-and-fallback.md)
- [STORY-09 브랜치별 연결 및 트리거 구성 생성](./STORY-09-branch-trigger-mapping.md)
- [STORY-10 MSBuild 플랜용 Directory.Build.targets 사전 생성 지원](./STORY-10-msbuild-directory-build-targets-override.md)
- [STORY-11 빌드 작업 하위 경로 지정 지원](./STORY-11-build-working-subpath-support.md)

## 분해 기준

- 상위 에픽은 프로젝트 목표와 전체 범위를 담당한다.
- 하위 스토리는 입력 모델, 입력 처리, 생성 로직, 산출물 구조, Base 코드 관리, 저장소 연결, 브랜치 트리거 생성으로 나눴다.
- 각 스토리는 Jira에 바로 등록 가능한 수준의 요약과 수용 기준을 포함한다.
