# JSON 스키마 설계: Bamboo 빌드 정의

## 문서 메타데이터

- 문서 일자: 2026-03-17
- 문서 유형: Design
- 상태: 초안
- 관련 SRS: [../requirements/2026-03-17-bamboo-spec-generator-srs.md](../requirements/2026-03-17-bamboo-spec-generator-srs.md)
- 관련 초기 설계: [./2026-03-17-initial-design.md](./2026-03-17-initial-design.md)

## 요약

이 문서는 Bamboo Specs 생성기에 입력으로 사용할 JSON 빌드 정의 스키마 초안을 제안한다. 연도 정보는 JSON 내부가 아니라 디렉터리 경로에서 관리하며, JSON은 개별 빌드 정의 자체에만 집중한다.

## 배경

- 연도별 운영 기준을 디렉터리 구조로 확정했다.
- 따라서 JSON은 빌드 정의의 내용만 표현하고, 관리 메타데이터 일부는 파일 시스템 구조가 담당한다.
- 초기 MVP에서는 최소 Bamboo 플랜 생성에 필요한 필드만 포함하는 것이 적절하다.

## 목표

- 사람이 작성하고 검토하기 쉬운 JSON 구조를 정의한다.
- 생성기 내부 모델로 변환하기 쉬운 스키마를 제공한다.
- 이후 단계, 작업, 태스크 확장에 대응 가능한 구조를 마련한다.

## 비목표

- 모든 Bamboo 기능을 첫 버전에서 표현하지 않는다.
- Base 코드 세부 구조를 JSON 스키마에 반영하지 않는다.

## 설계안

### 1. 파일 배치 규칙

- 입력 파일은 `build_info_json/<year>/<buildId>.json` 구조를 권장한다.
- `<year>` 디렉터리명이 빌드 정의의 연도다.
- 파일명은 `buildId`와 동일하게 맞추는 것을 권장하지만 필수는 아니다.

예시:

```text
build_info_json/
└── 2026/
    ├── sample-app-api.json
    └── sample-app-web.json
```

### 2. 최상위 JSON 구조

```json
{
  "buildId": "sample-app-api",
  "name": "Sample App API",
  "planKey": "SAMPAPI",
  "description": "Sample App API build plan",
  "repository": {
    "name": "sample-app-repo",
    "branch": "main"
  },
  "stages": [
    {
      "name": "Build",
      "jobs": [
        {
          "key": "BUILD",
          "name": "Build Job",
          "tasks": [
            {
              "type": "script",
              "description": "Run Gradle build",
              "inlineBody": "./gradlew clean build"
            }
          ]
        }
      ]
    }
  ]
}
```

### 3. 필드 정의

#### 최상위 필드

- `buildId`
  - 타입: `string`
  - 필수: 예
  - 설명: 저장소 내부 및 산출물 경로에서 사용하는 빌드 식별자
- `name`
  - 타입: `string`
  - 필수: 예
  - 설명: 사람이 읽는 플랜 이름
- `planKey`
  - 타입: `string`
  - 필수: 예
  - 설명: Bamboo 플랜 키
- `description`
  - 타입: `string`
  - 필수: 아니오
  - 설명: 플랜 설명
- `repository`
  - 타입: `object`
  - 필수: 예
  - 설명: 소스 저장소 정보
- `stages`
  - 타입: `array`
  - 필수: 예
  - 설명: Bamboo 플랜의 단계 목록

#### repository

- `name`
  - 타입: `string`
  - 필수: 예
  - 설명: 저장소 식별 이름
- `branch`
  - 타입: `string`
  - 필수: 예
  - 설명: 기본 브랜치

#### stages[]

- `name`
  - 타입: `string`
  - 필수: 예
  - 설명: 스테이지 이름
- `jobs`
  - 타입: `array`
  - 필수: 예
  - 설명: 스테이지에 속한 작업 목록

#### jobs[]

- `key`
  - 타입: `string`
  - 필수: 예
  - 설명: Bamboo Job 키
- `name`
  - 타입: `string`
  - 필수: 예
  - 설명: Job 이름
- `tasks`
  - 타입: `array`
  - 필수: 예
  - 설명: Job에서 실행할 태스크 목록

#### tasks[]

- `type`
  - 타입: `string`
  - 필수: 예
  - 허용 초안 값: `script`
  - 설명: 태스크 타입
- `description`
  - 타입: `string`
  - 필수: 아니오
  - 설명: 태스크 설명
- `inlineBody`
  - 타입: `string`
  - 필수: `type=script`일 때 예
  - 설명: 인라인 스크립트 본문

### 4. 검증 규칙

- `buildId`는 동일 연도 디렉터리 내에서 유일해야 한다.
- `planKey`는 전체 입력 집합에서 중복되지 않아야 한다.
- `stages`는 최소 1개 이상이어야 한다.
- 각 `stage.jobs`는 최소 1개 이상이어야 한다.
- 각 `job.tasks`는 최소 1개 이상이어야 한다.
- 초기 MVP에서는 `tasks[].type`으로 `script`만 지원한다.
- 연도는 JSON이 아니라 상위 디렉터리명에서 해석한다.

### 5. 내부 모델 매핑 초안

- 디렉터리명 `2026` -> 내부 모델 `year`
- `buildId` -> 내부 모델 `buildId`
- `name` -> 내부 모델 `name`
- `planKey` -> 내부 모델 `planKey`
- `repository` -> 내부 모델 `repository`
- `stages[].jobs[].tasks[]` -> Bamboo Specs 단계/잡/태스크 모델

### 6. 확장 포인트

- `variables`
- `triggers`
- `notifications`
- `permissions`
- `branches`
- `artifacts`

이 항목들은 MVP 이후 선택적으로 추가한다.

## 대안

### 대안 1. JSON에 `year` 필드 추가

- 장점: 단일 파일만 봐도 연도를 알 수 있다.
- 단점: 디렉터리 기준 정보와 중복되어 불일치 가능성이 생긴다.

### 대안 2. 모든 빌드를 배열로 묶은 단일 JSON

- 장점: 파일 수가 줄어든다.
- 단점: 빌드별 변경 추적과 개별 관리가 어려워진다.

## 영향 범위

- 입력 검증기 구현
- 내부 모델 구조 설계
- 생성기 초기 MVP 범위 정의
- 예제 입력 파일 작성
- 단일 Bamboo Specs 프로젝트 내 플랜별 클래스 및 파일 배치 규칙 정의

## 수용 기준

- 연도는 디렉터리 구조로 관리된다는 규칙이 명시되어 있다.
- 최상위 필수 필드와 하위 객체 구조가 정의되어 있다.
- MVP에서 지원할 최소 태스크 구조가 정의되어 있다.
- 검증 규칙과 확장 포인트가 정리되어 있다.
- 검토 가능한 예시 JSON이 포함되어 있다.

## 오픈 이슈

- `repository` 구조를 어디까지 상세화할지 결정 필요
- `planKey` 네이밍 규칙을 별도 제약으로 둘지 결정 필요
- 초기 MVP에 `script` 외 태스크 타입을 포함할지 결정 필요
- 플랜 변수와 트리거를 1차 범위에 넣을지 결정 필요

## 다음 단계

- 이 스키마 초안을 검토해 필드 추가/삭제 확정
- 예제 JSON 파일 세트 작성
- 검증 규칙을 별도 체크리스트 또는 JSON Schema 문서로 구체화
