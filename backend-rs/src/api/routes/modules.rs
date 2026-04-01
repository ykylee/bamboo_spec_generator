use actix_multipart::Multipart;
use actix_web::{web, HttpResponse, Result};
use futures_util::StreamExt as _;
use serde::Deserialize;
use uuid::Uuid;

use crate::api::responses;
use crate::infrastructure::repositories::module_repo;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct ModuleListQuery {
    #[serde(default, rename = "assetKind")]
    pub asset_kind: String,
    #[serde(default, rename = "providerScope")]
    pub provider_scope: String,
    #[serde(default)]
    pub status: String,
}

#[derive(Debug, Deserialize)]
pub struct ModuleDetailQuery {
    #[serde(default, rename = "version")]
    pub version_id: String,
    #[serde(default, rename = "compare")]
    pub compare_version_id: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModuleActivateRequest {
    pub version_id: Uuid,
}

pub async fn list_modules(
    state: web::Data<AppState>,
    web::Query(query): web::Query<ModuleListQuery>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match module_repo::list_modules(pool, &query.asset_kind, &query.provider_scope, &query.status).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_load_status(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match module_repo::get_load_status(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_module_detail(
    state: web::Data<AppState>,
    path: web::Path<Uuid>,
    web::Query(query): web::Query<ModuleDetailQuery>,
) -> Result<HttpResponse> {
    let asset_id = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match module_repo::get_module_detail(pool, asset_id, &query.version_id, &query.compare_version_id).await {
        Ok(Some(payload)) => Ok(HttpResponse::Ok().json(payload)),
        Ok(None) => Ok(responses::not_found("Module asset was not found.")),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn activate_module(
    state: web::Data<AppState>,
    path: web::Path<Uuid>,
    web::Json(payload): web::Json<ModuleActivateRequest>,
) -> Result<HttpResponse> {
    let asset_id = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match module_repo::activate_module_version(pool, asset_id, payload.version_id).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn deactivate_module(
    state: web::Data<AppState>,
    path: web::Path<Uuid>,
) -> Result<HttpResponse> {
    let asset_id = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match module_repo::deactivate_module(pool, asset_id).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn reload_modules(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match module_repo::reload_modules(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn upload_module(
    state: web::Data<AppState>,
    mut payload: Multipart,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };

    let mut asset_kind = String::new();
    let mut provider_scope = String::from("common");
    let mut module_id = String::new();
    let mut activate_after_upload = false;
    let mut filename = String::new();
    let mut content = Vec::new();

    while let Some(item) = payload.next().await {
        let mut field = match item {
            Ok(field) => field,
            Err(error) => {
                return Ok(responses::bad_request(error.to_string()));
            }
        };
        let field_name = field
            .content_disposition()
            .and_then(|disposition| disposition.get_name())
            .unwrap_or("")
            .to_string();

        if field_name == "file" {
            filename = field
                .content_disposition()
                .and_then(|disposition| disposition.get_filename())
                .unwrap_or("upload.bin")
                .to_string();
            while let Some(chunk) = field.next().await {
                let bytes = match chunk {
                    Ok(bytes) => bytes,
                    Err(error) => {
                        return Ok(responses::bad_request(error.to_string()));
                    }
                };
                content.extend_from_slice(&bytes);
            }
            continue;
        }

        let mut buffer = Vec::new();
        while let Some(chunk) = field.next().await {
            let bytes = match chunk {
                Ok(bytes) => bytes,
                Err(error) => {
                    return Ok(responses::bad_request(error.to_string()));
                }
            };
            buffer.extend_from_slice(&bytes);
        }
        let value = String::from_utf8(buffer).unwrap_or_default();
        match field_name.as_str() {
            "assetKind" => asset_kind = value.trim().to_string(),
            "providerScope" => provider_scope = value.trim().to_string(),
            "moduleId" => module_id = value.trim().to_string(),
            "activateAfterUpload" => {
                let normalized = value.trim().to_lowercase();
                activate_after_upload = normalized == "true" || normalized == "on" || normalized == "1";
            }
            _ => {}
        }
    }

    match module_repo::upload_module_asset(
        pool,
        module_repo::ModuleUploadInput {
            asset_kind,
            provider_scope,
            module_id,
            filename,
            content,
            activate_after_upload,
        },
    )
    .await
    {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::resource("/admin/modules")
            .route(web::get().to(list_modules))
    )
    .service(
        web::resource("/admin/modules/load-status")
            .route(web::get().to(get_load_status))
    )
    .service(
        web::resource("/admin/modules/uploads")
            .route(web::post().to(upload_module))
    )
    .service(
        web::resource("/admin/modules/reload")
            .route(web::post().to(reload_modules))
    )
    .service(
        web::resource("/admin/modules/{asset_id}")
            .route(web::get().to(get_module_detail))
    )
    .service(
        web::resource("/admin/modules/{asset_id}/activate")
            .route(web::post().to(activate_module))
    )
    .service(
        web::resource("/admin/modules/{asset_id}/deactivate")
            .route(web::post().to(deactivate_module))
    );
}
