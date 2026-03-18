# STORY-10 MSBuild 플랜용 Directory.Build.targets 사전 생성 지원

## 유형

- Story

## 구현 상태

- 구현됨
- MSBuild 기반 스크립트 자산과 pre-run overlay를 통해 `Directory.Build.targets` 생성과 Visual Studio 환경 변수 로드가 반영되어 있다.

## 우선순위

- 유지

## 요약

MSBuild 기반 Bamboo 플랜은 MSBuild가 수행되는 각 단계 실행 전에 `Directory.Build.targets` 파일을 생성해 최적화 관련 옵션을 무력화할 수 있어야 하며, Visual Studio 환경 설정 경로는 `VS2022_ENV` 같은 에이전트 환경변수를 통해 관리할 수 있어야 한다.

## 배경

Visual Studio/MSBuild 기반 프로젝트는 빌드 최적화 옵션 때문에 Bamboo 환경에서 예기치 않은 오류가 발생할 수 있다. 이 문제를 플랜별 수동 조치에 맡기면 운영 편차가 커지므로, 생성기가 공통 우회 규칙을 제공하는 방식이 필요하다.

## 설명

시스템은 입력 빌드 정의가 MSBuild 기반인지 식별해야 한다. MSBuild 플랜으로 판단되면 빌드 단계뿐 아니라 정적 분석 등 실제로 MSBuild가 수행되는 각 단계의 실행 전에 `Directory.Build.targets`를 생성하고, 그 안에 `Optimization`, `WholeProgramOptimization`, `LinkTimeCodeGeneration` 등을 무력화하는 기본 설정을 포함해야 한다. 또한 Visual Studio C++ 도구체인이 필요한 플랜에 대해서는 compiler 버전에 대응하는 `VSxxxx_ENV` 환경변수에서 `VsDevCmd.bat`, `vcvarsall.bat`, `vcvars64.bat` 등의 경로를 읽어 필요한 환경 변수를 보장해야 한다. 해당 동작은 비 MSBuild 플랜에는 적용되지 않아야 하며, 가능하면 기존 Python 스크립트 기반 실행 흐름 안에서 처리해야 한다.

## 수용 기준

- MSBuild 플랜 판별 규칙이 정의되어 있다.
- MSBuild 플랜에서 빌드 단계와 정적 분석 단계 등 각 MSBuild 실행 직전에 `Directory.Build.targets`를 생성한다고 정의되어 있다.
- 생성 파일에 `Optimization`, `WholeProgramOptimization`, `LinkTimeCodeGeneration` 무력화 설정이 포함된다고 정의되어 있다.
- 비 MSBuild 플랜에는 해당 사전 생성 로직이 적용되지 않는다고 정의되어 있다.
- MSBuild 플랜에 필요한 Visual Studio 개발자 명령 프롬프트 환경을 `VSxxxx_ENV` 규칙으로 보장하는 방식이 정의되어 있다.
- 관련 생성 로직을 검증할 자동 테스트 또는 동등 수준의 검증 방법이 정의되어 있다.

## 의존성

- STORY-03 Bamboo Specs Java 코드 생성 기능 구현
- STORY-06 공통 워크플로우 템플릿 및 빌드 상세 입력 구조 정의

## 오픈 이슈

- 무력화할 속성 목록을 고정 최소 집합으로 둘지 확장 가능 구조로 둘지 결정 필요
- `Directory.Build.targets` 생성 위치를 작업 루트 외 다른 경로로 지원할 필요가 있는지 검토 필요
- `VSxxxx_ENV` 값에 배치 파일 경로만 둘지, 추가 인자까지 허용할지 결정 필요
