use actix_web::{web, HttpResponse, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemSetting {
    pub key: String,
    pub value: Option<String>,
    pub description: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct SettingsListResponse {
    pub settings: Vec<SystemSetting>,
}

pub async fn list_settings() -> Result<HttpResponse> {
    let settings = vec![
        SystemSetting {
            key: "bamboo.server.url".to_string(),
            value: Some("http://localhost:8085".to_string()),
            description: Some("Bamboo server URL".to_string()),
        },
    ];
    Ok(HttpResponse::Ok().json(SettingsListResponse { settings }))
}

#[derive(Debug, Deserialize)]
pub struct UpdateSettingRequest {
    pub value: String,
    pub description: Option<String>,
}

pub async fn update_setting(
    web::Path(key): web::Path<String>,
    web::Json(payload): web::Json<UpdateSettingRequest>,
) -> Result<HttpResponse> {
    Ok(HttpResponse::Ok().json(SystemSetting {
        key,
        value: Some(payload.value),
        description: payload.description,
    }))
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::resource("/settings")
            .route(web::get().to(list_settings))
    )
    .service(
        web::resource("/settings/{key}")
            .route(web::put().to(update_setting))
    );
}
