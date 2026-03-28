use actix_web::{web, HttpResponse, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize)]
pub struct ActiveDefinitionResponse {
    pub plan_key: String,
    pub build_id: String,
    pub year: String,
    pub definition: serde_json::Value,
}

pub async fn get_active_definition(
    web::Path(plan_key): web::Path<String>,
) -> Result<HttpResponse> {
    Ok(HttpResponse::NotFound().json(serde_json::json!({
        "error": format!("Build plan '{}' not found", plan_key)
    })))
}

#[derive(Debug, Serialize)]
pub struct PrepareContextResponse {
    pub plan_key: String,
    pub project: ProjectContext,
    pub current_repository: RepositoryContext,
    pub project_build: ProjectBuildContext,
    pub repositories: Vec<RepositoryContext>,
    pub variables: std::collections::HashMap<String, String>,
}

#[derive(Debug, Serialize)]
pub struct ProjectContext {
    pub jira_project_key: String,
    pub bitbucket_project_key: String,
    pub representative_repo_slug: String,
}

#[derive(Debug, Serialize)]
pub struct RepositoryContext {
    pub repo_slug: String,
    pub coverity_project: Option<String>,
    pub coverity_stream: Option<String>,
    #[serde(default)]
    pub is_representative: bool,
}

#[derive(Debug, Serialize)]
pub struct ProjectBuildContext {
    pub build_name: String,
    pub build_type: String,
}

pub async fn get_prepare_context(
    web::Path(plan_key): web::Path<String>,
) -> Result<HttpResponse> {
    Ok(HttpResponse::NotFound().json(serde_json::json!({
        "error": format!("Prepare context for '{}' not found", plan_key)
    })))
}

#[derive(Debug, Serialize)]
pub struct ExecutionSummary {
    pub id: String,
    pub build_number: i32,
    pub success: bool,
    pub result_status: String,
    pub started_at: String,
    pub finished_at: Option<String>,
    pub commit_hash: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ExecutionListResponse {
    pub executions: Vec<ExecutionSummary>,
}

pub async fn get_executions(
    web::Path(plan_key): web::Path<String>,
) -> Result<HttpResponse> {
    Ok(HttpResponse::NotFound().json(serde_json::json!({
        "error": format!("Build plan '{}' not found", plan_key)
    })))
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
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
    );
}
