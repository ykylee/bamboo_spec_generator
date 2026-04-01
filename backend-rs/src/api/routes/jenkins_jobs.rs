use actix_web::{web, HttpResponse, Result};
use serde::Deserialize;

use crate::api::responses;
use crate::infrastructure::repositories::jenkins_repo;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct TriggerRequest {
    #[serde(default)]
    pub parameters: serde_json::Value,
}

pub async fn list_jenkins_jobs(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match jenkins_repo::list_jenkins_job_summaries(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_jenkins_job_status_endpoint(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let job_path = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match jenkins_repo::get_jenkins_job_status(pool, &job_path).await {
        Ok(Some(payload)) => Ok(HttpResponse::Ok().json(payload)),
        Ok(None) => Ok(responses::not_found("Jenkins job was not found.")),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn get_jenkins_job_details_endpoint(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let job_path = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match jenkins_repo::get_jenkins_job_details(pool, &job_path).await {
        Ok(Some(payload)) => Ok(HttpResponse::Ok().json(payload)),
        Ok(None) => Ok(responses::not_found("Jenkins job was not found.")),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn get_jenkins_executions(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let job_path = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match jenkins_repo::list_executions_by_job_path(pool, &job_path).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn trigger_jenkins_job_endpoint(
    state: web::Data<AppState>,
    path: web::Path<String>,
    web::Json(payload): web::Json<TriggerRequest>,
) -> Result<HttpResponse> {
    let job_path = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match jenkins_repo::trigger_jenkins_job(pool, &job_path, &payload.parameters).await {
        Ok(Some(result)) => Ok(HttpResponse::Ok().json(result)),
        Ok(None) => Ok(responses::not_found("Jenkins job was not found.")),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn configure_jenkins_job_endpoint(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> Result<HttpResponse> {
    let job_path = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match jenkins_repo::configure_jenkins_job(pool, &job_path).await {
        Ok(Some(result)) => Ok(HttpResponse::Ok().json(result)),
        Ok(None) => Ok(responses::not_found("Jenkins job was not found.")),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn get_jenkins_build_endpoint(
    state: web::Data<AppState>,
    path: web::Path<(String, String)>,
) -> Result<HttpResponse> {
    let (job_path, build_number) = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match jenkins_repo::get_jenkins_build_details(pool, &job_path, &build_number).await {
        Ok(Some(payload)) => Ok(HttpResponse::Ok().json(payload)),
        Ok(None) => Ok(responses::not_found("Jenkins build was not found.")),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn get_jenkins_system_status(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match jenkins_repo::get_jenkins_system_status(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(web::resource("/jenkins-jobs").route(web::get().to(list_jenkins_jobs)))
        .service(web::resource("/jenkins-jobs/system-status").route(web::get().to(get_jenkins_system_status)))
        .service(web::resource("/jenkins-jobs/{job_path:.+}/builds/{build_number}").route(web::get().to(get_jenkins_build_endpoint)))
        .service(web::resource("/jenkins-jobs/{job_path:.+}/status").route(web::get().to(get_jenkins_job_status_endpoint)))
        .service(web::resource("/jenkins-jobs/{job_path:.+}/details").route(web::get().to(get_jenkins_job_details_endpoint)))
        .service(web::resource("/jenkins-jobs/{job_path:.+}/executions").route(web::get().to(get_jenkins_executions)))
        .service(web::resource("/jenkins-jobs/{job_path:.+}/trigger").route(web::post().to(trigger_jenkins_job_endpoint)))
        .service(web::resource("/jenkins-jobs/{job_path:.+}/configure").route(web::post().to(configure_jenkins_job_endpoint)));
}
