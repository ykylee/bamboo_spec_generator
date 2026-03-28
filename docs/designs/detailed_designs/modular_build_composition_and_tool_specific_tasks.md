# Detailed Design: 모듈형 빌드 구성과 CI 도구별 Task 확장

## 문서 메타데이터

- 문서 일자: 2026-03-27
- 문서 유형: Detailed Design
- 관련 요구사항: [../../requirements/issues/STORY-34-modular-build-composition-and-tool-specific-tasks.md](../../requirements/issues/STORY-34-modular-build-composition-and-tool-specific-tasks.md)
- 관련 요구사항: [../../requirements/issues/STORY-12-plan-script-asset-management.md](../../requirements/issues/STORY-12-plan-script-asset-management.md)
- 관련 요구사항: [../../requirements/issues/STORY-32-ci-provider-domain-model.md](../../requirements/issues/STORY-32-ci-provider-domain-model.md)
- 관련 결정사항: [./modular_build_composition_decisions.md](./modular_build_composition_decisions.md)

## 요약

이 문서는 빌드 정의를 `stage -> job -> task` 계층의 모듈 조합으로 재구성하는 상세 설계를 정리한다. 핵심은 공통 조합 구조와 CI 도구별 task 정의를 분리하고, script/python task를 파일 기반 템플릿과 OS별 런처 정책으로 렌더링하며, 정해진 위치의 모듈 정의 파일 자동 로딩과 선언형 자산의 웹 업로드 경로를 수용하는 것이다.

## 배경

- 현재 생성기는 Bamboo 중심의 정적 워크플로우와 스크립트 자산 구조를 가진다.
- Bamboo와 Jenkins는 stage/job/task의 의미와 표현은 비슷하지만 task 실행 단위의 실제 스키마는 크게 다르다.
- 기존 script 자산 구조는 재사용성은 높지만, task 등록 모델과 renderer 확장 경계가 문서로 고정되어 있지 않다.
- 운영자가 코드 수정 없이 새 모듈을 반영하려면 파일 드롭 기반 자동 로딩 규칙이 필요하다.

## 목표

- build definition의 조합 단위를 `stage`, `job`, `task` 모듈로 명확히 정의한다.
- `task`는 CI 도구별 전용 스키마와 renderer를 통해 확장한다.
- script 계열 task는 파일 기반 템플릿으로 관리하고, python task는 OS별 실행 헤더/런처 정책으로 렌더링한다.
- 외부 시스템이 task provider, script template, renderer를 추가할 수 있는 확장 지점을 정의한다.
- stage/job/task 선언형 파일을 정해진 위치에 두면 자동 로딩되는 운영 모델을 정의한다.
- 운영 웹에서 선언형 모듈과 스크립트 자산을 업로드하는 경로를 검토한다.

## 비목표

- Jenkins plugin step 전체 카탈로그의 정식 지원
- Bamboo/Jenkins 원격 서버에 대한 실제 등록 자동화
- Python 본문 자체를 OS별 의미 체계로 자동 변환하는 기능

## 설계안

### 1. 조합 계층

#### 공통 엔터티

- `BuildComposition`
  - 전체 빌드 정의의 루트
- `StageModule`
  - 순서가 있는 상위 실행 그룹
- `JobModule`
  - stage 안에서 실행되는 작업 그룹
- `TaskModule`
  - job 안에서 순차 실행되는 최소 작업 단위

#### 공통 필드

- `id`
- `name`
- `enabled`
- `ci_provider`
- `conditions`
- `metadata`

#### 구조 규칙

- `BuildComposition`은 하나 이상의 `StageModule`을 가진다.
- `StageModule`은 하나 이상의 `JobModule`을 가진다.
- `JobModule`은 순서를 가진 `TaskModule` 목록을 가진다.
- stage와 job은 조합 가능한 선언 모델이며, 개별 구현과 분리된다.

### 2. CI 도구별 task 모델

#### 원칙

- 공통 코어는 task 공통 메타데이터만 가진다.
- 실제 task payload는 provider별 전용 타입으로 분리한다.
- 검증과 렌더링도 provider별 registry를 통해 분리한다.

#### Bamboo task 예시

- `BambooScriptTask`
- `BambooCommandTask`
- `BambooVcsCheckoutTask`
- `BambooArtifactDownloaderTask`
- `BambooInjectVariablesTask`

#### Jenkins task 예시

- `JenkinsShellTask`
- `JenkinsBatchTask`
- `JenkinsPowerShellTask`
- `JenkinsCheckoutStepTask`
- `JenkinsPluginStepTask`

#### 모델 예시

```text
TaskModule
  id
  name
  ci_provider
  task_kind
  provider_payload

BambooScriptTask
  script_mode
  file_path
  interpreter
  environment

JenkinsShellTask
  shell_kind
  file_path
  args
  environment
```

### 3. 등록형 확장 구조

#### 코어 책임

- 조합 파싱
- provider 선택
- schema validation 진입점
- template resolution
- renderer dispatch

#### 확장 책임

- task schema 추가
- task validator 추가
- task renderer 추가
- script template 추가
- OS policy 추가

#### 권장 registry 인터페이스

- `register_stage_module(...)`
- `register_job_module(...)`
- `register_task_provider(provider, task_kind, schema, validator, renderer)`
- `register_script_template(template_id, metadata, resolver)`
- `register_os_policy(runtime_kind, os_name, policy)`

### 4. 파일 기반 모듈 자동 로딩

#### 기본 원칙

- `stage`, `job`, `task`는 정해진 스키마의 선언형 파일로 정의한다.
- 시스템은 정해진 루트 디렉터리 아래의 모듈 정의 파일을 스캔해 registry에 적재한다.
- 유효하지 않은 파일은 전체 로딩을 중단시키기보다 격리하고 오류를 보고한다.

#### 권장 디렉터리 구조

```text
modules/
  stages/
    *.yaml
  jobs/
    *.yaml
  tasks/
    bamboo/
      *.yaml
    jenkins/
      *.yaml
  templates/
    scripts/
      ...
```

#### 파일 공통 필드

- `apiVersion`
- `kind`
- `metadata.id`
- `metadata.name`
- `spec`

#### kind 예시

- `StageModule`
- `JobModule`
- `BambooTaskModule`
- `JenkinsTaskModule`

#### YAML 예시

`modules/stages/prepare.yaml`

```yaml
apiVersion: buildmod/v1alpha1
kind: StageModule
metadata:
  id: prepare
  name: Prepare
spec:
  order: 10
  enabled: true
  jobs:
    - prepare-linux
    - prepare-windows
```

`modules/jobs/prepare-linux.yaml`

```yaml
apiVersion: buildmod/v1alpha1
kind: JobModule
metadata:
  id: prepare-linux
  name: Prepare Linux
spec:
  ciProvider: bamboo
  targetOs: linux
  tasks:
    - bamboo-checkout-default
    - bamboo-prepare-python
```

`modules/tasks/bamboo/bamboo-prepare-python.yaml`

```yaml
apiVersion: buildmod/v1alpha1
kind: BambooTaskModule
metadata:
  id: bamboo-prepare-python
  name: Bamboo Prepare Python
spec:
  taskKind: script
  script:
    runtimeKind: python
    templateId: prepare_build
    outputName: prepare_build.py
    context:
      buildCommandVar: BUILD_COMMAND
      subPathVar: SUB_PATH
```

#### 스키마 원칙

- `metadata.id`는 전역 유일 키로 사용한다.
- `spec` 아래 필드는 kind별 스키마로 검증한다.
- 다른 모듈 참조는 문자열 id로 표현한다.
- 실제 파일명은 id와 다를 수 있지만, 운영 혼선을 줄이기 위해 동일하게 유지하는 것을 권장한다.

#### 자동 로딩 시점

- 프로세스 시작 시 1차 전체 스캔
- 관리자 명시 재로드 API 또는 명령 제공
- 향후 선택 사항으로 파일 변경 감지 기반 hot reload 검토

#### 오류 처리

- 스키마 오류 파일은 `invalid` 상태로 분리
- 중복 id는 로딩 실패로 보고
- 참조 대상이 없는 job/task는 활성화 대상에서 제외
- 운영 UI와 API에서 마지막 로딩 시각, 성공 수, 실패 수, 오류 메시지를 조회 가능하게 한다

#### 로딩 상태 모델

- `ModuleLoadSnapshot`
  - `snapshot_id`
  - `loaded_at`
  - `loaded_by`
  - `status`
  - `module_count`
  - `invalid_count`
- `ModuleLoadEntry`
  - `module_id`
  - `module_kind`
  - `source_path`
  - `content_hash`
  - `status`
  - `error_message`

### 5. script task 템플릿 모델

#### 입력 모델

- `template_id`
- `runtime_kind`
- `context`
- `overlays`
- `output_name`
- `wrapper_policy`

#### 렌더링 순서

1. task가 참조하는 `template_id`를 resolve한다.
2. provider, task kind, compiler, os 기준 overlay를 계산한다.
3. context를 치환해 최종 본문을 만든다.
4. runtime kind에 맞게 파일 헤더, 줄바꿈, wrapper 정책을 적용한다.
5. 생성된 파일 경로를 provider renderer에 전달한다.

#### 템플릿 manifest 예시

```yaml
templateId: prepare_build
runtimeKind: python
entryFile: common/py/prepare_build.py
overlays:
  - match:
      taskId: prepare_build
      os: windows
    file: overlays/task/prepare_build/bat/python_task_launcher.bat
  - match:
      taskId: prepare_build
      os: linux
    file: overlays/task/prepare_build/sh/python_task_launcher.sh
```

### 6. Python task OS 정책

#### 입력 원칙

- Python task는 OS 비종속 Python 본문을 입력으로 가진다.
- 본문은 가능한 한 표준 라이브러리와 상대적으로 이식 가능한 로직으로 작성한다.
- 본문 내부의 OS별 의미 차이는 자동 변환 대상이 아니다.

#### 출력 정책

- Linux/macOS:
  - 기본 확장자 `.py`
  - 기본 shebang `#!/usr/bin/env python3`
  - 필요 시 실행 권한 부여
- Windows:
  - 기본 확장자 `.py`
  - shebang은 `#!python`을 허용하거나 wrapper로 대체
  - `.bat` 또는 동등한 wrapper 생성 가능

#### Bamboo 연결 방식

- Bamboo Linux job:
  - 생성된 `.py` 파일을 `ScriptTask` 또는 launcher script에서 호출
- Bamboo Windows job:
  - `.py` 직접 호출 또는 `.bat` wrapper를 통해 호출

#### Jenkins 연결 방식

- Jenkins Linux:
  - `sh` step에서 `python3 generated.py` 또는 실행 권한 있는 파일 직접 호출
- Jenkins Windows:
  - `bat` 또는 `powershell` step에서 `python generated.py` 호출

#### 주의사항

- shebang, wrapper, 실행 명령, 줄바꿈, 인코딩만 OS 정책으로 바꾼다.
- Python 본문의 경로 구분자, subprocess, 환경 변수 접근은 작성자가 이식성 있게 작성하는 것을 기본 원칙으로 둔다.

### 7. 웹 업로드 검토

#### 권장 범위

- 웹 업로드는 선언형 모듈 정의 파일과 스크립트 템플릿 자산에 한정한다.
- Python renderer, validator, provider 코드 자체의 웹 업로드는 1차 범위에서 제외한다.

#### 이유

- 임의 코드 업로드를 허용하면 서버 코드 실행, 배포 추적, 롤백 통제가 어려워진다.
- 선언형 파일과 자산 업로드만 허용해도 운영 편의성과 확장성 대부분을 확보할 수 있다.

#### 운영 흐름 예시

1. 사용자가 웹에서 stage/job/task YAML과 관련 스크립트 파일을 업로드한다.
2. 백엔드는 스키마 검증과 확장자 정책 검사를 수행한다.
3. 검증 성공 시 관리 디렉터리 또는 버전 저장소에 보관한다.
4. 관리자가 활성화하거나 재로드를 실행하면 registry에 반영한다.
5. 실패 시 오류를 업로드 이력과 함께 보여준다.

#### 운영 API 초안

- `POST /api/v1/admin/modules/uploads`
  - multipart 업로드
  - 대상 유형: `stage`, `job`, `task`, `script_template`
- `POST /api/v1/admin/modules/reload`
  - 현재 관리 디렉터리를 기준으로 재로드 실행
- `GET /api/v1/admin/modules/load-status`
  - 마지막 로딩 결과, 오류 목록, 활성 모듈 수 조회
- `GET /api/v1/admin/modules/`
  - 활성/비활성/오류 모듈 목록 조회
- `POST /api/v1/admin/modules/{moduleId}/activate`
  - 업로드된 모듈 활성화
- `POST /api/v1/admin/modules/{moduleId}/deactivate`
  - 활성 모듈 비활성화

#### UI 흐름 초안

1. 운영 사용자가 `모듈 관리` 화면에서 업로드 유형을 선택한다.
2. YAML 또는 스크립트 파일을 업로드한다.
3. 서버가 즉시 스키마/정책 검증 결과를 보여준다.
4. 사용자가 `활성화` 또는 `보류`를 선택한다.
5. `재로드` 실행 후 결과 패널에서 성공/실패 모듈을 확인한다.

#### 저장 위치 검토

- 옵션 A: 서버 파일시스템 관리 디렉터리
  - 장점: 현재 파일 스캔 구조와 잘 맞음
  - 단점: 다중 인스턴스 환경에서 동기화 필요
- 옵션 B: DB blob 또는 object storage
  - 장점: 업로드 이력과 권한 통제가 쉬움
  - 단점: 런타임 스캔 전에 파일 materialize 단계가 필요

#### 보안 제약

- 허용 확장자 화이트리스트 적용
- 파일 크기 제한 적용
- 업로드 사용자/시각/해시 기록
- 활성화 전 검토 상태 분리
- 운영 환경에서는 즉시 반영보다 승인 후 반영을 기본값으로 고려

### 8. 디렉터리 구조 제안

```text
modules/
  stages/
  jobs/
  tasks/
    bamboo/
    jenkins/
managed_modules/
  uploads/
    stages/
    jobs/
    tasks/
      bamboo/
      jenkins/
  active/
    stages/
    jobs/
    tasks/
      bamboo/
      jenkins/
  archive/
    2026/
scripts/plan_tasks/
  common/
    py/
    sh/
    bat/
    ps1/
  fragments/
    py/
    sh/
    bat/
    ps1/
  overlays/
    provider/
      bamboo/
      jenkins/
    compiler/
    task/
  manifests/
    task_templates.yaml
```

### 9. 검증 전략

#### 조합 검증

- stage id 중복 금지
- job id 중복 금지
- task id 중복 금지
- stage 안에 최소 1개 이상의 job 필요
- job 안에 최소 1개 이상의 task 필요
- stage의 `order` 중복 허용 여부는 정책으로 두되, 동일 값일 때는 `metadata.id` 순으로 안정 정렬
- 순환 참조 금지

#### provider 검증

- `ci_provider`와 task payload 타입 일치 여부
- provider가 지원하지 않는 task kind 차단
- provider 전용 필수 필드 검증
- provider별 허용 OS와 runtime kind 조합 검증

#### runtime 검증

- script template 존재 여부
- os policy 등록 여부
- python task의 허용 런처 정책 여부
- 업로드 자산의 허용 확장자/크기/해시 검증
- 로딩 루트 아래 파일 간 참조 일관성 검증
- 같은 출력 파일명을 생성하는 task 충돌 검증

### 10. 단계별 구현 제안

1. 모듈 정의 파일 스키마와 디렉터리 규칙을 확정한다.
2. 기존 고정 workflow 생성 로직을 `StageModule`/`JobModule` 선언 모델로 분리한다.
3. Bamboo task를 provider registry 기반으로 옮긴다.
4. script task 입력을 `template_id + context` 모델로 정리한다.
5. Python task의 OS policy와 wrapper 생성기를 도입한다.
6. Jenkins task registry와 renderer 초안을 추가한다.
7. 관리자 재로드 API와 로딩 상태 조회 기능을 추가한다.
8. 선언형 모듈/자산 웹 업로드를 검토하고 저장 전략을 확정한다.
9. 외부 시스템용 등록 인터페이스와 compatibility check를 정의한다.

## 수용 기준

- 공통 조합 계층과 provider별 task payload 분리가 문서화된다.
- 정해진 경로의 모듈 정의 파일 자동 로딩 규칙이 정의된다.
- script/python task의 template 기반 렌더링 절차가 정의된다.
- Linux와 Windows에서의 Python 실행 헤더/런처 정책이 정의된다.
- 외부 확장을 위한 registry 인터페이스가 정의된다.
- 선언형 파일과 스크립트 자산에 대한 웹 업로드 검토 방향이 정의된다.

## 오픈 이슈

- 모듈 정의 파일 포맷을 YAML로 둘지 JSON으로 둘지 결정 필요
- 자동 로딩을 hot reload까지 포함할지 관리자 재로드까지만 지원할지 결정 필요
- 업로드 자산 저장 위치를 관리 디렉터리, DB, object storage 중 무엇으로 둘지 결정 필요
- Jenkins plugin step task를 whitelist 방식으로 제한할지 완전 passthrough를 허용할지 결정 필요
