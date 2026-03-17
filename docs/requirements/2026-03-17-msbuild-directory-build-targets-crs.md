# CRS: MSBuild 플랜용 Directory.Build.targets 사전 생성

## 문서 메타데이터

- 문서 일자: 2026-03-17
- 문서 유형: CRS
- 상태: 초안
- 대상 프로젝트: `bamboo_spec_generator`
- Jira 전환 대상: Story 초안

## 요약

MSBuild를 사용하는 Bamboo 플랜은 실제 MSBuild 호출이 일어나는 모든 단계에서 실행 직전에 `Directory.Build.targets` 파일을 생성해, 빌드 최적화 옵션으로 인해 발생하는 오류를 사전에 방지할 수 있어야 한다. 또한 MSBuild가 Visual Studio C++ 도구체인을 정상적으로 찾을 수 있도록, 에이전트 환경변수에 저장된 `VsDevCmd.bat`, `vcvarsall.bat`, `vcvars64.bat` 등의 경로를 기준으로 환경 설정을 로드할 수 있어야 한다.

## 배경

- Visual Studio/MSBuild 기반 프로젝트는 환경에 따라 최적화 관련 옵션이 빌드 실패를 유발할 수 있다.
- 동일한 소스라도 Bamboo 에이전트의 설정 차이로 인해 `Optimization`, `WholeProgramOptimization`, `LinkTimeCodeGeneration` 같은 옵션이 문제를 일으킬 수 있다.
- Visual Studio C++ 빌드는 `PATH`, `INCLUDE`, `LIB`, `LIBPATH` 등 다수의 환경 변수에 의존하므로, 에이전트가 적절한 개발자 명령 프롬프트 환경을 갖추지 않으면 `msbuild` 호출 자체가 불안정할 수 있다.
- 플랜마다 수동으로 우회 설정을 넣으면 운영 편차가 커지므로, 생성기에서 일관된 사전 대응 규칙을 제공하는 편이 적절하다.

## 문제

현재 MSBuild 기반 플랜은 빌드 단계뿐 아니라 정적 분석 등 MSBuild가 재호출되는 단계 전반에서 최적화 옵션을 강제로 무력화하는 공통 장치가 없다. 또한 Bamboo 에이전트가 Visual Studio C++ 빌드 환경 변수 없이 `msbuild`를 호출하면 툴체인과 SDK 탐색이 실패할 수 있다. 이 경우 운영자는 플랜별로 개별 우회 작업과 환경 보정 작업을 반복해야 한다.

## 범위

### 포함 범위

- MSBuild 실행 여부를 판단하는 규칙 정의
- MSBuild 플랜에서 각 MSBuild 호출 전에 `Directory.Build.targets`를 생성하는 요구사항 정의
- 생성 파일에 포함할 최소 무력화 대상 옵션 정의
- 공통 워크플로우의 빌드 단계와 정적 분석 단계 등 MSBuild가 수행될 수 있는 구간에 적용하는 방식 정의
- Visual Studio C++ 빌드 환경 설정 로드 필요 여부 및 표준 방식 정의
- 입력 JSON 또는 내부 모델에서 이 동작을 표현할 필요가 있는지 검토

### 제외 범위

- 프로젝트별 세부 `.vcxproj` 수정 자동화
- 모든 MSBuild 속성에 대한 완전한 호환성 보장
- Visual Studio IDE 내부 설정 자체를 변경하는 기능

## 요구사항

### 기능 요구사항

- 시스템은 대상 빌드가 MSBuild 기반 플랜인지 식별할 수 있어야 한다.
- 시스템은 MSBuild 기반 플랜에 대해 실제 MSBuild 호출이 일어나는 각 단계의 실행 전에 `Directory.Build.targets` 파일을 생성해야 한다.
- 시스템은 생성 파일에 최적화 옵션을 무력화하는 최소 설정을 포함해야 한다.
- 시스템은 생성된 `Directory.Build.targets`가 빌드 작업 디렉터리에서 MSBuild에 의해 자동 적용되도록 배치해야 한다.
- 시스템은 해당 동작이 MSBuild 기반 플랜에만 적용되도록 해야 한다.
- 시스템은 MSBuild 기반 플랜에 대해 Visual Studio C++ 빌드에 필요한 환경 변수가 준비되었는지 보장해야 한다.
- 시스템은 환경 보장 방식을 에이전트 환경변수 기반으로 정의해야 한다.
- 시스템은 compiler 버전에 따라 `VS2013_ENV`, `VS2015_ENV`, `VS2017_ENV`, `VS2019_ENV`, `VS2022_ENV`, `VS2026_ENV` 같은 이름의 환경변수를 참조할 수 있어야 한다.
- 시스템은 해당 환경변수에 저장된 `VsDevCmd.bat`, `vcvarsall.bat`, `vcvars64.bat` 등의 경로를 호출해 Visual Studio 빌드 환경을 로드할 수 있어야 한다.

### 비기능 요구사항

- 사전 생성 로직은 Windows 에이전트에서 안정적으로 동작해야 한다.
- 생성 방식은 가능하면 shell 전용 스크립트보다 Python 호출 기반으로 유지해야 한다.
- 동일 입력에 대해 생성 결과가 일관되어야 한다.
- Visual Studio 설치 경로와 SDK 버전 차이가 있더라도 에이전트 환경변수만 교체해 운영 표준 방식으로 환경 설정을 재현할 수 있어야 한다.

## 수용 기준

- MSBuild 플랜으로 판별된 빌드 정의에 대해 `Directory.Build.targets` 생성 규칙이 정의되어 있다.
- 생성 파일에 `Optimization`, `WholeProgramOptimization`, `LinkTimeCodeGeneration` 무력화 설정이 포함된다고 명시되어 있다.
- `Directory.Build.targets`가 빌드 단계와 정적 분석 단계 등 실제 MSBuild 명령 실행 전에 생성된다고 정의되어 있다.
- 비 MSBuild 플랜에는 해당 로직이 적용되지 않는다고 정의되어 있다.
- 운영자가 플랜별 수동 우회 설정 없이 공통 생성 로직으로 동일한 대응을 사용할 수 있다고 정의되어 있다.
- MSBuild 플랜에 필요한 Visual Studio 개발자 명령 프롬프트 환경을 에이전트 환경변수 기반으로 보장하는 방식이 정의되어 있다.
- `VS2022_ENV` 같은 compiler별 환경변수 명명 규칙이 정의되어 있다.

## 제약/가정

- `Directory.Build.targets`는 MSBuild 평가 전에 작업 디렉터리 기준으로 생성되어야 대상 솔루션/프로젝트 빌드에 적용될 수 있다고 가정한다.
- 무력화 대상 옵션의 최종 목록은 실제 운영 중 추가 조정이 필요할 수 있다.
- 일부 프로젝트는 추가적인 개별 속성 무력화가 필요할 수 있다.
- 초기 범위에서는 파일 생성 시점과 기본 내용 정의에 집중하고, 사용자별 커스터마이징은 후속 범위로 둔다.
- Bamboo 에이전트에는 Visual Studio 2022 C++ 도구와 Windows SDK가 설치되어 있거나, 그에 준하는 표준 빌드 환경이 이미 준비되어 있다고 가정한다.
- Bamboo 에이전트에는 각 Visual Studio 버전에 대응하는 환경 설정 스크립트 경로가 적절한 `VSxxxx_ENV` 환경변수로 등록되어 있다고 가정한다.

## 오픈 이슈

- MSBuild 판별 기준을 `compiler`, `buildCommand`, 또는 둘 다로 볼지 최종 확정이 필요하다.
- `Directory.Build.targets` 내용을 고정 템플릿으로 둘지, JSON 입력으로 일부 제어 가능하게 할지 결정이 필요하다.
- 파일 생성 위치를 항상 작업 루트로 둘지, 솔루션 파일 기준 경로로 조정할지 검토가 필요하다.
- 커스텀 정적 분석 도구가 내부적으로 별도 MSBuild를 호출하는 경우에도 같은 환경 설정을 어떻게 강제할지 결정이 필요하다.
- `VSxxxx_ENV` 값에 배치 파일 경로만 둘지, 추가 인자까지 허용할지 결정이 필요하다.

## 다음 단계

- Story 문서로 세분화해 구현 단위와 수용 기준을 구체화한다.
- JSON 스키마/생성기/테스트에 필요한 반영 범위를 정리한다.
- 운영에서 실제로 문제가 되는 최적화 옵션 조합을 추가 수집해 템플릿 보완 여부를 판단한다.
