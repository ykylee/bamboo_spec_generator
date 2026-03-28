use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuildPlanDefinition {
    pub id: Uuid,
    pub build_unit_id: Uuid,
    pub project_id: Uuid,
    pub year: String,
    pub source_kind: String,
    pub definition_json: serde_json::Value,
    pub definition_hash: String,
    pub is_active: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuildVersion {
    pub id: Uuid,
    pub build_unit_id: Uuid,
    pub version_text: String,
    pub major: i32,
    pub minor: i32,
    pub patch: i32,
    pub branch_kind: String,
    pub commit_hash: String,
    pub is_latest: bool,
    pub created_at: DateTime<Utc>,
}
