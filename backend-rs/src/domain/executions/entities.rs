use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuildExecution {
    pub id: Uuid,
    pub build_unit_id: Uuid,
    pub build_version_id: Uuid,
    pub build_number: i32,
    pub commit_hash: String,
    pub success: bool,
    pub result_status: String,
    pub summary_message: Option<String>,
    pub stage_name: Option<String>,
    pub job_name: Option<String>,
    pub task_name: Option<String>,
    pub started_at: Option<DateTime<Utc>>,
    pub finished_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StaticAnalysisResult {
    pub id: Uuid,
    pub build_execution_id: Uuid,
    pub tool_name: String,
    pub status: String,
    pub summary: Option<String>,
    pub metrics_json: Option<serde_json::Value>,
    pub created_at: DateTime<Utc>,
}
