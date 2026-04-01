use actix_web::{web, HttpResponse, Result};
use serde::Deserialize;
use std::collections::BTreeMap;

use crate::api::responses;
use crate::infrastructure::repositories::{bamboo_repo, build_plan_repo};
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct ListQuery {
    #[serde(default)]
    pub ci_provider: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BambooQueueRequest {
    #[serde(default)]
    pub stage: String,
    #[serde(default)]
    pub execute_all_stages: bool,
    #[serde(default)]
    pub custom_revision: String,
    #[serde(default)]
    pub variables: BTreeMap<String, String>,
}

pub async fn list_build_plans(
    state: web::Data<AppState>,
    web::Query(params): web::Query<ListQuery>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match build_plan_repo::list_build_plan_summaries(pool, params.ci_provider.as_deref()).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_active_definition(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match build_plan_repo::get_active_definition(pool, &plan_key).await {
        Ok(Some(payload)) => Ok(HttpResponse::Ok().json(payload)),
        Ok(None) => Ok(responses::not_found(format!("Build plan '{}' was not found.", plan_key))),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_prepare_context(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match build_plan_repo::get_prepare_context(pool, &plan_key).await {
        Ok(Some(payload)) => Ok(HttpResponse::Ok().json(payload)),
        Ok(None) => Ok(responses::not_found(format!(
            "Prepare context for '{}' was not found.",
            plan_key
        ))),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_executions(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match build_plan_repo::get_executions(pool, &plan_key).await {
        Ok(Some(payload)) => Ok(HttpResponse::Ok().json(payload)),
        Ok(None) => Ok(responses::not_found(format!("Build plan '{}' was not found.", plan_key))),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_bamboo_status(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match bamboo_repo::get_plan_status(pool, &plan_key).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error)),
    }
}

pub async fn get_bamboo_details(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match bamboo_repo::get_plan_details(pool, &plan_key).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) if error.contains("찾지 못했습니다") || error.contains("등록되어 있지 않습니다") => {
            Ok(responses::not_found(error))
        }
        Err(error) => Ok(responses::bad_request(error)),
    }
}

pub async fn queue_bamboo_plan(
    state: web::Data<AppState>,
    path: web::Path<String>,
    web::Json(payload): web::Json<BambooQueueRequest>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    let request = bamboo_repo::BambooQueueRequest {
        stage: payload.stage,
        execute_all_stages: payload.execute_all_stages,
        custom_revision: payload.custom_revision,
        variables: payload.variables,
    };
    match bamboo_repo::queue_plan(pool, &plan_key, request).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) if error.contains("찾지 못했습니다") => Ok(responses::not_found(error)),
        Err(error) => Ok(responses::bad_request(error)),
    }
}

pub async fn publish_bamboo_specs(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match bamboo_repo::publish_plan_specs(pool, &plan_key).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) if error.contains("찾지 못했습니다") => Ok(responses::not_found(error)),
        Err(error) => Ok(responses::bad_request(error)),
    }
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::resource("/build-plans")
            .route(web::get().to(list_build_plans))
    )
    .service(
        web::resource("/build-plans/{plan_key}/active-definition")
            .route(web::get().to(get_active_definition))
    )
    .service(
        web::resource("/build-plans/{plan_key}/prepare-context")
            .route(web::get().to(get_prepare_context))
    )
    .service(
        web::resource("/build-plans/{plan_key}/executions")
            .route(web::get().to(get_executions))
    )
    .service(
        web::resource("/build-plans/{plan_key}/bamboo/status")
            .route(web::get().to(get_bamboo_status))
    )
    .service(
        web::resource("/build-plans/{plan_key}/bamboo/details")
            .route(web::get().to(get_bamboo_details))
    )
    .service(
        web::resource("/build-plans/{plan_key}/bamboo/queue")
            .route(web::post().to(queue_bamboo_plan))
    )
    .service(
        web::resource("/build-plans/{plan_key}/bamboo/publish")
            .route(web::post().to(publish_bamboo_specs))
    );
}
