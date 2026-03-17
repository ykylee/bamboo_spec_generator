# bamboo_spec_generator

`bamboo_spec_generator`는 연도별 JSON 빌드 정의를 읽어 Bamboo Specs Java 코드와 보조 실행 파일을 생성하는 로컬 실행형 샘플 생성기입니다. 여러 빌드 플랜을 하나의 `bamboo-specs/` Maven 프로젝트 형태로 만들고, 이를 Bamboo Repository Stored Specs 또는 수동 Java Specs 배포 흐름에서 사용할 수 있도록 하는 것을 목표로 합니다.

현재 저장소에는 요구사항 문서, 설계 문서, JSON 스키마 초안, Python 기반 초기 생성기 구현이 포함되어 있습니다.

## 현재 상태

- 입력 JSON 파싱, 검증, 내부 모델 변환, 산출물 생성 흐름이 구현되어 있습니다.
- 입력 루트 기본값은 `build_info_json/`, 출력 루트 기본값은 `bamboo-specs/`입니다.
- 생성 결과에는 Bamboo Specs Java 소스, `pom.xml`, 빌드별 Coverity 설정, 빌드별 Python 실행 스크립트가 포함됩니다.
- 테스트는 `unittest` 기반으로 일부 포함되어 있습니다.
- 실제 Bamboo 서버 import 및 실행까지는 아직 검증되지 않았습니다.

## 저장소 구조

- 입력 JSON: `build_info_json/<year>/<buildId>.json`
- 생성기 코드: `src/bamboo_spec_generator/`
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

MSBuild 기반 플랜은 생성된 Python 스크립트에서 실제 MSBuild 호출 직전에 `Directory.Build.targets`를 생성해 최적화 관련 옵션을 무력화합니다. 또한 Visual Studio 환경 설정 스크립트 경로는 `VS2022_ENV` 같은 에이전트 환경변수로 관리합니다.

`subPath`가 지정된 경우 준비, 빌드, 정적 분석 스크립트는 모두 해당 하위 경로를 작업 디렉터리로 사용합니다. MSBuild 플랜에서는 `Directory.Build.targets`도 같은 위치에 생성합니다.

## 구현 구조

생성기 코드는 `src/bamboo_spec_generator/` 아래에 있습니다.

- `cli.py`: 실행 진입점
- `parser.py`: JSON 입력 탐색 및 파싱
- `validator.py`: 입력 검증
- `model.py`: 내부 데이터 모델
- `generator.py`: Java, Python 스크립트, Coverity 설정 생성
- `writer.py`: 출력 파일 기록

## 요구 환경

로컬에서 생성기를 실행하고 생성 결과를 검토하려면 다음 도구가 필요합니다.

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

MSBuild 샘플까지 함께 검토하려면 Windows 에이전트 또는 유사 환경에 다음 준비가 필요합니다.

- Visual Studio 2022 또는 Build Tools 설치
- `VS2022_ENV` 환경변수에 `VsDevCmd.bat` 또는 `vcvars*.bat` 경로 등록
- Bamboo capability에 Visual Studio 및 `nuget` capability 등록

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
│   └── generated/<buildId>/
│       ├── prepare_build.py
│       ├── run_build.py
│       ├── run_coverity.py
│       ├── run_custom_analysis.py
│       └── trigger_follow_up.py
└── src/main/java/com/example/specs/generated/
    ├── AllPlansRegistry.java
    ├── SpecsPublisher.java
    └── <BuildId>PlanSpecs.java
```

이 출력 디렉터리는 Bamboo Repository Stored Specs로 올리거나, Maven 기반 Java Specs 프로젝트로 수동 배포하는 용도로 사용할 수 있습니다.

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

필수 환경변수:

- `BAMBOO_URL`: Bamboo 서버 URL
- `BAMBOO_TOKEN_FILE`: Bamboo 토큰 파일 경로. 생략 시 `.credentials`

예:

```bash
export BAMBOO_URL=https://bamboo.example.com
export BAMBOO_TOKEN_FILE=/path/to/.credentials
cd bamboo-specs
mvn -q exec:java
```

Windows `cmd` 기준:

```bat
set BAMBOO_URL=https://bamboo.example.com
set BAMBOO_TOKEN_FILE=C:\path\to\.credentials
cd bamboo-specs
mvn -q exec:java
```

Repository Stored Specs로 사용할 경우에는 생성된 `bamboo-specs/` 디렉터리를 Bamboo가 읽는 저장소에 포함시키고, Bamboo에서 해당 저장소를 Specs 저장소로 등록하면 됩니다.

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
