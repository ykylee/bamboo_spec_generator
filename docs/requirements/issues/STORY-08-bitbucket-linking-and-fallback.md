# STORY-08 Bitbucket 저장소 연결 및 미등록 저장소 대응 설계

## 유형

- Story

## 구현 상태

- 부분 구현
- `projectKey/repoSlug` 기반 linked repository 이름 생성은 구현되었다.
- 미등록 저장소 대응과 `create_if_missing` 실질 동작은 아직 미구현이다.

## 우선순위

- 높음

## 다음 구현 포인트

- `linkageMode=create_if_missing`일 때 생성 결과에 남길 메타데이터 형식 확정
- 생성기에서 `linked`와 `create_if_missing`를 실제로 분기 처리

## 요약

Bitbucket 저장소를 Bamboo 플랜에 연결하는 방식과 Bamboo 미등록 저장소 대응 전략을 설계한다.

## 배경

실제 운영 환경에서는 일부 저장소가 Bamboo에 linked repository로 사전 등록되어 있을 수 있고, 일부는 그렇지 않을 수 있다. 두 경우를 모두 다루지 못하면 생성 결과를 바로 운영에 적용하기 어렵다.

## 설명

시스템은 `projectKey`, `repoSlug`를 기반으로 Bitbucket 저장소를 식별하고, Bamboo 플랜 생성 시 적절한 저장소 연결 구성을 만들어야 한다. 사전 등록 저장소는 재사용 가능해야 하며, 미등록 저장소는 후속 등록 지점이 드러나거나 가능한 경우 직접 연결 구성이 생성되어야 한다.

## 수용 기준

- 사전 등록 저장소와 미등록 저장소의 처리 흐름이 문서화된다.
- 두 경우 모두 생성 결과에서 저장소 식별 정보가 추적 가능하다.
- 미등록 저장소 대응 시 운영자가 후속 작업 지점을 확인할 수 있다.
- 동일 입력에 대해 반복 실행 시 동일한 저장소 연결 구성이 생성된다.

## 의존성

- STORY-07 저장소 연결용 JSON 필드 및 검증 규칙 정의

## 오픈 이슈

- Bamboo Specs API에서 미등록 저장소를 어느 수준까지 직접 정의할 수 있는지 확인 필요
- Bitbucket 연동 대상이 Server/Data Center인지 Cloud인지 확정 필요
