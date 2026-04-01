use std::fs;
use std::path::PathBuf;

use actix_web::{http::StatusCode, test, web, App};
use actix_web_httpauth::middleware::HttpAuthentication;
use serial_test::serial;
use sqlx::PgPool;
use uuid::Uuid;

use bamboo_backend::api::routes::{build_plans, executions, jenkins_jobs, modules, projects, settings};
use bamboo_backend::AppState;

const TEST_TOKEN: &str = "golden-test-token";

fn configure_api_scope(cfg: &mut web::ServiceConfig) {
    cfg.configure(projects::configure)
        .configure(build_plans::configure)
        .configure(executions::configure)
        .configure(modules::configure)
        .configure(settings::configure)
        .configure(jenkins_jobs::configure);
}

async fn golden_pool() -> PgPool {
    let _ = dotenv::from_filename(".env");
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be configured for golden tests");
    bamboo_backend::infrastructure::database::create_pool(&database_url)
        .await
        .expect("Failed to connect test database")
}

async fn reset_tables(pool: &PgPool) {
    sqlx::query(
        r#"
        TRUNCATE TABLE
            buildmeta_static_analysis_result,
            buildmeta_execution_artifact,
            buildmeta_build_execution,
            buildmeta_build_version,
            buildmeta_bamboo_publish_execution,
            buildmeta_build_unit_definition,
            buildmeta_bamboo_build_info,
            buildmeta_bamboo_build_unit,
            buildmeta_jenkins_build_unit,
            buildmeta_build_unit,
            buildmeta_repository,
            buildmeta_project
        CASCADE
        "#,
    )
    .execute(pool)
    .await
    .expect("Failed to reset golden tables");

    sqlx::query(
        r#"
        DELETE FROM buildmeta_systemsetting
        WHERE key IN (
            'coverity.connect.url',
            'coverity.connect.on_new_cert',
            'coverity.commit.enabled',
            'repository.git.clone_url_template',
            'repository.linkage_mode'
        )
        "#,
    )
    .execute(pool)
    .await
    .expect("Failed to reset golden system settings");
}

async fn seed_sample_fixture(pool: &PgPool) {
    let project_id = Uuid::new_v4();
    let repository_id = Uuid::new_v4();
    let build_unit_id = Uuid::new_v4();
    let build_info_id = Uuid::new_v4();

    sqlx::query(
        r#"
        INSERT INTO buildmeta_project (
            id, created_at, updated_at, project_key, name, description, owner_team, service_type,
            ci_provider, status, representative_repository_id
        )
        VALUES ($1, NOW(), NOW(), 'SAMPLE', 'SAMPLE', '', '', '', 'bamboo', 'active', NULL)
        "#,
    )
    .bind(project_id)
    .execute(pool)
    .await
    .expect("Failed to insert golden project");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_repository (
            id, created_at, updated_at, project_id, repository_type, repository_provider, repo_type,
            repo_key, repo_slug, clone_url, default_branch, is_representative, coverity_project, coverity_stream
        )
        VALUES (
            $1, NOW(), NOW(), $2, 'git', 'bitbucket', 'bitbucket',
            'SAMPLE', 'sample-app-api', '', 'dev', true, 'sample-app', 'sample-app-dev'
        )
        "#,
    )
    .bind(repository_id)
    .bind(project_id)
    .execute(pool)
    .await
    .expect("Failed to insert golden repository");

    sqlx::query(
        r#"
        UPDATE buildmeta_project
        SET representative_repository_id = $1, updated_at = NOW()
        WHERE id = $2
        "#,
    )
    .bind(repository_id)
    .bind(project_id)
    .execute(pool)
    .await
    .expect("Failed to update representative repository");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_build_unit (
            id, created_at, updated_at, project_id, repository_id, ci_provider, unit_type, external_key,
            display_name, description, language, compiler, runtime_stack, lifecycle_status, is_enabled, latest_version_id
        )
        VALUES (
            $1, NOW(), NOW(), $2, $3, 'bamboo', 'build', 'SAMPAPI',
            'backend', '', 'java', 'python', 'java', 'active', true, NULL
        )
        "#,
    )
    .bind(build_unit_id)
    .bind(project_id)
    .bind(repository_id)
    .execute(pool)
    .await
    .expect("Failed to insert golden build unit");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_bamboo_build_unit (
            build_unit_id, created_at, updated_at, bamboo_project_key, plan_key, build_id,
            repository_linkage_mode, application_link, static_analysis_tool_version, coverity_project
        )
        VALUES ($1, NOW(), NOW(), 'SAMPLE', 'SAMPAPI', 'sample-app-api', '', 'BITBUCKET_SERVER', '', '')
        "#,
    )
    .bind(build_unit_id)
    .execute(pool)
    .await
    .expect("Failed to insert golden bamboo build unit");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_bamboo_build_info (
            id, created_at, updated_at, bamboo_build_unit_id, build_key, operating_system,
            pre_process, build_command, clean_command, language, compiler, analysis_excluded_files,
            coverity_stream, build_sub_path
        )
        VALUES (
            $1, NOW(), NOW(), $2, 'api-linux', 'linux',
            'mvn -B dependency:go-offline', 'mvn -B clean package', '', 'java', 'maven', '',
            'sample-app-dev', 'services/sample-app-api'
        )
        "#,
    )
    .bind(build_info_id)
    .bind(build_unit_id)
    .execute(pool)
    .await
    .expect("Failed to insert golden bamboo build info");
}

async fn seed_golden_settings(pool: &PgPool) {
    sqlx::query(
        r#"
        INSERT INTO buildmeta_systemsetting (id, created_at, updated_at, key, value, description)
        VALUES
            ($1, NOW(), NOW(), 'coverity.connect.url', 'https://coverity.example.com', 'Coverity Connect URL'),
            ($2, NOW(), NOW(), 'coverity.connect.on_new_cert', 'trust', 'Coverity on-new-cert policy'),
            ($3, NOW(), NOW(), 'coverity.commit.enabled', 'true', 'Coverity commit enabled flag'),
            ($4, NOW(), NOW(), 'repository.git.clone_url_template', 'https://git.example.com/scm/{project_key_lower}/{repo_slug}.git', 'Git clone URL template'),
            ($5, NOW(), NOW(), 'repository.linkage_mode', 'create_if_missing', 'Repository linkage mode')
        ON CONFLICT (key)
        DO UPDATE SET value = EXCLUDED.value, description = EXCLUDED.description, updated_at = NOW()
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(Uuid::new_v4())
    .bind(Uuid::new_v4())
    .bind(Uuid::new_v4())
    .bind(Uuid::new_v4())
    .execute(pool)
    .await
    .expect("Failed to seed golden settings");
}

fn auth_header() -> (String, String) {
    ("Authorization".to_string(), format!("Bearer {TEST_TOKEN}"))
}

fn golden_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("golden")
        .join(name)
}

fn assert_matches_golden(actual: serde_json::Value, filename: &str) {
    let expected_raw = fs::read_to_string(golden_path(filename)).expect("Failed to read golden file");
    let expected: serde_json::Value = serde_json::from_str(&expected_raw).expect("Invalid golden JSON");
    assert_eq!(actual, expected, "golden mismatch for {filename}");
}

#[actix_web::test]
#[serial]
async fn project_detail_matches_golden_snapshot() {
    let pool = golden_pool().await;
    reset_tables(&pool).await;
    seed_sample_fixture(&pool).await;
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", TEST_TOKEN); }

    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState {
                pool: Some(pool.clone()),
            }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;

    let response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri("/api/v1/projects/SAMPLE")
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let payload: serde_json::Value = test::read_body_json(response).await;
    assert_matches_golden(payload, "project_detail_sample.json");
}

#[actix_web::test]
#[serial]
async fn prepare_context_matches_golden_snapshot() {
    let pool = golden_pool().await;
    reset_tables(&pool).await;
    seed_sample_fixture(&pool).await;
    seed_golden_settings(&pool).await;
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", TEST_TOKEN); }

    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState {
                pool: Some(pool.clone()),
            }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;

    let response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri("/api/v1/build-plans/SAMPAPI/prepare-context")
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let payload: serde_json::Value = test::read_body_json(response).await;
    assert_matches_golden(payload, "prepare_context_sample.json");
}

#[actix_web::test]
#[serial]
async fn coverity_settings_match_golden_snapshot() {
    let pool = golden_pool().await;
    reset_tables(&pool).await;
    seed_golden_settings(&pool).await;
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", TEST_TOKEN); }

    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(AppState {
                pool: Some(pool.clone()),
            }))
            .wrap(HttpAuthentication::bearer(
                bamboo_backend::api::middleware::auth_middleware,
            ))
            .service(web::scope("/api/v1").configure(configure_api_scope)),
    )
    .await;

    let response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri("/api/v1/system-settings/coverity")
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let payload: serde_json::Value = test::read_body_json(response).await;
    assert_matches_golden(payload, "coverity_settings.json");
}
