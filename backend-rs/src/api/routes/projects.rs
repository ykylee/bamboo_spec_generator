use actix_web::{web, HttpResponse, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct ProjectSummary {
    pub jira_project_key: String,
    pub bitbucket_project_key: String,
    pub ci_provider: String,
    pub display_name: String,
    pub build_count: i32,
    pub repository_count: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ProjectListResponse {
    pub projects: Vec<ProjectSummary>,
}

#[derive(Debug, Deserialize)]
pub struct ListQuery {
    #[serde(default)]
    pub ci_provider: Option<String>,
}

pub async fn list_projects(
    web::Query(params): web::Query<ListQuery>,
) -> Result<HttpResponse> {
    let projects = vec![];
    Ok(HttpResponse::Ok().json(ProjectListResponse { projects }))
}

#[derive(Debug, Deserialize)]
pub struct ProjectPath {
    pub project_key: String,
}

#[derive(Debug, Serialize)]
pub struct ProjectDetailResponse {
    pub jira_project_key: String,
    pub bitbucket_project_key: String,
    pub ci_provider: String,
    pub display_name: String,
    pub description: Option<String>,
    pub repositories: Vec<RepositorySummary>,
    pub build_units: Vec<BuildUnitSummary>,
}

#[derive(Debug, Serialize)]
pub struct RepositorySummary {
    pub repo_slug: String,
    pub coverity_project: Option<String>,
    pub coverity_stream: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct BuildUnitSummary {
    pub build_name: String,
    pub plan_key: Option<String>,
    pub job_path: Option<String>,
}

pub async fn get_project(
    web::Path(project_key): web::Path<String>,
) -> Result<HttpResponse> {
    Ok(HttpResponse::NotFound().json(serde_json::json!({
        "error": "Project not found"
    })))
}

#[derive(Debug, Deserialize)]
pub struct CreateProjectRequest {
    pub jira_project_key: String,
    pub bitbucket_project_key: String,
    #[serde(default = "default_ci_provider")]
    pub ci_provider: String,
    pub display_name: String,
    pub description: Option<String>,
}

fn default_ci_provider() -> String {
    "bamboo".to_string()
}

pub async fn create_project(
    web::Json(payload): web::Json<CreateProjectRequest>,
) -> Result<HttpResponse> {
    Ok(HttpResponse::Created().json(serde_json::json!({
        "jira_project_key": payload.jira_project_key,
        "bitbucket_project_key": payload.bitbucket_project_key,
        "ci_provider": payload.ci_provider,
        "display_name": payload.display_name,
    })))
}

#[derive(Debug, Deserialize)]
pub struct UpdateProjectRequest {
    pub display_name: Option<String>,
    pub description: Option<String>,
    pub representative_repo_slug: Option<String>,
}

pub async fn update_project(
    web::Path(project_key): web::Path<String>,
    web::Json(payload): web::Json<UpdateProjectRequest>,
) -> Result<HttpResponse> {
    Ok(HttpResponse::Ok().json(serde_json::json!({
        "jira_project_key": project_key,
        "display_name": payload.display_name,
    })))
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::resource("/projects")
            .route(web::get().to(list_projects))
            .route(web::post().to(create_project))
    )
    .service(
        web::resource("/projects/{project_key}")
            .route(web::get().to(get_project))
            .route(web::put().to(update_project))
    );
}
