use actix_web::{web, HttpResponse, Result};
use serde::Deserialize;

use crate::api::responses;
use crate::infrastructure::repositories::project_repo;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct ListQuery {
    #[serde(default)]
    pub ci_provider: Option<String>,
}

pub async fn list_projects(
    state: web::Data<AppState>,
    web::Query(params): web::Query<ListQuery>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match project_repo::list_project_summaries(pool, params.ci_provider.as_deref()).await {
        Ok(projects) => Ok(HttpResponse::Ok().json(projects)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_project(
    state: web::Data<AppState>,
    path: web::Path<String>,
    web::Query(params): web::Query<ListQuery>,
) -> Result<HttpResponse> {
    let project_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match project_repo::get_project_detail(pool, &project_key, params.ci_provider.as_deref()).await {
        Ok(Some(project)) => Ok(HttpResponse::Ok().json(project)),
        Ok(None) => Ok(responses::not_found(format!("Project '{}' was not found.", project_key))),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn create_project(
    state: web::Data<AppState>,
    web::Json(payload): web::Json<project_repo::ProjectCreateInput>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match project_repo::create_project(pool, &payload).await {
        Ok(project) => Ok(HttpResponse::Ok().json(project)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn update_project(
    state: web::Data<AppState>,
    path: web::Path<String>,
    web::Json(payload): web::Json<project_repo::ProjectUpdateInput>,
) -> Result<HttpResponse> {
    let project_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match project_repo::update_project(pool, &project_key, &payload).await {
        Ok(Some(project)) => Ok(HttpResponse::Ok().json(project)),
        Ok(None) => Ok(responses::not_found(format!("Project '{}' was not found.", project_key))),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
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
