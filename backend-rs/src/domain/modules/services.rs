use crate::domain::modules::entities::{ModuleAsset, ModuleLoadStatus};

pub async fn list_modules() -> Result<Vec<ModuleAsset>, String> {
    Ok(vec![])
}

pub async fn upload_module(_name: &str, _module_type: &str, _content: &str) -> Result<ModuleAsset, String> {
    Err("Not implemented".to_string())
}

pub async fn reload_modules() -> Result<ModuleLoadStatus, String> {
    Err("Not implemented".to_string())
}

pub async fn get_load_status() -> Result<ModuleLoadStatus, String> {
    Ok(ModuleLoadStatus {
        last_load_at: None,
        status: "idle".to_string(),
        loaded_modules: 0,
        errors: vec![],
    })
}
