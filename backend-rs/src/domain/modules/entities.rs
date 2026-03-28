use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModuleAsset {
    pub id: Uuid,
    pub name: String,
    pub module_type: String,
    pub version: i32,
    pub content_hash: String,
    pub is_active: bool,
    pub uploaded_by: Option<String>,
    pub uploaded_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModuleAssetVersion {
    pub id: Uuid,
    pub module_asset_id: Uuid,
    pub version: i32,
    pub content: String,
    pub content_hash: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModuleLoadStatus {
    pub last_load_at: Option<DateTime<Utc>>,
    pub status: String,
    pub loaded_modules: i32,
    pub errors: Vec<ModuleLoadError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModuleLoadError {
    pub module_name: String,
    pub error_message: String,
}
