# EPIC-01 Bamboo Specs 기반 플랜 생성기 구축

## 유형

- Epic

## 구현 상태

- 부분 구현
- JSON 입력 로딩, 검증, 단일 Specs 프로젝트 생성, 스크립트 자산 관리, MSBuild 보정은 코드로 반영되어 있다.
- 브랜치별 트리거 생성과 `create_if_missing` 실동작은 아직 구현되지 않았다.

## 우선순위

- 현재 유지 및 보강 대상 Epic

## 요약

연도별로 관리되는 하나 이상의 JSON 빌드 정의를 읽어, 여러 빌드에 대응하는 Bamboo Specs Java 코드를 하나의 Specs 저장소 안에 생성하고, Bitbucket 저장소 연결 및 브랜치 트리거 구성까지 함께 지원하는 애플리케이션을 구축한다.

## 배경

- Bamboo 플랜 구성을 반복적으로 수작업 처리하면 설정 편차와 유지보수 비용이 증가한다.
- 빌드 정의를 JSON으로 표준화하면 재사용성과 변경 이력 관리가 쉬워진다.
- Bamboo Specs Java 코드 생성을 자동화하면 플랜 생성 과정을 일관되게 운영할 수 있다.
- 실제 운영에서는 Bitbucket 저장소 연결과 브랜치 트리거 구성이 함께 정의되어야 플랜을 즉시 활용할 수 있다.

## 설명

시스템은 여러 JSON 파일을 입력으로 받아야 하며, 타겟 빌드는 연도별로 관리될 수 있어야 한다. 각 빌드 정의를 분석해 하나의 Bamboo Specs 저장소 안에서 여러 플랜을 함께 관리할 수 있는 Bamboo Specs Java 코드를 생성해야 한다. 또한 Atlassian에서 제공하는 Bamboo Specs Base 코드를 저장소에서 관리하고 생성 로직에 재사용할 수 있어야 한다. 입력 JSON의 `projectKey`, `repoSlug`를 기반으로 Bitbucket 저장소를 식별하고, `dev`, `release`, `master` 브랜치에 대한 트리거 구성을 생성할 수 있어야 한다.

## 범위

### 포함

- JSON 기반 빌드 정의 모델링
- 다중 JSON 입력 처리
- 연도별 빌드 정의 관리
- Bamboo Specs Java 코드 생성
- 단일 Specs 저장소 내 플랜 구조화
- Base 코드 보관 및 재사용 전략
- Bitbucket 저장소 연결 정보 모델링
- 미등록 저장소 대응 전략
- 브랜치별 트리거 구성 생성

### 제외

- Bamboo 서버 자동 배포
- GUI 기반 입력 편집 기능
- Bamboo 외 CI/CD 도구 지원

## 수용 기준

- 하나 이상의 JSON 파일을 읽어 빌드 정의별로 처리할 수 있다.
- 연도별 관리 구조를 지원한다.
- 각 빌드 정의에 대해 Bamboo Specs Java 코드를 생성할 수 있다.
- 생성 결과는 단일 Bamboo Specs 저장소 안에서 여러 플랜을 함께 관리할 수 있다.
- 입력 JSON의 `projectKey`, `repoSlug`로 저장소를 식별할 수 있다.
- 사전 등록 저장소와 미등록 저장소에 대한 처리 방식을 구분할 수 있다.
- `dev`, `release`, `master` 브랜치별 트리거 구성이 정의된다.
- Base 코드 저장 위치와 활용 전략이 정의된다.

## 하위 이슈

- STORY-01 JSON 스키마 및 연도별 관리 구조 정의
- STORY-02 다중 JSON 입력 로딩 및 빌드 정의 식별 기능 구현
- STORY-03 Bamboo Specs Java 코드 생성 기능 구현
- STORY-04 단일 Specs 저장소 구조 및 등록 방식 설계
- STORY-05 Atlassian Base 코드 확보 및 저장소 관리 체계 정의
- STORY-06 공통 워크플로우 템플릿 및 빌드 상세 입력 구조 정의
- STORY-07 저장소 연결용 JSON 필드 및 검증 규칙 정의
- STORY-08 Bitbucket 저장소 연결 및 미등록 저장소 대응 설계
- STORY-09 브랜치별 연결 및 트리거 구성 생성
- STORY-10 MSBuild 플랜용 Directory.Build.targets 사전 생성 지원
- STORY-11 빌드 작업 하위 경로 지정 지원

## 오픈 이슈

- Bamboo 플랜 최소 구성 요소 범위를 어디까지 포함할지 결정 필요
- 미등록 저장소 대응을 어떤 Bamboo 모델로 구현할지 확정 필요
- 최종적으로 Bamboo 반영 자동화까지 포함할지 범위 확정 필요
