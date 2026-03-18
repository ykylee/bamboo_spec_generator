# STORY-19 Django 운영 백엔드 및 Admin 기반 관리 구조 도입

## 유형

- Story

## 구현 상태

- 부분 구현

## 우선순위

- 높음

## 요약

PostgreSQL 기반 운영 데이터를 관리하기 위한 Django 백엔드를 도입하고, 초기 운영 화면은 Django Admin을 활용할 수 있어야 한다.

## 배경

- 빌드 정의, 프로젝트/저장소 메타데이터, 버전, 실행 이력은 운영 관점에서 조회와 관리가 필요하다.
- 단순 DB 스키마만으로는 운영자가 데이터를 다루기 어렵다.
- Django는 ORM, migration, admin을 함께 제공하므로 초기 운영 백엔드 기반으로 적합하다.

## 설명

운영 계층은 생성기 본체와 분리된 Django 백엔드로 구현한다. 이 백엔드는 PostgreSQL을 사용하고, 설계된 주요 엔터티를 ORM 모델로 표현해야 한다. 또한 초기 운영 관리 기능은 Django Admin에서 수행할 수 있어야 한다. 생성기 본체는 이 백엔드와 책임을 분리한 채로 유지한다. 현재 코드에는 Django 프로젝트 구조, ORM 모델, migration, Admin, SQLite/PostgreSQL 스위치 설정, 개발용 DB 초기화 명령이 추가되었다.

## 범위

### 포함

- Django 프로젝트/앱 초기 구조
- PostgreSQL 연동 설정
- 주요 엔터티 ORM 모델
- migration 관리
- Django Admin 등록 및 기본 조회/관리 화면

### 제외

- 외부 공개 API 상세 구현
- 고급 사용자용 커스텀 프론트엔드

## 수용 기준

- Django 기반 운영 백엔드 구조가 정의된다.
- PostgreSQL 기반 ORM 모델이 정의된다.
- Django Admin에서 주요 엔터티를 조회 가능하다.
- 생성기 본체와 운영 백엔드의 책임 경계가 문서화된다.
- 현재 기준 Django 프로젝트, ORM 모델, migration, Admin 스캐폴딩이 코드에 반영되어 있다.

## 오픈 이슈

- Django 프로젝트를 단일 저장소 내부에 둘지 별도 서비스로 분리할지 결정 필요
- Admin만으로 충분한 초기 운영 범위를 어디까지 볼지 결정 필요
