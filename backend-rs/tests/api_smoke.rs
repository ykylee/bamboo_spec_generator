use actix_web::{http::StatusCode, test, web, App};
use actix_web_httpauth::middleware::HttpAuthentication;
use serial_test::serial;

use bamboo_backend::api::routes::{build_plans, executions, jenkins_jobs, modules, projects, settings};
use bamboo_backend::AppState;

fn configure_api_scope(cfg: &mut web::ServiceConfig) {
    cfg.configure(projects::configure)
        .configure(build_plans::configure)
        .configure(executions::configure)
        .configure(modules::configure)
        .configure(settings::configure)
        .configure(jenkins_jobs::configure);
}

#[actix_web::test]
#[serial]
async fn projects_endpoint_returns_service_unavailable_without_database() {
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", "test-token"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri("/api/v1/projects")
        .insert_header(("Authorization", "Bearer test-token"))
        .to_request();
    let response = test::call_service(&app, request).await;

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
}

#[actix_web::test]
#[serial]
async fn build_plan_endpoint_returns_service_unavailable_without_database() {
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", "test-token"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri("/api/v1/build-plans/SAMPAPI/active-definition")
        .insert_header(("Authorization", "Bearer test-token"))
        .to_request();
    let response = test::call_service(&app, request).await;

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
}

#[actix_web::test]
#[serial]
async fn execution_start_returns_service_unavailable_without_database() {
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", "test-token"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::post()
        .uri("/api/v1/build-plans/SAMPAPI/executions/start")
        .insert_header(("Authorization", "Bearer test-token"))
        .set_json(serde_json::json!({
            "branchKind": "dev",
            "commitHash": "abcdef123456",
            "buildNumber": "101",
        }))
        .to_request();
    let response = test::call_service(&app, request).await;

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
}

#[actix_web::test]
#[serial]
async fn coverity_settings_endpoint_returns_service_unavailable_without_database() {
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", "test-token"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri("/api/v1/system-settings/coverity")
        .insert_header(("Authorization", "Bearer test-token"))
        .to_request();
    let response = test::call_service(&app, request).await;

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
}

#[actix_web::test]
#[serial]
async fn module_upload_endpoint_returns_service_unavailable_without_database() {
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", "test-token"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::post()
        .uri("/api/v1/admin/modules/uploads")
        .insert_header(("Authorization", "Bearer test-token"))
        .to_request();
    let response = test::call_service(&app, request).await;

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
}

#[actix_web::test]
#[serial]
async fn specs_draft_initialize_endpoint_returns_service_unavailable_without_database() {
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", "test-token"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::post()
        .uri("/api/v1/system-settings/specs-drafts/initialize")
        .insert_header(("Authorization", "Bearer test-token"))
        .to_request();
    let response = test::call_service(&app, request).await;

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
}

#[actix_web::test]
#[serial]
async fn jenkins_jobs_endpoint_returns_service_unavailable_without_database() {
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", "test-token"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri("/api/v1/jenkins-jobs")
        .insert_header(("Authorization", "Bearer test-token"))
        .to_request();
    let response = test::call_service(&app, request).await;

    assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
}

#[actix_web::test]
#[serial]
async fn api_requires_valid_bearer_token() {
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", "test-token"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::get().uri("/api/v1/projects").to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);

    let request = test::TestRequest::get()
        .uri("/api/v1/projects")
        .insert_header(("Authorization", "Bearer wrong-token"))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}

#[actix_web::test]
#[serial]
async fn api_returns_internal_server_error_when_token_is_not_configured() {
    unsafe { std::env::remove_var("BAMBOO_API_TOKEN"); }
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState { pool: None }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;
    let request = test::TestRequest::get()
        .uri("/api/v1/projects")
        .insert_header(("Authorization", "Bearer test-token"))
        .to_request();
    let response = test::call_service(&app, request).await;
    assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
}
