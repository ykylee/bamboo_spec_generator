use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    pub id: Uuid,
    pub jira_project_key: String,
    pub bitbucket_project_key: String,
    pub ci_provider: String,
    pub display_name: String,
    pub description: Option<String>,
    pub representative_repo_slug: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectRepository {
    pub id: Uuid,
    pub project_id: Uuid,
    pub repo_slug: String,
    pub coverity_project: Option<String>,
    pub coverity_stream: Option<String>,
    pub is_representative: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuildUnit {
    pub id: Uuid,
    pub project_id: Uuid,
    pub build_name: String,
    pub build_type: String,
    pub runtime_stack: Option<String>,
    pub ci_provider: String,
    pub plan_key: Option<String>,
    pub job_path: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}
