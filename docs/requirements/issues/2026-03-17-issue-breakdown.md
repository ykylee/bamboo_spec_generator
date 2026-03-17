# Bamboo Spec Generator 이슈 분해

## 개요

현재 CRS를 Jira 등록 가능한 단위로 분해한 초안이다. 상위 에픽 1건과 하위 스토리 5건으로 구성한다.

## 이슈 목록

- [EPIC-01 Bamboo Specs 기반 플랜 생성기 구축](./EPIC-01-bamboo-spec-generator.md)
- [STORY-01 타겟 빌드 JSON 스키마 및 연도별 관리 구조 정의](./STORY-01-json-schema-and-yearly-structure.md)
- [STORY-02 다중 JSON 입력 로딩 및 빌드 정의 식별 기능 구현](./STORY-02-multi-json-loading.md)
- [STORY-03 Bamboo Specs Java 코드 생성 기능 구현](./STORY-03-bamboo-specs-code-generation.md)
- [STORY-04 빌드별 산출물 분리 및 등록 단위 구조 설계](./STORY-04-output-structure.md)
- [STORY-05 Atlassian Base 코드 확보 및 저장소 관리 체계 정의](./STORY-05-base-code-management.md)

## 분해 기준

- 상위 에픽은 프로젝트 목표와 전체 범위를 담당한다.
- 하위 스토리는 입력 모델, 입력 처리, 생성 로직, 산출물 구조, Base 코드 관리로 나눴다.
- 각 스토리는 Jira에 바로 등록 가능한 수준의 요약과 수용 기준을 포함한다.
