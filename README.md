# bamboo_spec_generator

`bamboo_spec_generator`는 연도별 JSON 빌드 정의를 읽어 Bamboo Specs Java 코드를 생성하는 로컬 실행형 샘플 생성기입니다. 여러 빌드 플랜을 하나의 `bamboo-specs/` Maven 프로젝트 형태로 만들고, 이를 Bamboo Repository Stored Specs 또는 수동 Java Specs 배포 흐름에서 사용할 수 있도록 하는 것을 목표로 합니다.

현재 저장소에는 요구사항 문서, 설계 문서, JSON 스키마 초안, Python 기반 초기 생성기 구현이 포함되어 있습니다.

## 현재 상태

- 입력 JSON 파싱, 검증, 내부 모델 변환, 산출물 생성 흐름이 구현되어 있습니다.
- 입력 루트 기본값은 `build_info_json/`, 출력 루트 기본값은 `bamboo-specs/`입니다.
- 생성 결과에는 Bamboo Specs Java 소스, `pom.xml`, 빌드별 Coverity 설정, 빌드별 렌더링 스크립트와 OS별 실행 보조 자산이 포함되며, Task 실행 로직은 Specs의 `ScriptTask.inlineBody(...)`에 직접 포함됩니다.
- Python 기반 Task 스크립트 원본은 `scripts/plan_tasks/common/py/` 아래의 자산 파일로 분리되어 있으며, 생성 시 빌드 정의에 맞게 렌더링됩니다.
- OS별 Python wrapper도 `scripts/plan_tasks/common/sh/`, `scripts/plan_tasks/common/bat/` 자산으로 분리되어 있습니다.
- 테스트는 `unittest` 기반으로 일부 포함되어 있습니다.
- 실제 Bamboo 서버 import 및 실행까지는 아직 검증되지 않았습니다.

## 저장소 구조

- 입력 JSON: `build_info_json/<year>/<buildId>.json`
- 생성기 코드: `src/bamboo_spec_generator/`
- 스크립트 자산: `scripts/plan_tasks/`
- 테스트: `tests/`
- 문서: `docs/`
- 생성 결과 기본 경로: `bamboo-specs/`

## 공통 워크플로우

모든 플랜은 동일한 워크플로우를 사용합니다.

1. `Prepare`
2. `Build`
3. `Static Analysis`
4. `Trigger Follow-up`

`Static Analysis` 스테이지는 두 개의 병렬 Job으로 구성됩니다.

- `Coverity Scan`
- `Custom Analysis`

입력 JSON은 스테이지 구조 자체를 정의하지 않고, 이 공통 워크플로우 안에서 달라지는 빌드 상세 설정만 제공합니다.

## 입력 JSON

입력 JSON은 다음 블록으로 구성됩니다.

- 기본 식별 정보: `buildId`, `name`, `planKey`, `description`
- 빌드 환경 정보: `language`, `compiler`
- 저장소 정보: `repository`
- 에이전트 요구사항: `requirements`
- 빌드 상세 설정: `build`

`build` 블록의 주요 필드는 다음과 같습니다.

- `subPath`: 저장소 루트 대신 작업 기준으로 사용할 하위 경로
- `prepareCommand`: 준비 단계에서 실행할 실제 명령
- `buildCommand`: 빌드 단계에서 실행할 실제 명령
- `staticAnalysis.customTool.commands`: 커스텀 분석 단계 명령 목록
- `runtimeRequirements.commands`: 에이전트에 있어야 하는 실행 명령 목록
- `runtimeRequirements.envVars`: 에이전트에 있어야 하는 환경변수 목록
- `postBuildTrigger`: 후속 플랜 트리거 설정

중요한 점은 `prepareCommand`와 `buildCommand`가 생성기가 내부적으로 쓰는 스크립트 경로가 아니라, 실제 프로젝트에서 수행할 원본 준비/빌드 명령이라는 점입니다.

예제 파일:

- [sample-app-api.json](./build_info_json/2026/sample-app-api.json)
- [sample-app-web.json](./build_info_json/2026/sample-app-web.json)
- [sample-app-mfc.json](./build_info_json/2026/sample-app-mfc.json)

현재 샘플은 다음 시나리오를 기준으로 정리되어 있습니다.

- `sample-app-api`: Linux 에이전트에서 Maven으로 빌드하는 Java API 서비스
- `sample-app-web`: Linux 에이전트에서 `npm`으로 빌드하는 Node.js 웹 애플리케이션
- `sample-app-mfc`: Windows 에이전트에서 `nuget restore` 후 `msbuild`를 수행하는 Visual Studio 2022 기반 MFC 애플리케이션

## Capability 처리

입력 JSON은 사용자 친화적인 compiler/capability 이름을 사용하고, 생성기 내부에서 Bamboo capability key로 변환합니다.

예:

- `maven` -> `system.builder.mvn3.Maven 3`
- `node.js` -> `system.builder.nodejs`
- `vs2022` -> `system.builder.visualstudio.2022`
- `nuget` -> `system.builder.nuget`

MSBuild 기반 플랜은 생성된 inline Python 코드에서 실제 MSBuild 호출 직전에 `Directory.Build.targets`를 생성해 최적화 관련 옵션을 무력화합니다. 또한 Visual Studio 환경 설정 스크립트 경로는 `VS2022_ENV` 같은 에이전트 환경변수로 관리합니다.

`subPath`가 지정된 경우 준비, 빌드, 정적 분석 스크립트는 모두 해당 하위 경로를 작업 디렉터리로 사용합니다. MSBuild 플랜에서는 `Directory.Build.targets`도 같은 위치에 생성합니다.

모든 생성 플랜은 작업 실행을 위해 Bamboo 에이전트에 Python 실행 환경이 있다고 가정하며, 생성된 Specs에는 `system.builder.python` requirement가 함께 포함됩니다.

입력 JSON의 `runtimeRequirements`는 Bamboo capability로 직접 강제하기 어려운 런타임 전제 조건을 명시적으로 남기기 위한 블록입니다. 예를 들어 `coverity`, `custom-tool`, `trigger-plan`, `VS2022_ENV` 같은 항목을 각 빌드 단위로 기록합니다.

## 스크립트 자산 관리

플랜 Task 스크립트의 Python 원본은 저장소에서 직접 편집 가능한 자산 파일로 관리합니다.

- 공통 Python 템플릿: `scripts/plan_tasks/common/py/`
- OS별 wrapper 자산: `scripts/plan_tasks/common/sh/`, `scripts/plan_tasks/common/bat/`
- 공통 실행 프래그먼트: `scripts/plan_tasks/fragments/py/`
- 환경별 오버레이: `scripts/plan_tasks/overlays/`
  - compiler별 오버레이: `scripts/plan_tasks/overlays/compiler/`
  - task별 launcher 오버레이: `scripts/plan_tasks/overlays/task/`
- 자산 선택: `src/bamboo_spec_generator/script_assets.py`
- 자산 렌더링: `src/bamboo_spec_generator/script_renderer.py`
- Java wrapper 자산 선택: `src/bamboo_spec_generator/java_assets.py`

현재는 공통 템플릿에 프래그먼트와 오버레이를 조합한 뒤, 빌드 정의 값으로 렌더링해 최종 결과를 Java `ScriptTask.inlineBody(...)`에 넣는 방식입니다. 즉 실행 모델은 유지하면서 스크립트 원본 관리 구조를 먼저 분리했습니다.

## 구현 구조

생성기 코드는 `src/bamboo_spec_generator/` 아래에 있습니다.

- `cli.py`: 실행 진입점
- `parser.py`: JSON 입력 탐색 및 파싱
- `validator.py`: 입력 검증
- `model.py`: 내부 데이터 모델
- `script_assets.py`: Task 스크립트 자산 선택 및 로딩
- `script_renderer.py`: Task 스크립트 렌더링
- `java_assets.py`: OS별 Java wrapper 자산 선택
- `generator.py`: Java Specs 코드와 Coverity 설정 생성
- `writer.py`: 출력 파일 기록

## 요구 환경

로컬에서 생성기를 실행하고 생성 결과를 검토하려면 다음 도구가 필요합니다.

- Python 3
- Java 17 이상
- Maven 3.9 이상
- Bamboo 에이전트에 등록된 Python capability (`system.builder.python`)

권장 확인 명령:

```bash
python3 --version
java -version
mvn -version
```

Windows `cmd` 기준:

```bat
python --version
java -version
mvn -version
```

MSBuild 샘플까지 함께 검토하려면 Windows 에이전트 또는 유사 환경에 다음 준비가 필요합니다.

- Visual Studio 2022 또는 Build Tools 설치
- `VS2022_ENV` 환경변수에 `VsDevCmd.bat` 또는 `vcvars*.bat` 경로 등록
- Bamboo capability에 Visual Studio 및 `nuget` capability 등록
- Bamboo capability에 Python capability 등록

예:

```bat
set VS2022_ENV=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat
```

## 실행 방법

기본 입력 루트는 `build_info_json/`, 기본 출력 루트는 `bamboo-specs/`입니다.

생성기 실행:

```bash
PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli
```

Windows `cmd` 기준:

```bat
set PYTHONPATH=.
python -m src.bamboo_spec_generator.cli
```

출력 경로를 직접 지정하려면:

```bash
PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli --output-root bamboo-specs
```

Windows `cmd` 기준:

```bat
set PYTHONPATH=.
python -m src.bamboo_spec_generator.cli --output-root bamboo-specs
```

입력 루트를 직접 지정하려면:

```bash
PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli --input-root build_info_json
```

실행이 성공하면 처리한 JSON 파일 수와 생성된 파일 수를 출력합니다.

## 생성 결과

생성 결과는 기본적으로 `bamboo-specs/` 아래에 기록되며, 주요 구조는 다음과 같습니다.

```text
bamboo-specs/
├── README.md
├── pom.xml
├── coverity/
│   └── <buildId>/coverity.yaml
├── scripts/
│   ├── index.json
│   ├── index-summary.txt
│   ├── compare-report.txt
│   ├── compare-report.json
│   └── <buildId>/
│       ├── README.md
│       ├── manifest.json
│       ├── bundle-summary.txt
│       ├── prepare_build.py
│       ├── prepare_build.sh or prepare_build.bat
│       ├── run_build.py
│       ├── run_coverity.py
│       ├── run_custom_analysis.py
│       └── trigger_follow_up.py
└── src/main/java/com/example/specs/generated/
    ├── AllPlansRegistry.java
    ├── SpecsPublisher.java
    └── <BuildId>PlanSpecs.java
```

이 출력 디렉터리는 Bamboo Repository Stored Specs로 올리거나, Maven 기반 Java Specs 프로젝트로 수동 배포하는 용도로 사용할 수 있습니다. `scripts/<buildId>/` 아래 파일은 생성 시점에 렌더링된 최종 스크립트와 OS별 실행 보조 자산이므로, Java inline body와 함께 검토용 산출물로 활용할 수 있습니다. 각 빌드 디렉터리의 `README.md`에는 task별 파일 매핑과 런타임 요구사항이 정리되고, `manifest.json`에는 같은 정보를 구조화된 형태로 기록합니다. 또한 각 task가 어떤 자산 템플릿과 오버레이에서 생성되었는지, 렌더링 결과 체크섬이 무엇인지, 언제 어떤 생성기 버전과 git revision으로 만들어졌는지도 함께 포함합니다. `bundle-summary.txt`에는 같은 내용을 diff 친화적인 평문 형식과 bundle fingerprint로 기록합니다. 루트의 `scripts/index.json`과 `scripts/index-summary.txt`에는 전체 build bundle 목록과 fingerprint 인덱스가 기록되고, `scripts/compare-report.txt`와 `scripts/compare-report.json`에는 이전 생성본과 비교한 added/changed/removed/unchanged 상태가 content checksum 기준으로 정리됩니다. bundle이 `changed`인 경우에는 어떤 task의 Python 스크립트 또는 launcher가 바뀌었는지, 어떤 asset source 경로가 달라졌는지, build 수준 런타임 요구사항이 바뀌었는지도 세부 항목으로 함께 기록됩니다.

## 생성 결과 검증

생성된 Bamboo Specs 프로젝트가 컴파일되는지 확인하려면:

```bash
cd bamboo-specs
mvn -q -DskipTests compile
```

Windows `cmd` 기준:

```bat
cd bamboo-specs
mvn -q -DskipTests compile
```

## 수동 배포

생성 결과에는 `SpecsPublisher.java`가 포함됩니다. 환경변수를 설정한 뒤 Maven으로 publish 진입점을 실행할 수 있습니다.

기본 생성 `pom.xml`에는 Bamboo Specs 내부 백그라운드 스레드와 `exec-maven-plugin` 종료 처리 충돌을 피하기 위해 `cleanupDaemonThreads=false`가 포함됩니다.

필수 환경변수:

- `BAMBOO_URL`: Bamboo 서버 URL
- `BAMBOO_TOKEN_FILE`: Bamboo 토큰 파일 경로. 생략 시 `.credentials`

토큰 파일 형식:

- `FileTokenCredentials`를 사용하므로 파일은 일반 텍스트 토큰만 두는 것이 아니라 Java properties 형식이어야 합니다.
- 최소 형식은 `token=<personal-access-token>` 한 줄입니다.

실제 publish 전 선행조건:

- Bamboo 서버 버전과 생성된 `pom.xml`의 Bamboo Specs 버전이 일치하거나 호환되어야 합니다.
- 샘플 JSON처럼 `linked` 저장소를 참조하는 경우 Bamboo에 같은 이름의 Linked Repository가 미리 있어야 합니다.
- 샘플 입력 기준 필요한 저장소 이름은 `SAMPLE/sample-app-api`, `SAMPLE/sample-app-web`, `SAMPLE/sample-app-mfc` 입니다.
- `BAMBOO_URL`은 Bamboo context path를 포함한 URL을 사용해야 합니다. 예를 들어 `/bamboo`로 서비스 중이면 `https://host.example.com/bamboo` 형태여야 합니다.

Linked Repository 확인 방법:

```bash
curl --silent --user 'admin:password' \
  'https://atlassian.ddn777.synology.me/bamboo/rest/api/latest/repository?searchTerm=SAMPLE/'
```

응답의 `searchResults`에 필요한 저장소 이름이 모두 있으면 됩니다.

없을 때 등록 방법:

1. Bamboo 관리자 화면에서 `Administration` -> `Linked repositories` -> `Add repository` 로 이동합니다.
2. 저장소 타입으로 `Git`을 선택합니다.
3. 아래 값을 저장소마다 각각 입력합니다.

- Name: `SAMPLE/sample-app-api`
- Name: `SAMPLE/sample-app-web`
- Name: `SAMPLE/sample-app-mfc`
- Repository URL: 실제 Git 저장소 URL
- Authentication type: 저장소 환경에 맞는 값
- Web repository: 필요 없으면 `None`

테스트 환경에서는 위 3개 이름을 가진 Git Linked Repository를 먼저 만든 뒤 publish를 진행했습니다.

프로젝트가 아직 없다면 먼저 생성:

```bash
curl --silent --user 'admin:password' \
  --header 'Accept: application/json' \
  --header 'Content-Type: application/json' \
  --data '{"key":"SAMPLE","name":"Sample"}' \
  'https://atlassian.ddn777.synology.me/bamboo/rest/api/latest/project'
```

예:

```bash
cd bamboo-specs
mvn -q exec:java -Dexec.args="--dry-run"
mvn -q exec:java -Dexec.args="--print-plans"
export BAMBOO_URL=https://bamboo.example.com
export BAMBOO_TOKEN_FILE=/path/to/.credentials
mvn -q exec:java
```

실제 검증한 순차 실행 예:

```bash
python3 -m src.bamboo_spec_generator.cli --output-root bamboo-specs
cd bamboo-specs
mvn -q -DskipTests compile
printf '%s\n' 'token=<personal-access-token>' > .credentials
chmod 600 .credentials
export BAMBOO_URL=https://atlassian.ddn777.synology.me/bamboo
export BAMBOO_TOKEN_FILE=.credentials
mvn -q exec:java
```

실행 결과 확인 예:

```bash
curl --silent --user 'admin:password' \
  'https://atlassian.ddn777.synology.me/bamboo/rest/api/latest/project/Y2026?expand=plans'
```

위 조회에서 샘플 기준으로 `Y2026-SAMPAPI`, `Y2026-SAMPMFC`, `Y2026-SAMPWEB` 플랜이 보이면 publish가 완료된 것입니다.

Windows `cmd` 기준:

```bat
cd bamboo-specs
mvn -q exec:java -Dexec.args="--dry-run"
mvn -q exec:java -Dexec.args="--print-plans"
set BAMBOO_URL=https://bamboo.example.com
set BAMBOO_TOKEN_FILE=C:\path\to\.credentials
mvn -q exec:java
```

Repository Stored Specs로 사용할 경우에는 생성된 `bamboo-specs/` 디렉터리를 Bamboo가 읽는 저장소에 포함시키고, Bamboo에서 해당 저장소를 Specs 저장소로 등록하면 됩니다.

## Bamboo 사전 점검

실제 Bamboo 서버에 올리기 전에는 최소한 다음 항목을 확인해야 합니다.

- Bamboo 서버 버전이 생성된 `pom.xml`의 Bamboo Specs 버전과 호환되는지 확인
- Bamboo Linked Repository 이름이 `projectKey/repoSlug` 규칙과 일치하는지 확인
- Personal Access Token 파일이 `token=...` 형식인지 확인
- 대상 에이전트에 `system.builder.python` capability가 등록되어 있는지 확인
- 빌드 명령이 사용하는 `mvn`, `npm`, `nuget`, `msbuild` 같은 도구가 에이전트에 설치되어 있는지 확인
- 정적 분석/후속 단계가 사용하는 `coverity`, `custom-tool`, `trigger-plan` 명령이 에이전트에서 실행 가능한지 확인
- Windows 플랜의 경우 `VS2022_ENV` 같은 환경변수가 올바른 Visual Studio 환경 스크립트를 가리키는지 확인
- Repository Stored Specs로 쓸 경우 `bamboo-specs/` 디렉터리가 Bamboo가 읽는 저장소에 실제로 포함되는지 확인

## 테스트

테스트 실행:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```

Windows `cmd` 기준:

```bat
set PYTHONPATH=.
python -m unittest discover -s tests
```

## 문서

핵심 문서:

- [CRS](./docs/requirements/2026-03-17-bamboo-spec-generator-crs.md)
- [SRS](./docs/requirements/2026-03-17-bamboo-spec-generator-srs.md)
- [초기 설계](./docs/designs/2026-03-17-initial-design.md)
- [JSON 스키마 설계](./docs/designs/2026-03-17-json-schema-design.md)
- [저장소 연결 설계](./docs/designs/2026-03-17-repository-linking-design.md)
- [플랜 스크립트 관리 CRS](./docs/requirements/2026-03-18-plan-script-management-crs.md)
- [플랜 스크립트 관리 설계](./docs/designs/2026-03-18-plan-script-management-design.md)
- [플랜 스크립트 구현 계획](./docs/designs/2026-03-18-plan-script-management-implementation-plan.md)
- [이슈 분해](./docs/requirements/issues/2026-03-17-issue-breakdown.md)

## 작업 흐름

기본 작업 흐름은 다음과 같습니다.

1. 최신 `dev`에서 작업 브랜치 생성
2. 가능하면 `codex/{브랜치명}` 형식 사용
3. 구현과 문서 변경을 함께 반영
4. 1차 PR은 `dev` 대상으로 생성
5. `dev` 검증 후 `main`으로 승격

## 현재 한계

- 실제 Bamboo 서버에 import하여 플랜이 정상 반영되는지까지는 아직 검증하지 않았습니다.
- capability 명명 규칙은 Bamboo 운영 환경마다 차이가 있을 수 있어 추가 매핑이 필요할 수 있습니다.
- Linked Repository 이름은 현재 `projectKey/repoSlug` 규칙을 전제로 생성합니다.
- 생성 스크립트의 명령 실행 모델은 현재 `subprocess.run()` 기반의 단순 구조입니다.
