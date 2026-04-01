use actix_web::{web, HttpResponse, Result};
use chrono::{DateTime, Utc};
use serde::Deserialize;
use uuid::Uuid;

use crate::api::responses;
use crate::infrastructure::repositories::execution_repo;
use crate::AppState;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecutionStartRequest {
    pub branch_kind: String,
    pub commit_hash: String,
    pub build_number: String,
    #[serde(default)]
    pub build_key: String,
    pub started_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StaticAnalysisResultInput {
    pub tool_name: String,
    pub status: String,
    #[serde(default)]
    pub summary: String,
    pub metrics_json: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StaticAnalysisResultsUpsertRequest {
    pub static_analysis_results: Vec<StaticAnalysisResultInput>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecutionFinishRequest {
    pub success: bool,
    pub result_status: String,
    #[serde(default)]
    pub summary_message: String,
    #[serde(default)]
    pub stage_name: String,
    #[serde(default)]
    pub job_name: String,
    #[serde(default)]
    pub task_name: String,
    pub finished_at: Option<DateTime<Utc>>,
    #[serde(default)]
    pub static_analysis_results: Vec<StaticAnalysisResultInput>,
}

pub async fn create_execution(
    state: web::Data<AppState>,
    path: web::Path<String>,
    web::Json(payload): web::Json<ExecutionStartRequest>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match execution_repo::start_execution(
        pool,
        &plan_key,
        &payload.branch_kind,
        &payload.commit_hash,
        &payload.build_number,
        &payload.build_key,
        payload.started_at,
    )
    .await
    {
        Ok(response) => Ok(HttpResponse::Ok().json(response)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn complete_execution(
    state: web::Data<AppState>,
    path: web::Path<Uuid>,
    web::Json(payload): web::Json<ExecutionFinishRequest>,
) -> Result<HttpResponse> {
    let execution_id = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    let static_analysis_results = payload
        .static_analysis_results
        .iter()
        .map(static_analysis_result_to_value)
        .collect::<Vec<_>>();
    match execution_repo::finish_execution(
        pool,
        execution_id,
        payload.success,
        &payload.result_status,
        &payload.summary_message,
        &payload.stage_name,
        &payload.job_name,
        &payload.task_name,
        payload.finished_at,
        &static_analysis_results,
    )
    .await
    {
        Ok(response) => Ok(HttpResponse::Ok().json(response)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn upsert_static_analysis_results(
    state: web::Data<AppState>,
    path: web::Path<Uuid>,
    web::Json(payload): web::Json<StaticAnalysisResultsUpsertRequest>,
) -> Result<HttpResponse> {
    let execution_id = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    let static_analysis_results = payload
        .static_analysis_results
        .iter()
        .map(static_analysis_result_to_value)
        .collect::<Vec<_>>();
    match execution_repo::record_static_analysis_results(pool, execution_id, &static_analysis_results).await {
        Ok(response) => Ok(HttpResponse::Ok().json(response)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

fn static_analysis_result_to_value(result: &StaticAnalysisResultInput) -> serde_json::Value {
    serde_json::json!({
        "toolName": result.tool_name,
        "status": result.status,
        "summary": result.summary,
        "metricsJson": result.metrics_json,
    })
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::resource("/build-plans/{plan_key}/executions/start")
            .route(web::post().to(create_execution)),
    )
    .service(
        web::resource("/build-executions/{execution_id}/finish")
            .route(web::post().to(complete_execution)),
    )
    .service(
        web::resource("/build-executions/{execution_id}/static-analysis-results")
            .route(web::post().to(upsert_static_analysis_results)),
    );
}
