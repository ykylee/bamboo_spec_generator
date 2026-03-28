use actix_web::{web, HttpResponse, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct ModuleSummary {
    pub id: String,
    pub name: String,
    pub module_type: String,
    pub version: i32,
    pub is_active: bool,
    pub uploaded_at: String,
    pub uploaded_by: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ModuleListResponse {
    pub modules: Vec<ModuleSummary>,
}

pub async fn list_modules() -> Result<HttpResponse> {
    let modules = vec![];
    Ok(HttpResponse::Ok().json(ModuleListResponse { modules }))
}

#[derive(Debug, Deserialize)]
pub struct UploadModuleRequest {
    pub name: String,
    pub module_type: String,
    pub content: String,
}

pub async fn upload_module(
    web::Json(_payload): web::Json<UploadModuleRequest>,
) -> Result<HttpResponse> {
    Ok(HttpResponse::Created().json(serde_json::json!({
        "status": "uploaded"
    })))
}

#[derive(Debug, Serialize)]
pub struct ReloadResponse {
    pub status: String,
    pub reloaded_modules: Vec<String>,
    pub errors: Vec<String>,
}

pub async fn reload_modules() -> Result<HttpResponse> {
    Ok(HttpResponse::Ok().json(ReloadResponse {
        status: "success".to_string(),
        reloaded_modules: vec![],
        errors: vec![],
    }))
}

#[derive(Debug, Serialize)]
pub struct LoadStatusResponse {
    pub last_load_at: Option<String>,
    pub status: String,
    pub loaded_modules: i32,
    pub errors: Vec<LoadError>,
}

#[derive(Debug, Serialize)]
pub struct LoadError {
    pub module_name: String,
    pub error_message: String,
}

pub async fn get_load_status() -> Result<HttpResponse> {
    Ok(HttpResponse::Ok().json(LoadStatusResponse {
        last_load_at: None,
        status: "idle".to_string(),
        loaded_modules: 0,
        errors: vec![],
    }))
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::resource("/modules")
            .route(web::get().to(list_modules))
    )
    .service(
        web::resource("/modules/upload")
            .route(web::post().to(upload_module))
    )
    .service(
        web::resource("/modules/reload")
            .route(web::post().to(reload_modules))
    )
    .service(
        web::resource("/modules/load-status")
            .route(web::get().to(get_load_status))
    );
}
