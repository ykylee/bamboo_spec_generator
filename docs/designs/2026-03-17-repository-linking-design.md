# 설계: Bitbucket 저장소 연결 및 브랜치 트리거

## 문서 메타데이터

- 문서 일자: 2026-03-17
- 문서 유형: Design
- 상태: 초안
- 관련 SRS: [../requirements/2026-03-17-bamboo-spec-generator-srs.md](../requirements/2026-03-17-bamboo-spec-generator-srs.md)
- 관련 초기 설계: [./2026-03-17-initial-design.md](./2026-03-17-initial-design.md)
- 관련 스키마 설계: [./2026-03-17-json-schema-design.md](./2026-03-17-json-schema-design.md)

## 요약

이 문서는 Bamboo Specs 생성기에서 Bitbucket 저장소 연결과 브랜치별 트리거를 어떻게 모델링하고 생성할지 정의한다. 초기 버전은 `projectKey`, `repoSlug`를 기준으로 저장소를 식별하고, `linked`와 `create_if_missing` 두 가지 연결 모드를 지원하며, `dev`, `release`, `master` 브랜치를 기본 연결 및 트리거 대상으로 다룬다.

## 배경

- 통합 요구사항은 저장소 연결과 브랜치 트리거를 생성 결과에 포함하도록 요구한다.
- Bamboo 환경에 따라 저장소가 사전 등록되어 있을 수도, 그렇지 않을 수도 있다.
- 저장소 연결 방식이 모호하면 운영자가 생성 결과를 수동으로 보정해야 한다.

## 목표

- 저장소 연결 모델을 입력 JSON과 내부 모델 양쪽에서 일관되게 정의한다.
- 사전 등록 저장소와 미등록 저장소에 대한 처리 전략을 명확히 한다.
- 브랜치별 연결 및 트리거 생성 규칙을 결정한다.

## 비목표

- Bitbucket 저장소 생성 자동화
- 저장소 인증 정보 관리 자동화
- 브랜치 패턴 일반화

## 설계안

### 1. 저장소 입력 모델

`repository` 블록은 다음 구조를 사용한다.

```json
{
  "provider": "bitbucket",
  "projectKey": "SAMPLE",
  "repoSlug": "sample-app-api",
  "linkageMode": "linked",
  "branches": ["dev", "release", "master"]
}
```

- `provider`는 초기 버전에서 `bitbucket` 고정이다.
- `projectKey`와 `repoSlug`는 필수다.
- `linkageMode`는 생략 시 `linked`다.
- `branches`는 생략 시 `dev`, `release`, `master`를 기본값으로 사용한다.

### 2. 내부 모델

- `RepositoryDefinition`
  - `provider`
  - `projectKey`
  - `repoSlug`
  - `linkageMode`
  - `branches`
- `BranchTriggerDefinition`
  - `name`
  - `triggerEnabled`
  - `order`

`order`는 생성 결과 일관성을 위해 고정한다. 기본값은 `dev=1`, `release=2`, `master=3`이다.

### 3. 연결 모드 전략

#### `linked`

- Bamboo에 사전 등록된 linked repository를 참조하는 모드다.
- 생성기는 `projectKey/repoSlug`를 기반으로 참조 식별자를 만든다.
- 운영 환경에서 linked repository 명명 규칙이 있더라도 입력 식별자는 원본 값을 유지한다.

#### `create_if_missing`

- 사전 등록 저장소가 없어도 생성 결과를 만들기 위한 모드다.
- 초기 버전에서는 Bamboo Specs에서 직접 linked repository를 완전 생성한다고 가정하지 않는다.
- 대신 생성 결과에 다음 정보를 남긴다.
  - 원본 `projectKey`
  - 원본 `repoSlug`
  - 연결 모드
  - 후속 등록 필요 여부
- 이를 통해 운영자가 사후 보정하거나, 후속 구현에서 직접 연결 생성 로직을 추가할 수 있게 한다.

### 4. 브랜치 정책

- 기본 브랜치는 `dev`, `release`, `master`다.
- `release`는 초기 버전에서 단일 브랜치명으로 고정한다.
- 입력 JSON이 `branches`를 명시하더라도 세 기본 브랜치를 모두 포함해야 한다.
- 브랜치별 트리거는 모두 활성화 대상이다.

### 5. 생성 규칙

플랜 생성 시 저장소 관련 메타데이터는 다음 순서로 반영한다.

1. `projectKey/repoSlug`로 저장소 식별자 구성
2. `linkageMode`에 따라 linked 참조 또는 후속 등록 메타데이터 결정
3. 브랜치 목록 정규화
4. 브랜치별 트리거 정의 생성
5. 플랜 객체에 저장소 연결 정보와 트리거 정보 결합

### 6. 검증 규칙

- `projectKey`, `repoSlug`는 비어 있으면 안 된다.
- `provider`가 주어지면 `bitbucket`만 허용한다.
- `linkageMode`는 `linked`, `create_if_missing`만 허용한다.
- `branches`는 중복되면 안 된다.
- `branches`에는 `dev`, `release`, `master`가 모두 포함되어야 한다.

### 7. 오류 처리

- 저장소 필드 누락은 검증 단계에서 오류로 처리한다.
- 잘못된 연결 모드는 생성 단계까지 진행하지 않는다.
- 기본 브랜치가 누락되면 어떤 브랜치가 빠졌는지 포함한 메시지를 반환한다.

## 대안

### 대안 1. 브랜치 정책을 완전 고정

- 장점: 스키마와 구현이 단순하다.
- 단점: 향후 예외 프로젝트 대응이 어렵다.

### 대안 2. `release/*` 패턴 지원

- 장점: 일반적인 release 브랜치 운영에 더 유연하다.
- 단점: 초기 검증 규칙과 트리거 생성이 복잡해진다.

### 대안 3. 미등록 저장소를 즉시 linked repository로 생성

- 장점: 운영자 후속 작업을 줄일 수 있다.
- 단점: Bamboo Specs API 지원 범위와 환경 의존성이 커진다.

## 영향 범위

- 입력 JSON 스키마 변경
- 파서 및 검증 로직 변경
- 내부 모델 확장
- Bamboo Specs 생성 로직 확장
- 샘플 JSON 및 README 문서 갱신 필요

## 수용 기준

- 저장소 연결 입력 모델이 문서화되어 있다.
- `linked`, `create_if_missing` 두 연결 모드의 처리 전략이 정의되어 있다.
- `dev`, `release`, `master` 브랜치 트리거 규칙이 정의되어 있다.
- 검증 규칙과 오류 처리 방향이 정의되어 있다.

## 오픈 이슈

- Bamboo Specs에서 미등록 저장소를 직접 생성할 수 있는지 실제 API 기준 확인 필요
- Bitbucket Server/Data Center와 Cloud 중 우선 지원 대상을 확정할 필요가 있다
- 브랜치별 트리거를 단일 플랜 안에서 표현할지 브랜치 플랜으로 분리할지 후속 판단 필요
