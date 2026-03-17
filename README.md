# bamboo_spec_generator

`bamboo_spec_generator`는 연도별 JSON 빌드 정의를 읽어 Bamboo Specs Java 코드와 보조 실행 파일을 생성하는 프로젝트입니다. 목표는 여러 빌드 플랜을 하나의 `bamboo-specs/` 저장소 형태로 생성하고, Bamboo가 해당 저장소를 스캔해 전체 플랜 변경을 반영할 수 있게 하는 것입니다.

현재 저장소에는 요구사항 문서, 초기 설계 문서, JSON 스키마 초안, 그리고 이를 바탕으로 한 샘플 생성기 구현이 포함되어 있습니다.

## 현재 상태

- 요구사항 문서와 SRS가 정리되어 있습니다.
- 공통 워크플로우 기반 JSON 스키마 초안이 있습니다.
- Python 기반 샘플 생성기가 구현되어 있습니다.
- 샘플 생성기는 `build_info_json/`을 읽어 `bamboo-specs/`를 생성합니다.
- 생성 결과는 Bamboo Specs Maven 프로젝트, Java Specs 클래스, Coverity 설정 파일, Python 실행 스크립트를 포함합니다.

## 목표 구조

- 입력: `build_info_json/<year>/<buildId>.json`
- 출력: `bamboo-specs/`
- 출력물 구성:
  - Bamboo Specs Java 파일
  - Bamboo Specs Maven `pom.xml`
  - 빌드별 Python 스크립트
  - 빌드별 `coverity.yaml`

## 공통 워크플로우

모든 플랜은 동일한 워크플로우를 사용합니다.

1. `Prepare`
2. `Build`
3. `Static Analysis`
4. `Trigger Follow-up`

`Static Analysis` 스테이지는 2개의 병렬 Job으로 구성됩니다.

- Job 1: `Coverity Scan`
- Job 2: `Custom Analysis`

## 입력 JSON 개요

현재 샘플 JSON은 다음 정보를 포함합니다.

- 기본 식별 정보: `buildId`, `name`, `planKey`
- 빌드 환경 정보: `language`, `compiler`
- 저장소 정보: `repository`
- Capability 요구사항: `requirements`
- 빌드 상세 설정: `build`

`build` 블록에는 필요 시 `subPath`를 지정해 저장소 루트가 아닌 하위 디렉터리를 작업 기준 경로로 사용할 수 있습니다. 이 필드는 MSBuild 전용이 아니라 모든 빌드 유형에서 공통으로 사용할 수 있습니다.

예제 파일:

- [sample-app-api.json](./build_info_json/2026/sample-app-api.json)
- [sample-app-web.json](./build_info_json/2026/sample-app-web.json)
- [sample-app-mfc.json](./build_info_json/2026/sample-app-mfc.json)

## Capability 처리

입력 JSON은 사용자 친화적인 compiler/capability 이름을 사용하고, 생성기 내부에서 Bamboo capability key로 변환합니다.

예:

- `maven` -> `system.builder.mvn3.Maven 3`
- `node.js` -> `system.builder.nodejs`
- `vs2022` -> `system.builder.visualstudio.2022`
- `cuda12.1` -> `system.cuda.12.1`
- `nuget` -> `system.builder.nuget`

`msbuild`가 수행되는 플랜은 생성된 `run_build.py`에서 빌드 직전에 `Directory.Build.targets`를 생성해 최적화 관련 옵션을 무력화하도록 구성합니다.
또한 Visual Studio 환경 설정 스크립트 경로는 에이전트 환경변수로 관리하며, 예를 들어 `vs2022` 컴파일러는 `VS2022_ENV`에 `VsDevCmd.bat` 또는 `vcvars*.bat` 경로를 설정해 사용합니다. 해당 규칙은 `prepare_build.py`, `run_build.py`, `run_custom_analysis.py` 같은 MSBuild 관련 생성 스크립트에 공통 적용됩니다.
`subPath`가 지정된 경우 준비, 빌드, 정적 분석 스크립트는 모두 해당 하위 경로를 작업 디렉터리로 사용합니다. MSBuild 플랜에서는 `Directory.Build.targets`도 같은 위치에 생성합니다.

## 샘플 생성기 구조

샘플 생성기 코드는 `src/bamboo_spec_generator/` 아래에 있습니다.

- `cli.py`: 실행 진입점
- `parser.py`: JSON 입력 파싱
- `validator.py`: 입력 검증
- `model.py`: 내부 데이터 모델
- `generator.py`: Java, Python 스크립트, Coverity 설정 생성
- `writer.py`: 출력 파일 기록

## 초기 셋업

이 프로젝트를 로컬에서 실행하고 생성 결과를 검증하려면 다음 도구가 필요합니다.

- Python 3
- Java 17 이상
- Maven 3.9 이상

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

MSBuild 기반 샘플까지 함께 검토할 경우 Bamboo Windows 에이전트에는 추가로 다음 준비가 필요합니다.

- Visual Studio C++ 빌드 도구 또는 Visual Studio 2022 설치
- `VS2022_ENV` 같은 환경변수에 `VsDevCmd.bat` 또는 `vcvars*.bat` 경로 등록
- Bamboo capability에 Visual Studio 및 추가 capability 등록

예:

```bash
set VS2022_ENV=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat
```

## 실행 가이드

기본 출력 경로는 루트의 `bamboo-specs/` 이며, 이 디렉터리는 Bamboo Repository Stored Specs에 올릴 수 있는 Maven 프로젝트 형태로 생성됩니다.

### 1. 생성기 실행

```bash
PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli
```

Windows `cmd` 기준:

```bat
set PYTHONPATH=.
python -m src.bamboo_spec_generator.cli
```

출력 경로를 바꾸려면:

```bash
PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli --output-root bamboo-specs
```

Windows `cmd` 기준:

```bat
set PYTHONPATH=.
python -m src.bamboo_spec_generator.cli --output-root bamboo-specs
```

### 2. 생성 결과 컴파일 검증

생성된 Bamboo Specs 프로젝트가 실제 Java/Maven 프로젝트로 컴파일되는지 확인하려면:

```bash
cd bamboo-specs
mvn -q -DskipTests compile
```

Windows `cmd` 기준:

```bat
cd bamboo-specs
mvn -q -DskipTests compile
```

### 3. Bamboo Specs 수동 배포

생성 결과에는 `SpecsPublisher.java`가 포함되며, 환경변수를 설정한 뒤 Maven으로 publish 진입점을 실행할 수 있습니다.

필수 환경변수:

- `BAMBOO_URL`: Bamboo 서버 URL
- `BAMBOO_TOKEN_FILE`: Bamboo 토큰 파일 경로. 생략 시 `.credentials`

예:

```bash
export BAMBOO_URL=https://bamboo.example.com
export BAMBOO_TOKEN_FILE=/path/to/.credentials
cd bamboo-specs
mvn -q -Ppublish-specs bamboo-specs-runner:run
```

Windows `cmd` 기준:

```bat
set BAMBOO_URL=https://bamboo.example.com
set BAMBOO_TOKEN_FILE=C:\path\to\.credentials
cd bamboo-specs
mvn -q -Ppublish-specs bamboo-specs-runner:run
```

### 4. Repository Stored Specs 사용

수동 publish 대신 Repository Stored Specs로 사용할 경우에는 생성된 `bamboo-specs/` 디렉터리를 Bamboo가 읽는 저장소에 포함시키고, Bamboo 쪽에서 해당 저장소를 Specs 저장소로 등록합니다.

## 테스트

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```

Windows `cmd` 기준:

```bat
set PYTHONPATH=.
python -m unittest discover -s tests
```

## 생성 결과 예시

생성 결과 예시 경로:

- [pom.xml](./bamboo-specs/pom.xml)
- [AllPlansRegistry.java](./bamboo-specs/src/main/java/com/example/specs/generated/AllPlansRegistry.java)
- [SampleAppApiPlanSpecs.java](./bamboo-specs/src/main/java/com/example/specs/generated/SampleAppApiPlanSpecs.java)
- [SampleAppWebPlanSpecs.java](./bamboo-specs/src/main/java/com/example/specs/generated/SampleAppWebPlanSpecs.java)
- [SpecsPublisher.java](./bamboo-specs/src/main/java/com/example/specs/generated/SpecsPublisher.java)
- [sample-app-api coverity.yaml](./bamboo-specs/coverity/sample-app-api/coverity.yaml)
- [sample-app-api prepare_build.py](./bamboo-specs/scripts/generated/sample-app-api/prepare_build.py)

## 문서

핵심 문서:

- [CRS](./docs/requirements/2026-03-17-bamboo-spec-generator-crs.md)
- [SRS](./docs/requirements/2026-03-17-bamboo-spec-generator-srs.md)
- [초기 설계](./docs/designs/2026-03-17-initial-design.md)
- [JSON 스키마 설계](./docs/designs/2026-03-17-json-schema-design.md)
- [저장소 연결 설계](./docs/designs/2026-03-17-repository-linking-design.md)
- [이슈 분해](./docs/requirements/issues/2026-03-17-issue-breakdown.md)

## 작업 흐름

기본 작업 흐름은 다음과 같습니다.

1. 작업 브랜치 생성: `codex/{브랜치명}`
2. 구현 및 문서 반영
3. 1차 PR 대상: `dev`
4. `dev`에서 검증
5. 검증 후 `main`으로 승격

## 현재 한계

- 생성 결과는 실제 Bamboo Specs Maven 프로젝트 구조를 따르며 로컬 `mvn compile`까지 검증했습니다. 다만 실제 Bamboo 서버 import와 실행까지는 아직 검증하지 않았습니다.
- Python 실행 스크립트는 `subprocess.run()` 기반이며, 더 엄격한 명령 모델로 추가 개선 여지가 있습니다.
- 실제 Bamboo 인스턴스 capability naming convention은 환경별 차이가 있을 수 있으므로 추가 매핑 정리가 필요할 수 있습니다.
- Linked Repository 이름은 현재 `projectKey/repoSlug` 규칙을 전제로 생성하므로, Bamboo 환경과 다르면 조정이 필요합니다.
