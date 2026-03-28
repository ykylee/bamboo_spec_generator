# API 엔드포인트 매핑: Django → Rust

## 문서 개요

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-03-28 |
| 목적 | Django API → Rust API 매핑 기록 |

---

## 1. Projects API

### 1.1 목록 조회

**Django:**
```
GET /api/v1/projects/
```

**Rust:**
```
GET /api/v1/projects/
```

**Query Parameters:**
| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `ci_provider` | string | No | CI 제공자 필터 (bamboo, jenkins) |

**Response:**
```json
{
  "projects": [
    {
      "jira_project_key": "SAMPLE",
      "bitbucket_project_key": "SAMPLE",
      "ci_provider": "bamboo",
      "display_name": "Sample Project",
      "build_count": 5,
      "repository_count": 3
    }
  ]
}
```

---

### 1.2 프로젝트 생성

**Django:**
```
POST /api/v1/projects/
```

**Rust:**
```
POST /api/v1/projects/
```

**Request Body:**
```json
{
  "jira_project_key": "SAMPLE",
  "bitbucket_project_key": "SAMPLE",
  "ci_provider": "bamboo",
  "display_name": "Sample Project",
  "description": "Sample project description"
}
```

---

### 1.3 상세 조회

**Django:**
```
GET /api/v1/projects/{project_key}
```

**Rust:**
```
GET /api/v1/projects/{project_key}
```

---

### 1.4 프로젝트 수정

**Django:**
```
PUT /api/v1/projects/{project_key}
```

**Rust:**
```
PUT /api/v1/projects/{project_key}
```

---

## 2. Build Plans API

### 2.1 활성 정의 조회

**Django:**
```
GET /api/v1/build-plans/{plan_key}/active-definition
```

**Rust:**
```
GET /api/v1/build-plans/{plan_key}/active-definition
```

**Response:**
```json
{
  "plan_key": "SAMPAPI",
  "build_id": "sample-app-api",
  "year": "2026",
  "definition": {
    "buildId": "sample-app-api",
    "name": "Sample App API",
    "planKey": "SAMPAPI",
    ...
  }
}
```

---

### 2.2 준비 컨텍스트 조회

**Django:**
```
GET /api/v1/build-plans/{plan_key}/prepare-context
```

**Rust:**
```
GET /api/v1/build-plans/{plan_key}/prepare-context
```

---

### 2.3 실행 이력 조회

**Django:**
```
GET /api/v1/build-plans/{plan_key}/executions
```

**Rust:**
```
GET /api/v1/build-plans/{plan_key}/executions
```

---

## 3. Modules API

### 3.1 목록 조회

**Django:**
```
GET /api/v1/admin/modules/
```

**Rust:**
```
GET /api/v1/modules/
```

---

### 3.2 업로드

**Django:**
```
POST /api/v1/admin/modules/uploads
```

**Rust:**
```
POST /api/v1/modules/upload
```

---

### 3.3 재로드

**Django:**
```
POST /api/v1/admin/modules/reload
```

**Rust:**
```
POST /api/v1/modules/reload
```

---

### 3.4 로드 상태 조회

**Django:**
```
GET /api/v1/admin/modules/load-status
```

**Rust:**
```
GET /api/v1/modules/load-status
```

---

## 4. Settings API

### 4.1 설정 목록 조회

**Django:**
```
GET /api/v1/system-settings/
```

**Rust:**
```
GET /api/v1/settings/
```

---

### 4.2 설정 수정

**Django:**
```
PUT /api/v1/system-settings/{key}
```

**Rust:**
```
PUT /api/v1/settings/{key}
```

---

## 5. Jenkin Jobs API

### 5.1 목록 조회

**Django:**
```
GET /api/v1/jenkins-jobs/
```

**Rust:**
```
GET /api/v1/jenkins-jobs/
```

---

### 5.2 상세 조회

**Django:**
```
GET /api/v1/jenkins-jobs/{job_name}
```

**Rust:**
```
GET /api/v1/jenkins-jobs/{job_name}
```

---

### 5.3 빌드 이력 조회

**Django:**
```
GET /api/v1/jenkins-jobs/{job_name}/builds
```

**Rust:**
```
GET /api/v1/jenkins-jobs/{job_name}/builds
```

---

## 6. 매핑 요약표

| 번호 | Django 엔드포인트 | Rust 엔드포인트 | 상태 |
|------|-----------------|----------------|------|
| 1 | GET /api/v1/projects/ | GET /api/v1/projects/ | ✅ |
| 2 | POST /api/v1/projects/ | POST /api/v1/projects/ | ✅ |
| 3 | GET /api/v1/projects/{key} | GET /api/v1/projects/{key} | ✅ |
| 4 | PUT /api/v1/projects/{key} | PUT /api/v1/projects/{key} | ✅ |
| 5 | GET /api/v1/build-plans/{plan_key}/active-definition | 同 | ✅ |
| 6 | GET /api/v1/build-plans/{plan_key}/prepare-context | 同 | ✅ |
| 7 | GET /api/v1/build-plans/{plan_key}/executions | 同 | ✅ |
| 8 | GET /api/v1/admin/modules/ | GET /api/v1/modules/ | ✅ |
| 9 | POST /api/v1/admin/modules/uploads | POST /api/v1/modules/upload | ✅ |
| 10 | POST /api/v1/admin/modules/reload | POST /api/v1/modules/reload | ✅ |
| 11 | GET /api/v1/admin/modules/load-status | GET /api/v1/modules/load-status | ✅ |
| 12 | GET /api/v1/system-settings/ | GET /api/v1/settings/ | ✅ |
| 13 | PUT /api/v1/system-settings/{key} | PUT /api/v1/settings/{key} | ✅ |
| 14 | GET /api/v1/jenkins-jobs/ | GET /api/v1/jenkins-jobs/ | ✅ |
| 15 | GET /api/v1/jenkins-jobs/{job_name} | GET /api/v1/jenkins-jobs/{job_name} | ✅ |
| 16 | GET /api/v1/jenkins-jobs/{job_name}/builds | GET /api/v1/jenkins-jobs/{job_name}/builds | ✅ |

---

## 7. 참고

- 기존 Django 라우터: `backend/apps/api/router.py`
- 기존 Django 라우트: `backend/apps/api/routers/`
- 기존 Django 스키마: `backend/apps/api/schemas/`
