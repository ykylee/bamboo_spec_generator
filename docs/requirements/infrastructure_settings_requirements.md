#QV|# 운영 설정 요구사항: 연관 인프라별 구역 관리

## 문서 메타데이터

- 문서 일자: 2026-03-25
- 문서 유형: 요구사항
- 상태: 초안

---

## 1. 개요

현재 운영 설정 페이지(/settings/coverity/)에서 Coverity, Bamboo, Repository 설정을 하나의 폼에서 관리하고 있다. 사용자가 구역을 명확히 구분할 수 있도록 UI를 개선하고자 한다.

---

## 2. 현재 인프라 설정 키

| 구역 | 설정 키 | 설명 |
|------|---------|------|
| **Coverity** | `coverity.connect.url` | Coverity Connect 서버 URL |
| **Coverity** | `coverity.connect.on_new_cert` | 새 인증서 정책 |
| **Coverity** | `coverity.commit.enabled` | Commit 분석 활성화 |
| **Bamboo** | `bamboo.server.url` | Bamboo 서버 URL |
| **Repository** | `repository.git.clone_url_template` | Git 클론 URL 템플릿 |
| **Repository** | `repository.linkage_mode` | 저장소 연결 모드 |
| **Jenkins** | `jenkins.server.url` | Jenkins 서버 URL |

---

## 3. 요구사항

### FR-OPS-01: 설정 페이지 구역 분리

- 설정 페이지를 다음 구역으로 구분해야 한다:
  - **CI 서버** 구역: Bamboo, Jenkins 서버 URL
  - **정적 분석** 구역: Coverity 설정
  - **저장소** 구역: Git 클론 URL 템플릿, 연결 모드
- 각 구역은 시각적으로 구분되는 섹션으로 표시해야 한다.
- 구역마다 제목을 명확히 표시해야 한다.

### FR-OPS-02: 구역별 설정 입력

**CI 서버 구역:**
- Bamboo 서버 URL 입력 필드
- Jenkins 서버 URL 입력 필드

**정적 분석 구역:**
- Coverity Connect URL 입력 필드
- 인증서 정책 선택 (trust/reject)
- Commit 활성화 체크박스

**저장소 구역:**
- Git 클론 URL 템플릿 입력 필드
- 저장소 연결 모드 선택 (linked/create_if_missing)

---

## 4. 구현 방향

- 기존 `/settings/coverity/` 페이지 유지
- HTML/CSS로 구역 시각화 (구분선 또는 카드 형태)
- 기존 폼 구조 활용, 구역 제목만 추가

---

## 5. 다음 단계

1. 현재 템플릿 파일 확인
2. 구역 구분 HTML 구조 설계
3. CSS 스타일 추가