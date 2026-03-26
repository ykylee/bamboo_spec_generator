# 저장소 연결 지원 방식 설계

## 요약

이 문서는 운영 시스템이 지원할 저장소 연결 방식을 정의한다. 핵심 방향은 저장소 연결을 하나의 enum으로 단순화하지 않고, `repository_type`과 `repository_provider`를 분리해 Git/SVN 같은 버전관리 방식과 GitHub/Bitbucket/Gitea 같은 호스팅 제공자를 독립적으로 다루는 것이다.

## 배경

- 현재 시스템은 Bamboo Specs 생성과 운영 메타데이터 관리 흐름이 Git 중심으로 구성되어 있다.
- 그러나 운영 환경에서는 self-hosted Git, Bitbucket, GitHub, Gitea, 그리고 일부 SVN 저장소를 함께 다룰 가능성이 있다.
- `bitbucket`, `github`, `svn` 같은 값을 하나의 필드에 혼합하면 버전관리 방식과 호스팅 제공자가 섞여 모델 확장성과 검증 규칙이 불안정해진다.

## 목표

- 저장소 연결 방식을 명확한 내부 모델로 정의한다.
- Git 계열 호스팅 제공자와 SVN 계열 연결 방식을 일관된 UI/API 구조로 수용한다.
- Bamboo/Jenkins 연동 시 저장소 메타데이터를 provider-aware하게 처리할 수 있는 기반을 만든다.

## 비목표

- 이번 설계에서 SVN 기반 실제 빌드 생성/브랜치 전략까지 구현하지는 않는다.
- GitHub, Bitbucket, Gitea 각각의 webhook, app installation, OAuth 상세 플로우를 이번 문서에서 확정하지는 않는다.
- 저장소별 인증 방식의 최종 UI/비밀정보 저장 정책까지 모두 확정하지는 않는다.

## 설계안

### 1. 모델 분리 원칙

- `repository_type`
  - 저장소의 버전관리 방식을 나타낸다.
  - 후보: `git`, `svn`

- `repository_provider`
  - 저장소가 어느 제품/호스팅 계층에 속하는지 나타낸다.
  - 후보: `generic_git`, `github`, `bitbucket`, `gitea`, `generic_svn`

이 구조를 사용하면 다음 조합이 가능하다.

- `git + generic_git`
- `git + github`
- `git + bitbucket`
- `git + gitea`
- `svn + generic_svn`

### 2. 허용 조합

초기 허용 규칙은 다음과 같이 둔다.

| repository_type | repository_provider | 허용 여부 | 비고 |
| --- | --- | --- | --- |
| `git` | `generic_git` | 허용 | 사내 Git 서버/범용 Git URL |
| `git` | `github` | 허용 | GitHub Cloud/Enterprise 포함 가능 |
| `git` | `bitbucket` | 허용 | 현재 Bamboo 친화 경로 |
| `git` | `gitea` | 허용 | self-hosted Git 계열 |
| `svn` | `generic_svn` | 허용 | SVN 기본 연결 |
| `svn` | `github/bitbucket/gitea` | 비허용 | 의미 충돌 |
| `git` | `generic_svn` | 비허용 | 의미 충돌 |

### 3. 권장 데이터 필드

저장소 메타데이터는 최소한 아래 수준을 갖는 것을 권장한다.

- `repository_type`
- `repository_provider`
- `repo_slug`
- `repo_key`
- `repo_url`
- `web_url`
- `default_branch`
- `credential_ref`
- `clone_protocol`
- `is_self_hosted`

보조 규칙:

- `svn` 저장소는 `default_branch`를 optional로 본다.
- `github`, `bitbucket`, `gitea`는 현재 단계에서 `repository_type=git`만 허용한다.
- `generic_git`는 제품 미지정 Git 서버를 수용하는 fallback provider로 둔다.
- `generic_svn`는 SVN 서버 일반형을 의미한다.

### 4. UI 입력 원칙

프로젝트 등록/수정 UI에서는 저장소 입력을 다음 두 단계로 나눈다.

1. `저장소 타입`
   - `git`
   - `svn`

2. `저장소 제공자`
   - `generic_git`, `github`, `bitbucket`, `gitea`
   - `repository_type=svn`일 때는 `generic_svn`만 선택 가능

UI 규칙:

- `git` 선택 시 Git 전용 예시 placeholder를 노출한다.
- `svn` 선택 시 branch/slug 중심 문구 대신 repository URL 중심 문구를 노출한다.
- Bamboo 전용 `linked/create_if_missing` 연결 방식은 Git + Bitbucket 조합에서 우선 지원 대상으로 본다.
- GitHub/Gitea/Git generic은 Bamboo에서는 당장은 `linked`보다 clone URL 기반 또는 별도 adapter 경로를 우선 검토한다.

### 5. 1차/2차 도입 범위

#### 1차 지원

- `git + generic_git`
- `git + github`
- `git + bitbucket`
- `git + gitea`

이유:

- 현재 빌드 생성기와 운영 콘솔의 주요 흐름이 Git 기반이다.
- Bamboo/Jenkins 모두 Git 저장소를 기본 전제로 확장하기 쉽다.
- provider별 메타데이터 차이는 URL/clone/auth 처리 계층에서 흡수 가능하다.

#### 2차 지원

- `svn + generic_svn`

이유:

- SVN은 branch/tag/trunk 해석, checkout 전략, 인증, 작업 경로 규칙이 Git과 다르다.
- Bamboo Specs/Jenkins job bootstrap에서 SVN용 태스크/checkout 전략을 별도 검토해야 한다.
- 따라서 메타데이터 모델은 지금 수용하되, 실제 생성/연동은 2차 과제로 분리하는 편이 안전하다.

### 6. Bamboo/Jenkins 관점의 영향

#### Bamboo

- 현재 가장 자연스러운 조합은 `git + bitbucket`
- `linked/create_if_missing`는 Bitbucket 계열 저장소에서 우선 지원
- `github`, `gitea`, `generic_git`는 Bamboo linked repository와 직접 1:1 대응되지 않을 수 있으므로 provider adapter 또는 clone URL 기반 정책이 필요
- `svn`은 Bamboo checkout task와 브랜치 전략을 별도 검토해야 함

#### Jenkins

- Jenkins는 상대적으로 provider 중립적인 job 구성이 가능하다
- `git` 계열은 provider별 URL/credential 정책만 정리되면 수용 가능
- `svn`도 이론상 수용 가능하지만 job template과 checkout 스텝 분기가 필요하다

## 대안

### 대안 1. 단일 enum에 모두 포함

예: `bitbucket`, `github`, `gitea`, `git`, `svn`

문제:

- `svn`은 VCS이고 `bitbucket/github/gitea`는 호스팅 제공자라 의미 계층이 다르다.
- 검증 규칙과 UI 분기가 필드 하나에 과도하게 몰린다.

### 대안 2. 현재처럼 `repo_type`만 두고 Git provider는 URL로 추론

장점:

- 모델이 단순하다.

문제:

- GitHub/Bitbucket/Gitea별 정책 차이를 명시적으로 다루기 어렵다.
- UI와 운영 설정에서 provider별 옵션을 제어하기 어렵다.

## 영향 범위

- `Repository` 또는 동등한 저장소 메타데이터 모델
- 프로젝트 등록/수정 UI
- 프로젝트/저장소 API schema
- Bamboo/Jenkins provider별 저장소 adapter 계층
- 정의 생성 시 repository descriptor 직렬화 로직

## 수용 기준

- 저장소 메타데이터는 `repository_type`과 `repository_provider`를 구분해 표현할 수 있어야 한다.
- GitHub/Bitbucket/Gitea는 `git` 계열 provider로 표현 가능해야 한다.
- SVN은 `svn + generic_svn` 조합으로 표현 가능해야 한다.
- UI/API는 허용되지 않는 조합을 검증할 수 있어야 한다.
- 1차 구현 범위와 2차 구현 범위를 문서 수준에서 구분할 수 있어야 한다.

## 오픈 이슈

- `repository_provider`를 기존 `repo_type` 필드 확장으로 흡수할지, 신규 필드로 분리할지 migration 전략을 정해야 한다.
- GitHub/Gitea를 Bamboo에서 어떤 repository linkage 정책으로 지원할지 추가 설계가 필요하다.
- SVN 저장소의 branch/tag/trunk 표현을 내부 모델에서 어떻게 표준화할지 정해야 한다.
- provider별 인증 정보 저장 정책을 시스템 설정과 어떻게 연결할지 정해야 한다.
