# JSON 스키마 설계: Bamboo 빌드 정의

## 문서 메타데이터

- 문서 일자: 2026-03-17
- 문서 유형: Design
- 상태: 초안
- 관련 SRS: [../requirements/2026-03-17-bamboo-spec-generator-srs.md](../requirements/2026-03-17-bamboo-spec-generator-srs.md)
- 관련 초기 설계: [./2026-03-17-initial-design.md](./2026-03-17-initial-design.md)

## 요약

이 문서는 Bamboo Specs 생성기에 입력으로 사용할 JSON 빌드 정의 스키마 초안을 제안한다. 연도 정보는 JSON 내부가 아니라 디렉터리 경로에서 관리하며, JSON은 개별 빌드 정의의 언어 및 빌드 상세 설정, Bitbucket 저장소 연결 정보에 집중한다. 스테이지 워크플로우는 공통 템플릿으로 고정한다.

## 배경

- 연도별 운영 기준을 디렉터리 구조로 확정했다.
- 따라서 JSON은 빌드 정의의 내용만 표현하고, 관리 메타데이터 일부는 파일 시스템 구조가 담당한다.
- 초기 MVP에서는 최소 Bamboo 플랜 생성에 필요한 필드만 포함하고, 공통 스테이지 정의는 입력에서 제외하는 것이 적절하다.

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

### 2. 공통 워크플로우 전제

- 모든 플랜은 동일한 워크플로우를 사용한다.
- 스테이지 순서는 다음과 같이 고정한다.
  1. 빌드 준비
  2. 빌드
  3. 정적분석
  4. 후속 작업 트리거
- 정적분석 스테이지는 2개의 병렬 Job으로 실행한다.
- 정적분석 Job 1은 Coverity로 고정한다.
- 정적분석 Job 2는 커스텀툴로 고정하며, 명령어 셋 안에 `analyze {build command}` 형태를 포함한다.
- Coverity Job은 생성기가 만든 `coverity.yaml`을 사용해 `coverity scan` 명령으로 실행한다.
- 스크립트 실행 명령은 가능하면 shell 전용 스크립트 대신 Python 스크립트 호출 형태를 사용한다.
- JSON은 이 워크플로우 전체를 정의하지 않고, 각 스테이지에서 사용할 빌드 상세 설정만 제공한다.

### 3. 최상위 JSON 구조

```json
{
  "buildId": "sample-app-api",
  "name": "Sample App API",
  "planKey": "SAMPAPI",
  "description": "Sample App API build plan",
  "language": "java",
  "compiler": "maven",
  "repository": {
    "provider": "bitbucket",
    "projectKey": "SAMPLE",
    "repoSlug": "sample-app-api",
    "linkageMode": "linked",
    "branches": [
      "dev",
      "release",
      "master"
    ]
  },
  "requirements": {
    "os": "linux",
    "extraCapabilities": [
      "cuda12.1"
    ]
  },
  "build": {
    "prepareCommand": "python scripts/prepare_build.py --tool maven",
    "buildCommand": "python scripts/run_build.py --tool maven --goal package",
    "staticAnalysis": {
        "customTool": {
          "commands": [
            "python scripts/custom_tool.py init",
            "custom-tool analyze {buildCommand}",
            "python scripts/custom_tool.py publish"
          ]
        }
    },
    "postBuildTrigger": {
      "type": "plan",
      "targetPlanKey": "POSTBUILD"
    }
  }
}
```

### 4. 필드 정의

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
- `language`
  - 타입: `string`
  - 필수: 예
  - 설명: 빌드 대상 언어
- `compiler`
  - 타입: `string`
  - 필수: 예
  - 설명: 컴파일러 또는 빌드 도구 식별자
- `repository`
  - 타입: `object`
  - 필수: 예
  - 설명: Bitbucket 저장소 연결 정보
- `requirements`
  - 타입: `object`
  - 필수: 예
  - 설명: 빌드 Job에 적용할 agent capability 요구사항
- `build`
  - 타입: `object`
  - 필수: 예
  - 설명: 공통 워크플로우 내 상세 빌드 설정

#### repository

- `provider`
  - 타입: `string`
  - 필수: 아니오
  - 기본값: `bitbucket`
  - 설명: 저장소 제공자 식별자
- `projectKey`
  - 타입: `string`
  - 필수: 예
  - 설명: Bitbucket project key
- `repoSlug`
  - 타입: `string`
  - 필수: 예
  - 설명: Bitbucket repository slug
- `linkageMode`
  - 타입: `string`
  - 필수: 아니오
  - 기본값: `linked`
  - 허용 초안 값: `linked`, `create_if_missing`
  - 설명: Bamboo 저장소 연결 방식
- `branches`
  - 타입: `array<string>`
  - 필수: 아니오
  - 기본값: `["dev", "release", "master"]`
  - 설명: 저장소 연결 및 트리거 생성 대상 브랜치 목록

#### requirements

- `os`
  - 타입: `string`
  - 필수: 예
  - 허용 초안 값: `windows`, `linux`
  - 설명: 에이전트 OS capability 요구사항
- `extraCapabilities`
  - 타입: `array<string>`
  - 필수: 아니오
  - 설명: 프로젝트 특성에 따른 보조 capability 목록. 예: `cuda12.1`, `nuget`

#### build

- `prepareCommand`
  - 타입: `string`
  - 필수: 예
  - 설명: 빌드 준비 스테이지에서 사용할 명령. 가능하면 Python 스크립트 호출 형태를 사용한다.
- `buildCommand`
  - 타입: `string`
  - 필수: 예
  - 설명: 빌드 스테이지에서 사용할 명령. 가능하면 Python 스크립트 호출 형태를 사용한다.
- `staticAnalysis`
  - 타입: `object`
  - 필수: 예
  - 설명: 정적분석 스테이지의 2개 병렬 Job에서 사용할 명령 집합
- `postBuildTrigger`
  - 타입: `object`
  - 필수: 예
  - 설명: 후속 작업 트리거 설정

#### staticAnalysis

- `customTool`
  - 타입: `object`
  - 필수: 예
  - 설명: 커스텀툴 실행 명령어 셋

#### customTool

- `commands`
  - 타입: `array<string>`
  - 필수: 예
  - 설명: 커스텀툴 실행 순서대로 사용할 명령 목록. 가능하면 Python 스크립트 호출 형태를 사용한다.

#### postBuildTrigger

- `type`
  - 타입: `string`
  - 필수: 예
  - 허용 초안 값: `plan`
- `targetPlanKey`
  - 타입: `string`
  - 필수: 예

### 5. 검증 규칙

- `buildId`는 동일 연도 디렉터리 내에서 유일해야 한다.
- `planKey`는 전체 입력 집합에서 중복되지 않아야 한다.
- `repository.provider`는 생략 시 `bitbucket`으로 간주한다.
- `repository.projectKey`, `repository.repoSlug`는 비어 있으면 안 된다.
- `repository.linkageMode`는 `linked`, `create_if_missing`만 허용한다.
- `repository.branches`는 생략 시 `dev`, `release`, `master`를 사용한다.
- `repository.branches`가 제공되면 `dev`, `release`, `master`를 모두 포함해야 한다.
- `language`와 `compiler`는 지원 가능한 조합 목록에 포함되어야 한다.
- `compiler`는 현재 `vs2013`, `vs2015`, `vs2017`, `vs2019`, `vs2022`, `vs2026`, `node.js`, `python`, `maven`, `keil`, `cmake`만 지원한다.
- `requirements.os`는 `windows` 또는 `linux`만 허용한다.
- `build.prepareCommand`, `build.buildCommand`는 비어 있으면 안 된다.
- `build.staticAnalysis.customTool.commands`는 최소 1개 이상이어야 한다.
- `build.staticAnalysis.customTool.commands` 중 하나는 `analyze {build command}` 패턴을 충족해야 한다.
- 스크립트 명령은 가능하면 Python 실행 형태로 작성해야 한다.
- `postBuildTrigger.type`은 초기 MVP에서 `plan`만 지원한다.
- 연도는 JSON이 아니라 상위 디렉터리명에서 해석한다.
- 스테이지 구조는 JSON이 아니라 공통 워크플로우 템플릿으로 고정한다.

### 6. 내부 모델 매핑 초안

- 디렉터리명 `2026` -> 내부 모델 `year`
- `buildId` -> 내부 모델 `buildId`
- `name` -> 내부 모델 `name`
- `planKey` -> 내부 모델 `planKey`
- `language` -> 내부 모델 `language`
- `compiler` -> 내부 모델 `compiler`
- `repository` -> 내부 모델 `repository`
- `repository.projectKey` + `repository.repoSlug` -> 저장소 식별자
- `repository.linkageMode` -> 저장소 연결 전략 선택값
- `repository.branches[]` -> 브랜치별 연결 및 트리거 정의
- `requirements.os` -> OS capability requirement
- `requirements.extraCapabilities[]` -> 추가 capability requirements
- `build.buildCommand` -> Coverity용 `coverity.yaml`의 `build-command` 값
- `build.staticAnalysis.customTool.commands` -> 커스텀툴 Job 명령 셋
- `build.*` -> 공통 워크플로우 템플릿에 주입할 상세 설정

### 7. Capability 매핑 규칙

- 입력 JSON의 `compiler`와 `requirements.extraCapabilities`는 사용자 친화적인 식별자를 사용한다.
- 생성기는 이를 Bamboo capability key로 변환한다.

#### compiler -> capability key

- `vs2013` -> `system.builder.visualstudio.2013`
- `vs2015` -> `system.builder.visualstudio.2015`
- `vs2017` -> `system.builder.visualstudio.2017`
- `vs2019` -> `system.builder.visualstudio.2019`
- `vs2022` -> `system.builder.visualstudio.2022`
- `vs2026` -> `system.builder.visualstudio.2026`
- `node.js` -> `system.builder.nodejs`
- `python` -> `system.builder.python`
- `maven` -> `system.builder.mvn3.Maven 3`
- `keil` -> `system.builder.keil`
- `cmake` -> `system.builder.cmake`

#### extra capability -> capability key

- `cuda12.1` -> `system.cuda.12.1`
- `nuget` -> `system.builder.nuget`

### 7. 확장 포인트

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

### 대안 2. JSON에 스테이지 정의까지 모두 포함

- 장점: 플랜 구조를 데이터로 완전히 제어할 수 있다.
- 단점: 모든 플랜이 동일 워크플로우를 사용해야 한다는 요구와 충돌하고 입력이 불필요하게 복잡해진다.

### 대안 3. 모든 빌드를 배열로 묶은 단일 JSON

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
- 공통 워크플로우가 고정되고 JSON이 빌드 상세 정보만 담는다는 규칙이 명시되어 있다.
- 최상위 필수 필드와 하위 객체 구조가 정의되어 있다.
- Coverity와 커스텀툴 명령 구조가 정의되어 있다.
- 검증 규칙과 확장 포인트가 정리되어 있다.
- 검토 가능한 예시 JSON이 포함되어 있다.

## 오픈 이슈

- `repository` 구조를 어디까지 상세화할지 결정 필요
- `planKey` 네이밍 규칙을 별도 제약으로 둘지 결정 필요
- 지원 가능한 `language`와 `compiler` 조합 목록 확정 필요
- 커스텀툴 명령어 셋에서 고정 명령과 사용자 입력 명령의 경계를 어디까지 둘지 결정 필요
- 플랜 변수와 트리거를 1차 범위에 넣을지 결정 필요

## 다음 단계

- 이 스키마 초안을 검토해 필드 추가/삭제 확정
- 예제 JSON 파일 세트 작성
- 검증 규칙을 별도 체크리스트 또는 JSON Schema 문서로 구체화
