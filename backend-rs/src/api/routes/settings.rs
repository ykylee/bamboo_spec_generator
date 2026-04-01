use actix_web::{web, HttpResponse, Result};
use serde::Deserialize;

use crate::api::responses;
use crate::infrastructure::repositories::settings_repo;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct SpecsDraftInitializeQuery {
    #[serde(default, rename = "resetExisting")]
    pub reset_existing: bool,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CoveritySettingsRequest {
    #[serde(default)]
    pub connect_url: String,
    #[serde(default = "default_on_new_cert")]
    pub on_new_cert: String,
    #[serde(default)]
    pub commit_enabled: bool,
    #[serde(default)]
    pub git_clone_url_template: String,
    #[serde(default = "default_repository_linkage_mode")]
    pub repository_linkage_mode: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BambooSettingsRequest {
    #[serde(default)]
    pub server_url: String,
    #[serde(default)]
    pub token: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JenkinsSettingsRequest {
    #[serde(default)]
    pub server_url: String,
    #[serde(default)]
    pub username: String,
    #[serde(default)]
    pub token: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GithubSettingsRequest {
    #[serde(default)]
    pub server_url: String,
    #[serde(default)]
    pub token: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BitbucketSettingsRequest {
    #[serde(default)]
    pub server_url: String,
    #[serde(default)]
    pub token: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GiteaSettingsRequest {
    #[serde(default)]
    pub server_url: String,
    #[serde(default)]
    pub token: String,
}

fn default_on_new_cert() -> String {
    "trust".to_string()
}

fn default_repository_linkage_mode() -> String {
    "linked".to_string()
}

pub async fn get_coverity_settings(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::get_coverity_settings(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn put_coverity_settings(
    state: web::Data<AppState>,
    web::Json(payload): web::Json<CoveritySettingsRequest>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::update_coverity_settings(
        pool,
        &payload.connect_url,
        &payload.on_new_cert,
        payload.commit_enabled,
        &payload.git_clone_url_template,
        &payload.repository_linkage_mode,
    )
    .await
    {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_bamboo_settings(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::get_bamboo_settings(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn put_bamboo_settings(
    state: web::Data<AppState>,
    web::Json(payload): web::Json<BambooSettingsRequest>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    let token = if payload.token.trim().is_empty() {
        None
    } else {
        Some(payload.token.trim())
    };
    match settings_repo::update_bamboo_settings(
        pool,
        payload.server_url.trim(),
        token,
    )
    .await
    {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_jenkins_settings(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::get_jenkins_settings(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn put_jenkins_settings(
    state: web::Data<AppState>,
    web::Json(payload): web::Json<JenkinsSettingsRequest>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    let token = if payload.token.trim().is_empty() {
        None
    } else {
        Some(payload.token.trim())
    };
    match settings_repo::update_jenkins_settings(
        pool,
        payload.server_url.trim(),
        payload.username.trim(),
        token,
    )
    .await
    {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_github_settings(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::get_github_settings(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn put_github_settings(
    state: web::Data<AppState>,
    web::Json(payload): web::Json<GithubSettingsRequest>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    let token = if payload.token.trim().is_empty() {
        None
    } else {
        Some(payload.token.trim())
    };
    match settings_repo::update_github_settings(
        pool,
        payload.server_url.trim(),
        token,
    )
    .await
    {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_bitbucket_settings(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::get_bitbucket_settings(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn put_bitbucket_settings(
    state: web::Data<AppState>,
    web::Json(payload): web::Json<BitbucketSettingsRequest>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    let token = if payload.token.trim().is_empty() {
        None
    } else {
        Some(payload.token.trim())
    };
    match settings_repo::update_bitbucket_settings(
        pool,
        payload.server_url.trim(),
        token,
    )
    .await
    {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn get_gitea_settings(state: web::Data<AppState>) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::get_gitea_settings(pool).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn put_gitea_settings(
    state: web::Data<AppState>,
    web::Json(payload): web::Json<GiteaSettingsRequest>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    let token = if payload.token.trim().is_empty() {
        None
    } else {
        Some(payload.token.trim())
    };
    match settings_repo::update_gitea_settings(
        pool,
        payload.server_url.trim(),
        token,
    )
    .await
    {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::internal_error(error.to_string())),
    }
}

pub async fn post_initialize_specs_drafts(
    state: web::Data<AppState>,
    web::Query(query): web::Query<SpecsDraftInitializeQuery>,
) -> Result<HttpResponse> {
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::initialize_specs_draft_data(pool, query.reset_existing).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub async fn post_initialize_specs_draft_for_plan(
    state: web::Data<AppState>,
    path: web::Path<String>,
    web::Query(query): web::Query<SpecsDraftInitializeQuery>,
) -> Result<HttpResponse> {
    let plan_key = path.into_inner();
    let Some(pool) = state.pool.as_ref() else {
        return Ok(responses::service_unavailable_database());
    };
    match settings_repo::initialize_specs_draft_for_plan(pool, &plan_key, query.reset_existing).await {
        Ok(payload) => Ok(HttpResponse::Ok().json(payload)),
        Err(error) => Ok(responses::map_domain_error(&error)),
    }
}

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::resource("/settings")
            .route(web::get().to(get_coverity_settings))
    )
    .service(
        web::resource("/system-settings/coverity")
            .route(web::get().to(get_coverity_settings))
            .route(web::put().to(put_coverity_settings))
    )
    .service(
        web::resource("/system-settings/bamboo")
            .route(web::get().to(get_bamboo_settings))
            .route(web::put().to(put_bamboo_settings))
    )
    .service(
        web::resource("/system-settings/specs-drafts/initialize")
            .route(web::post().to(post_initialize_specs_drafts))
    )
    .service(
        web::resource("/system-settings/jenkins")
            .route(web::get().to(get_jenkins_settings))
            .route(web::put().to(put_jenkins_settings))
    )
    .service(
        web::resource("/system-settings/github")
            .route(web::get().to(get_github_settings))
            .route(web::put().to(put_github_settings))
    )
    .service(
        web::resource("/system-settings/bitbucket")
            .route(web::get().to(get_bitbucket_settings))
            .route(web::put().to(put_bitbucket_settings))
    )
    .service(
        web::resource("/system-settings/gitea")
            .route(web::get().to(get_gitea_settings))
            .route(web::put().to(put_gitea_settings))
    )
    .service(
        web::resource("/system-settings/specs-drafts/initialize/{planKey}")
            .route(web::post().to(post_initialize_specs_draft_for_plan))
    );
}
