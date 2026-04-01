use actix_web::{http::StatusCode, test, web, App};
use actix_web_httpauth::middleware::HttpAuthentication;
use reqwest::header::{HeaderMap, HeaderName, HeaderValue};
use serial_test::serial;
use sqlx::{PgPool, Row};
use tokio::time::{sleep, Duration};
use uuid::Uuid;

use bamboo_backend::api::routes::{build_plans, executions, jenkins_jobs, modules, projects, settings};
use bamboo_backend::AppState;

const TEST_TOKEN: &str = "contract-test-token";
const COVERITY_SETTING_KEYS: [&str; 5] = [
    "coverity.connect.url",
    "coverity.connect.on_new_cert",
    "coverity.commit.enabled",
    "repository.git.clone_url_template",
    "repository.linkage_mode",
];
const PREPARE_CONTEXT_SETTING_KEYS: [&str; 2] = [
    "repository.git.clone_url_template",
    "repository.linkage_mode",
];
const APPLICATION_LINK: &str = "BITBUCKET_SERVER";

fn configure_api_scope(cfg: &mut web::ServiceConfig) {
    cfg.configure(projects::configure)
        .configure(build_plans::configure)
        .configure(executions::configure)
        .configure(modules::configure)
        .configure(settings::configure)
        .configure(jenkins_jobs::configure);
}

#[derive(Clone)]
struct ContractFixture {
    build_unit_id: Uuid,
    project_key: String,
    repo_slug: String,
    plan_key: String,
    build_id: String,
    build_sub_path: String,
}

#[derive(Clone)]
struct JenkinsFixture {
    project_key: String,
    repo_slug: String,
    job_path: String,
}

#[derive(Clone)]
struct StoredSetting {
    key: String,
    value: String,
    description: String,
}

async fn contract_pool() -> PgPool {
    let _ = dotenv::from_filename(".env");
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be configured for contract tests");
    bamboo_backend::infrastructure::database::create_pool(&database_url)
        .await
        .expect("Failed to connect test database")
}

async fn reset_contract_tables(pool: &PgPool) {
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
    .expect("Failed to reset contract tables");

    sqlx::query(
        r#"
        DELETE FROM buildmeta_systemsetting
        WHERE key IN (
            'coverity.connect.url',
            'coverity.connect.on_new_cert',
            'coverity.commit.enabled',
            'repository.git.clone_url_template',
            'repository.linkage_mode',
            'bamboo.server.url'
        )
        "#,
    )
    .execute(pool)
    .await
    .expect("Failed to reset contract system settings");
}

async fn seed_bamboo_fixture(pool: &PgPool) -> ContractFixture {
    let suffix = Uuid::new_v4().simple().to_string()[..8].to_uppercase();
    let project_id = Uuid::new_v4();
    let repository_id = Uuid::new_v4();
    let build_unit_id = Uuid::new_v4();
    let build_info_id = Uuid::new_v4();
    let project_key = format!("S{suffix}");
    let repo_slug = format!("sample-app-api-{}", suffix.to_lowercase());
    let plan_key = format!("{}API", &project_key[..project_key.len().min(8)]);
    let build_id = repo_slug.clone();
    let application_link = APPLICATION_LINK.to_string();
    let build_sub_path = "services/sample-app-api".to_string();

    sqlx::query(
        r#"
        INSERT INTO buildmeta_project (
            id, created_at, updated_at, project_key, name, description, owner_team, service_type,
            ci_provider, status, representative_repository_id
        )
        VALUES ($1, NOW(), NOW(), $2, $2, '', '', '', 'bamboo', 'active', NULL)
        "#,
    )
    .bind(project_id)
    .bind(&project_key)
    .execute(pool)
    .await
    .expect("Failed to insert project");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_repository (
            id, created_at, updated_at, project_id, repository_type, repository_provider, repo_type,
            repo_key, repo_slug, clone_url, default_branch, is_representative, coverity_project, coverity_stream
        )
        VALUES (
            $1, NOW(), NOW(), $2, 'git', 'bitbucket', 'bitbucket',
            $3, $4, '', 'dev', true, 'sample-app', 'sample-app-dev'
        )
        "#,
    )
    .bind(repository_id)
    .bind(project_id)
    .bind(&project_key)
    .bind(&repo_slug)
    .execute(pool)
    .await
    .expect("Failed to insert repository");

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
            $1, NOW(), NOW(), $2, $3, 'bamboo', 'build', $4,
            'backend', '', 'java', 'python', 'java', 'active', true, NULL
        )
        "#,
    )
    .bind(build_unit_id)
    .bind(project_id)
    .bind(repository_id)
    .bind(&plan_key)
    .execute(pool)
    .await
    .expect("Failed to insert build unit");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_bamboo_build_unit (
            build_unit_id, created_at, updated_at, bamboo_project_key, plan_key, build_id,
            repository_linkage_mode, application_link, static_analysis_tool_version, coverity_project
        )
        VALUES ($1, NOW(), NOW(), $2, $3, $4, '', $5, '', '')
        "#,
    )
    .bind(build_unit_id)
    .bind(&project_key)
    .bind(&plan_key)
    .bind(&build_id)
    .bind(&application_link)
    .execute(pool)
    .await
    .expect("Failed to insert bamboo build unit");

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
            'sample-app-dev', $3
        )
        "#,
    )
    .bind(build_info_id)
    .bind(build_unit_id)
    .bind(&build_sub_path)
    .execute(pool)
    .await
    .expect("Failed to insert bamboo build info");

    ContractFixture {
        build_unit_id,
        project_key,
        repo_slug,
        plan_key,
        build_id,
        build_sub_path,
    }
}

async fn seed_jenkins_fixture(pool: &PgPool) -> JenkinsFixture {
    let suffix = Uuid::new_v4().simple().to_string()[..8].to_lowercase();
    let project_id = Uuid::new_v4();
    let repository_id = Uuid::new_v4();
    let build_unit_id = Uuid::new_v4();
    let project_key = format!("J{suffix}").to_uppercase();
    let repo_slug = format!("jenkins-app-{suffix}");
    let job_path = format!("folder/jenkins-contract-{suffix}");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_project (
            id, created_at, updated_at, project_key, name, description, owner_team, service_type,
            ci_provider, status, representative_repository_id
        )
        VALUES ($1, NOW(), NOW(), $2, $2, '', '', '', 'jenkins', 'active', NULL)
        "#,
    )
    .bind(project_id)
    .bind(&project_key)
    .execute(pool)
    .await
    .expect("Failed to insert jenkins project");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_repository (
            id, created_at, updated_at, project_id, repository_type, repository_provider, repo_type,
            repo_key, repo_slug, clone_url, default_branch, is_representative, coverity_project, coverity_stream
        )
        VALUES (
            $1, NOW(), NOW(), $2, 'git', 'bitbucket', 'bitbucket',
            $3, $4, '', 'main', true, '', ''
        )
        "#,
    )
    .bind(repository_id)
    .bind(project_id)
    .bind(&project_key)
    .bind(&repo_slug)
    .execute(pool)
    .await
    .expect("Failed to insert jenkins repository");

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
    .expect("Failed to update jenkins representative repository");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_build_unit (
            id, created_at, updated_at, project_id, repository_id, ci_provider, unit_type, external_key,
            display_name, description, language, compiler, runtime_stack, lifecycle_status, is_enabled, latest_version_id
        )
        VALUES (
            $1, NOW(), NOW(), $2, $3, 'jenkins', 'build', $4,
            'jenkins-backend', '', 'python', 'python', 'python3.12', 'active', true, NULL
        )
        "#,
    )
    .bind(build_unit_id)
    .bind(project_id)
    .bind(repository_id)
    .bind(&job_path)
    .execute(pool)
    .await
    .expect("Failed to insert jenkins build unit");

    sqlx::query(
        r#"
        INSERT INTO buildmeta_jenkins_build_unit (
            build_unit_id, created_at, updated_at, job_path, job_type, folder_path, pipeline_kind
        )
        VALUES ($1, NOW(), NOW(), $2, 'pipeline', 'folder', 'declarative')
        "#,
    )
    .bind(build_unit_id)
    .bind(&job_path)
    .execute(pool)
    .await
    .expect("Failed to insert jenkins build unit metadata");

    JenkinsFixture {
        project_key,
        repo_slug,
        job_path,
    }
}

async fn snapshot_settings(pool: &PgPool, keys: &[&str]) -> Vec<StoredSetting> {
    let mut snapshot = Vec::new();
    for key in keys {
        if let Some(row) = sqlx::query(
            "SELECT key, value, description FROM buildmeta_systemsetting WHERE key = $1",
        )
        .bind(*key)
        .fetch_optional(pool)
        .await
        .expect("Failed to fetch system setting")
        {
            snapshot.push(StoredSetting {
                key: row.get("key"),
                value: row.get("value"),
                description: row.get("description"),
            });
        }
    }
    snapshot
}

async fn restore_settings(pool: &PgPool, keys: &[&str], snapshot: &[StoredSetting]) {
    for key in keys {
        sqlx::query("DELETE FROM buildmeta_systemsetting WHERE key = $1")
            .bind(*key)
            .execute(pool)
            .await
            .expect("Failed to clear system setting");
    }
    for setting in snapshot {
        sqlx::query(
            r#"
            INSERT INTO buildmeta_systemsetting (id, created_at, updated_at, key, value, description)
            VALUES ($1, NOW(), NOW(), $2, $3, $4)
            "#,
        )
        .bind(Uuid::new_v4())
        .bind(&setting.key)
        .bind(&setting.value)
        .bind(&setting.description)
        .execute(pool)
        .await
        .expect("Failed to restore system setting");
    }
}

fn auth_header() -> (String, String) {
    ("Authorization".to_string(), format!("Bearer {TEST_TOKEN}"))
}

async fn jenkins_auth(pool: &PgPool) -> (String, String, String) {
    let row = sqlx::query(
        r#"
        SELECT
            COALESCE(MAX(CASE WHEN key = 'jenkins.server.url' THEN value END), '') AS server_url,
            COALESCE(MAX(CASE WHEN key = 'jenkins.server.token' THEN value END), '') AS token
        FROM buildmeta_systemsetting
        WHERE key IN ('jenkins.server.url', 'jenkins.server.token')
        "#,
    )
    .fetch_one(pool)
    .await
    .expect("Failed to load Jenkins settings");
    let server_url: String = row.get("server_url");
    let settings_token: String = row.get("token");
    let username = std::env::var("JENKINS_USERNAME").unwrap_or_else(|_| "admin".to_string());
    let token = std::env::var("JENKINS_TOKEN")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or(settings_token);
    assert!(!server_url.trim().is_empty(), "jenkins.server.url must be configured");
    assert!(!token.trim().is_empty(), "Jenkins token must be configured");
    (server_url, username, token)
}

fn jenkins_job_url(server_url: &str, job_path: &str) -> String {
    let segments = job_path
        .split('/')
        .filter(|segment| !segment.trim().is_empty())
        .map(|segment| format!("job/{}", urlencoding::encode(segment)))
        .collect::<Vec<_>>();
    format!("{}/{}", server_url.trim_end_matches('/'), segments.join("/"))
}

async fn jenkins_crumb_headers(
    client: &reqwest::Client,
    server_url: &str,
    username: &str,
    token: &str,
) -> HeaderMap {
    let response = client
        .get(format!("{}/crumbIssuer/api/json", server_url.trim_end_matches('/')))
        .basic_auth(username, Some(token))
        .send()
        .await
        .expect("Failed to request Jenkins crumb");
    if response.status().as_u16() == 404 {
        return HeaderMap::new();
    }
    let payload: serde_json::Value = response
        .json()
        .await
        .expect("Failed to parse Jenkins crumb response");
    let mut headers = HeaderMap::new();
    let field = payload
        .get("crumbRequestField")
        .and_then(serde_json::Value::as_str)
        .expect("crumbRequestField must exist");
    let crumb = payload
        .get("crumb")
        .and_then(serde_json::Value::as_str)
        .expect("crumb must exist");
    headers.insert(
        HeaderName::from_bytes(field.as_bytes()).expect("Invalid crumb header name"),
        HeaderValue::from_str(crumb).expect("Invalid crumb value"),
    );
    headers
}

async fn delete_jenkins_job(pool: &PgPool, job_path: &str) {
    let (server_url, username, token) = jenkins_auth(pool).await;
    let client = reqwest::Client::new();
    let crumb_headers = jenkins_crumb_headers(&client, &server_url, &username, &token).await;
    let response = client
        .post(format!("{}/doDelete", jenkins_job_url(&server_url, job_path)))
        .headers(crumb_headers)
        .basic_auth(username, Some(token))
        .send()
        .await
        .expect("Failed to delete Jenkins job");
    assert!(
        response.status().is_success() || response.status().as_u16() == 404,
        "Unexpected Jenkins delete status: {}",
        response.status()
    );
}

#[actix_web::test]
#[serial]
async fn projects_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_bamboo_fixture(&pool).await;
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

    let list_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri("/api/v1/projects")
            .insert_header(("Authorization", format!("Bearer {TEST_TOKEN}")))
            .to_request(),
    )
    .await;
    assert_eq!(list_response.status(), StatusCode::OK);
    let list_payload: serde_json::Value = test::read_body_json(list_response).await;
    let projects = list_payload.as_array().expect("projects payload must be an array");
    assert_eq!(projects.len(), 1);
    assert_eq!(projects[0]["projectKey"], fixture.project_key);
    assert_eq!(projects[0]["generationReady"], true);
    assert_eq!(projects[0]["activeDefinitionCount"], 0);

    let detail_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/projects/{}", fixture.project_key))
            .insert_header(("Authorization", format!("Bearer {TEST_TOKEN}")))
            .to_request(),
    )
    .await;
    assert_eq!(detail_response.status(), StatusCode::OK);
    let detail_payload: serde_json::Value = test::read_body_json(detail_response).await;
    assert_eq!(detail_payload["generation"]["generationReady"], true);
    assert_eq!(detail_payload["builds"][0]["activeDefinitionYear"], "");
    assert_eq!(detail_payload["builds"][0]["buildId"], fixture.build_id);
    assert_eq!(detail_payload["builds"][0]["planKey"], fixture.plan_key);
    assert_eq!(detail_payload["builds"][0]["repositorySlug"], fixture.repo_slug);
}

#[actix_web::test]
#[serial]
async fn project_create_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
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
        test::TestRequest::post()
            .uri("/api/v1/projects")
            .insert_header(auth_header())
            .set_json(serde_json::json!({
                "jiraProjectKey": "NEWPROJ",
                "bitbucketProjectKey": "NEWPROJ",
                "representativeRepoSlug": "new-service",
                "repositories": [
                    {
                        "repoSlug": "new-service",
                        "coverityProject": "new-service",
                        "coverityStream": "new-service-dev",
                        "isRepresentative": true
                    }
                ],
                "builds": [
                    {
                        "buildName": "api",
                        "buildType": "python",
                        "runtimeStack": "python3.12",
                        "buildId": "new-service-api",
                        "planKey": "NEWSVCAPI",
                        "repositorySlug": "new-service"
                    }
                ]
            }))
            .to_request(),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let payload: serde_json::Value = test::read_body_json(response).await;
    assert_eq!(payload["jiraProjectKey"], "NEWPROJ");
    assert_eq!(payload["generation"]["generationReady"], false);
    assert_eq!(
        payload["generation"]["generationReadinessIssues"],
        serde_json::json!(["빌드 정보 없음 1"])
    );
}

#[actix_web::test]
#[serial]
async fn project_update_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_bamboo_fixture(&pool).await;
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
        test::TestRequest::put()
            .uri(&format!("/api/v1/projects/{}", fixture.project_key))
            .insert_header(auth_header())
            .set_json(serde_json::json!({
                "bitbucketProjectKey": "SAMPLE2",
                "representativeRepoSlug": fixture.repo_slug,
                "repositories": [
                    {
                        "repoSlug": fixture.repo_slug,
                        "coverityProject": "sample-app",
                        "coverityStream": "sample-app-release",
                        "isRepresentative": true
                    }
                ],
                "builds": [
                    {
                        "buildName": "backend-api",
                        "buildType": "java",
                        "runtimeStack": "java17",
                        "buildId": fixture.build_id,
                        "planKey": fixture.plan_key,
                        "repositorySlug": fixture.repo_slug
                    }
                ]
            }))
            .to_request(),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let payload: serde_json::Value = test::read_body_json(response).await;
    assert_eq!(payload["bitbucketProjectKey"], "SAMPLE2");
    assert_eq!(payload["builds"][0]["buildName"], "backend-api");
    assert_eq!(payload["repositories"][0]["coverityStream"], "sample-app-release");
    assert_eq!(payload["builds"][0]["repositorySlug"], fixture.repo_slug);
}

#[actix_web::test]
#[serial]
async fn project_create_and_update_supports_multiple_repositories_and_builds() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
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

    let create_response = test::call_service(
        &app,
        test::TestRequest::post()
            .uri("/api/v1/projects")
            .insert_header(auth_header())
            .set_json(serde_json::json!({
                "jiraProjectKey": "MREACT1",
                "bitbucketProjectKey": "MREACT1",
                "name": "React Multi Project",
                "ciProvider": "bamboo",
                "representativeRepoSlug": "react-multi-api",
                "repositories": [
                    {
                        "repoSlug": "react-multi-api",
                        "coverityProject": "react-multi-api",
                        "coverityStream": "react-multi-api-dev",
                        "isRepresentative": true
                    },
                    {
                        "repoSlug": "react-multi-web",
                        "coverityProject": "react-multi-web",
                        "coverityStream": "react-multi-web-dev",
                        "isRepresentative": false
                    }
                ],
                "builds": [
                    {
                        "buildName": "api",
                        "buildType": "python",
                        "runtimeStack": "python3.12",
                        "buildId": "react-multi-api",
                        "planKey": "MREACTAPI",
                        "repositorySlug": "react-multi-api"
                    },
                    {
                        "buildName": "web",
                        "buildType": "node",
                        "runtimeStack": "node20",
                        "buildId": "react-multi-web",
                        "planKey": "MREACTWEB",
                        "repositorySlug": "react-multi-web"
                    }
                ]
            }))
            .to_request(),
    )
    .await;
    assert_eq!(create_response.status(), StatusCode::OK);
    let create_payload: serde_json::Value = test::read_body_json(create_response).await;
    assert_eq!(create_payload["repositories"].as_array().unwrap().len(), 2);
    assert_eq!(create_payload["builds"].as_array().unwrap().len(), 2);
    assert_eq!(create_payload["representativeRepoSlug"], "react-multi-api");

    let update_response = test::call_service(
        &app,
        test::TestRequest::put()
            .uri("/api/v1/projects/MREACT1")
            .insert_header(auth_header())
            .set_json(serde_json::json!({
                "bitbucketProjectKey": "MREACT2",
                "representativeRepoSlug": "react-multi-web",
                "repositories": [
                    {
                        "repoSlug": "react-multi-api",
                        "coverityProject": "react-multi-api",
                        "coverityStream": "react-multi-api-release",
                        "isRepresentative": false
                    },
                    {
                        "repoSlug": "react-multi-web",
                        "coverityProject": "react-multi-web",
                        "coverityStream": "react-multi-web-release",
                        "isRepresentative": true
                    },
                    {
                        "repoSlug": "react-multi-batch",
                        "coverityProject": "react-multi-batch",
                        "coverityStream": "react-multi-batch-release",
                        "isRepresentative": false
                    }
                ],
                "builds": [
                    {
                        "buildName": "api",
                        "buildType": "python",
                        "runtimeStack": "python3.12",
                        "buildId": "react-multi-api",
                        "planKey": "MREACTAPI",
                        "repositorySlug": "react-multi-api"
                    },
                    {
                        "buildName": "web",
                        "buildType": "node",
                        "runtimeStack": "node20",
                        "buildId": "react-multi-web",
                        "planKey": "MREACTWEB",
                        "repositorySlug": "react-multi-web"
                    },
                    {
                        "buildName": "batch",
                        "buildType": "python",
                        "runtimeStack": "python3.12",
                        "buildId": "react-multi-batch",
                        "planKey": "MREACTBAT",
                        "repositorySlug": "react-multi-batch"
                    }
                ]
            }))
            .to_request(),
    )
    .await;
    assert_eq!(update_response.status(), StatusCode::OK);
    let update_payload: serde_json::Value = test::read_body_json(update_response).await;
    assert_eq!(update_payload["bitbucketProjectKey"], "MREACT2");
    assert_eq!(update_payload["representativeRepoSlug"], "react-multi-web");
    assert_eq!(update_payload["repositories"].as_array().unwrap().len(), 3);
    assert_eq!(update_payload["builds"].as_array().unwrap().len(), 3);

    let detail_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri("/api/v1/projects/MREACT1")
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(detail_response.status(), StatusCode::OK);
    let detail_payload: serde_json::Value = test::read_body_json(detail_response).await;
    assert_eq!(detail_payload["representativeRepoSlug"], "react-multi-web");
    assert_eq!(detail_payload["repositories"].as_array().unwrap().len(), 3);
    assert_eq!(detail_payload["builds"].as_array().unwrap().len(), 3);
    assert!(
        detail_payload["builds"]
            .as_array()
            .unwrap()
            .iter()
            .any(|build| {
                build["planKey"] == "MREACTBAT" && build["repositorySlug"] == "react-multi-batch"
            })
    );
}

#[actix_web::test]
#[serial]
async fn coverity_settings_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    let snapshot = snapshot_settings(&pool, &COVERITY_SETTING_KEYS).await;
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

    let put_response = test::call_service(
        &app,
        test::TestRequest::put()
            .uri("/api/v1/system-settings/coverity")
            .insert_header(("Authorization", format!("Bearer {TEST_TOKEN}")))
            .set_json(serde_json::json!({
                "connectUrl": "https://coverity.example.com",
                "onNewCert": "trust",
                "commitEnabled": true,
                "repositoryLinkageMode": "create_if_missing",
                "gitCloneUrlTemplate": "https://git.example.com/scm/{project_key_lower}/{repo_slug}.git"
            }))
            .to_request(),
    )
    .await;
    assert_eq!(put_response.status(), StatusCode::OK);
    let put_payload: serde_json::Value = test::read_body_json(put_response).await;
    assert_eq!(put_payload["connectUrl"], "https://coverity.example.com");
    assert_eq!(put_payload["commitEnabled"], true);
    assert_eq!(put_payload["repositoryLinkageMode"], "create_if_missing");
    assert_eq!(
        put_payload["gitCloneUrlTemplate"],
        "https://git.example.com/scm/{project_key_lower}/{repo_slug}.git"
    );

    let setting_row = sqlx::query("SELECT value FROM buildmeta_systemsetting WHERE key = $1")
        .bind("coverity.connect.url")
        .fetch_one(&pool)
        .await
        .expect("coverity.connect.url must be persisted");
    let persisted_connect_url: String = setting_row.get("value");
    assert_eq!(persisted_connect_url, "https://coverity.example.com");

    restore_settings(&pool, &COVERITY_SETTING_KEYS, &snapshot).await;
}

#[actix_web::test]
#[serial]
async fn specs_draft_initialize_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_bamboo_fixture(&pool).await;
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
        test::TestRequest::post()
            .uri("/api/v1/system-settings/specs-drafts/initialize?resetExisting=true")
            .insert_header(("Authorization", format!("Bearer {TEST_TOKEN}")))
            .to_request(),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let payload: serde_json::Value = test::read_body_json(response).await;
    assert_eq!(payload["initializedCount"], 0);
    assert_eq!(payload["updatedCount"], 1);
    assert_eq!(payload["removedCount"], 0);
    assert_eq!(payload["skippedCount"], 0);

    let build_info = sqlx::query(
        r#"
        SELECT operating_system, build_sub_path
        FROM buildmeta_bamboo_build_info
        WHERE bamboo_build_unit_id = $1 AND build_key = 'api-linux'
        "#,
    )
    .bind(fixture.build_unit_id)
    .fetch_one(&pool)
    .await
    .expect("bamboo build info must exist");
    let operating_system: String = build_info.get("operating_system");
    let build_sub_path: String = build_info.get("build_sub_path");
    assert_eq!(operating_system, "linux");
    assert_eq!(build_sub_path, fixture.build_sub_path);
}

#[actix_web::test]
#[serial]
async fn build_plan_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_bamboo_fixture(&pool).await;
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

    let active_definition_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/build-plans/{}/active-definition", fixture.plan_key))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(active_definition_response.status(), StatusCode::OK);
    let active_definition_payload: serde_json::Value =
        test::read_body_json(active_definition_response).await;
    assert_eq!(active_definition_payload["planKey"], fixture.plan_key);
    assert_eq!(active_definition_payload["definition"]["buildId"], fixture.build_id);
    assert_eq!(
        active_definition_payload["definition"]["repository"]["applicationLink"],
        APPLICATION_LINK
    );
    assert_eq!(
        active_definition_payload["definition"]["build"]["subPath"],
        fixture.build_sub_path
    );

    let prepare_context_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/build-plans/{}/prepare-context", fixture.plan_key))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(prepare_context_response.status(), StatusCode::OK);
    let prepare_context_payload: serde_json::Value = test::read_body_json(prepare_context_response).await;
    assert_eq!(prepare_context_payload["project"]["jiraProjectKey"], fixture.project_key);
    assert_eq!(prepare_context_payload["variables"]["BITBUCKET_REPO_SLUG"], fixture.repo_slug);
    assert_eq!(
        prepare_context_payload["variables"]["BITBUCKET_APPLICATION_LINK"],
        APPLICATION_LINK
    );
    assert_eq!(
        prepare_context_payload["currentRepository"]["applicationLink"],
        APPLICATION_LINK
    );
    assert_eq!(prepare_context_payload["currentRepository"]["linkageMode"], "linked");
}

#[actix_web::test]
#[serial]
async fn build_plan_list_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_bamboo_fixture(&pool).await;
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
            .uri("/api/v1/build-plans")
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);

    let payload: serde_json::Value = test::read_body_json(response).await;
    let plans = payload.as_array().expect("build plan list should be an array");
    assert_eq!(plans.len(), 1);
    assert_eq!(plans[0]["projectKey"], fixture.project_key);
    assert_eq!(plans[0]["planKey"], fixture.plan_key);
    assert_eq!(plans[0]["buildId"], fixture.build_id);
    assert_eq!(plans[0]["repositorySlug"], fixture.repo_slug);
    assert_eq!(plans[0]["buildInfoCount"], 1);
}

#[actix_web::test]
#[serial]
async fn prepare_context_contract_respects_create_if_missing_settings() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_bamboo_fixture(&pool).await;
    let snapshot = snapshot_settings(&pool, &PREPARE_CONTEXT_SETTING_KEYS).await;
    unsafe { std::env::set_var("BAMBOO_API_TOKEN", TEST_TOKEN); }

    sqlx::query(
        r#"
        INSERT INTO buildmeta_systemsetting (id, created_at, updated_at, key, value, description)
        VALUES
            ($1, NOW(), NOW(), 'repository.git.clone_url_template', $2, 'Git clone URL template'),
            ($3, NOW(), NOW(), 'repository.linkage_mode', 'create_if_missing', 'Repository linkage mode')
        ON CONFLICT (key)
        DO UPDATE SET value = EXCLUDED.value, description = EXCLUDED.description, updated_at = NOW()
        "#,
    )
    .bind(Uuid::new_v4())
    .bind("https://git.example.com/scm/{project_key_lower}/{repo_slug}.git")
    .bind(Uuid::new_v4())
    .execute(&pool)
    .await
    .expect("Failed to seed prepare-context settings");

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
            .uri(&format!("/api/v1/build-plans/{}/prepare-context", fixture.plan_key))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(response.status(), StatusCode::OK);
    let payload: serde_json::Value = test::read_body_json(response).await;
    assert_eq!(payload["currentRepository"]["linkageMode"], "create_if_missing");
    assert_eq!(
        payload["currentRepository"]["cloneUrl"],
        format!(
            "https://git.example.com/scm/{}/{}.git",
            fixture.project_key.to_lowercase(),
            fixture.repo_slug
        )
    );
    assert_eq!(
        payload["variables"]["currentRepository.linkageMode"],
        "create_if_missing"
    );

    restore_settings(&pool, &PREPARE_CONTEXT_SETTING_KEYS, &snapshot).await;
}

#[actix_web::test]
#[serial]
async fn executions_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_bamboo_fixture(&pool).await;
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

    let start_response = test::call_service(
        &app,
        test::TestRequest::post()
            .uri(&format!("/api/v1/build-plans/{}/executions/start", fixture.plan_key))
            .insert_header(auth_header())
            .set_json(serde_json::json!({
                "branchKind": "dev",
                "commitHash": "abcdef123456",
                "buildNumber": "101",
                "startedAt": "2026-03-19T00:00:00Z"
            }))
            .to_request(),
    )
    .await;
    let start_status = start_response.status();
    let start_payload: serde_json::Value = test::read_body_json(start_response).await;
    assert_eq!(start_status, StatusCode::OK, "unexpected start payload: {start_payload}");
    assert_eq!(start_payload["version"], "v0.0.1");
    assert_eq!(start_payload["reusedExistingVersion"], false);

    let execution_id = start_payload["buildExecutionId"]
        .as_str()
        .expect("buildExecutionId must be present")
        .to_string();

    let finish_response = test::call_service(
        &app,
        test::TestRequest::post()
            .uri(&format!("/api/v1/build-executions/{execution_id}/finish"))
            .insert_header(auth_header())
            .set_json(serde_json::json!({
                "success": true,
                "resultStatus": "successful",
                "summaryMessage": "Build passed",
                "stageName": "Static Analysis",
                "jobName": "Coverity Scan",
                "taskName": "run_coverity.py",
                "finishedAt": "2026-03-19T00:12:00Z",
                "staticAnalysisResults": [
                    {
                        "toolName": "coverity",
                        "status": "passed",
                        "summary": "0 high impact defects",
                        "metricsJson": {"high": 0}
                    }
                ]
            }))
            .to_request(),
    )
    .await;
    assert_eq!(finish_response.status(), StatusCode::OK);
    let finish_payload: serde_json::Value = test::read_body_json(finish_response).await;
    assert_eq!(finish_payload["success"], true);
    assert_eq!(finish_payload["resultStatus"], "successful");

    let list_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/build-plans/{}/executions", fixture.plan_key))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(list_response.status(), StatusCode::OK);
    let list_payload: serde_json::Value = test::read_body_json(list_response).await;
    let executions = list_payload.as_array().expect("executions payload must be an array");
    assert_eq!(executions.len(), 1);
    assert_eq!(executions[0]["version"], "v0.0.1");
    assert_eq!(executions[0]["resultStatus"], "successful");
    assert_eq!(executions[0]["staticAnalysisResults"][0]["toolName"], "coverity");
}

#[actix_web::test]
#[serial]
async fn static_analysis_upsert_contract_matches_django_smoke_fixture() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_bamboo_fixture(&pool).await;
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

    let start_response = test::call_service(
        &app,
        test::TestRequest::post()
            .uri(&format!("/api/v1/build-plans/{}/executions/start", fixture.plan_key))
            .insert_header(auth_header())
            .set_json(serde_json::json!({
                "branchKind": "dev",
                "commitHash": "abcdef123456",
                "buildNumber": "101"
            }))
            .to_request(),
    )
    .await;
    let start_status = start_response.status();
    let start_payload: serde_json::Value = test::read_body_json(start_response).await;
    assert_eq!(start_status, StatusCode::OK, "unexpected start payload: {start_payload}");
    let execution_id = start_payload["buildExecutionId"]
        .as_str()
        .expect("buildExecutionId must be present")
        .to_string();

    let upsert_response = test::call_service(
        &app,
        test::TestRequest::post()
            .uri(&format!(
                "/api/v1/build-executions/{execution_id}/static-analysis-results"
            ))
            .insert_header(auth_header())
            .set_json(serde_json::json!({
                "staticAnalysisResults": [
                    {
                        "toolName": "coverity",
                        "status": "passed",
                        "summary": "0 high impact defects",
                        "metricsJson": {"high": 0}
                    }
                ]
            }))
            .to_request(),
    )
    .await;
    assert_eq!(upsert_response.status(), StatusCode::OK);
    let upsert_payload: serde_json::Value = test::read_body_json(upsert_response).await;
    assert_eq!(upsert_payload["updatedCount"], 1);

    let list_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/build-plans/{}/executions", fixture.plan_key))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(list_response.status(), StatusCode::OK);
    let list_payload: serde_json::Value = test::read_body_json(list_response).await;
    assert_eq!(list_payload[0]["staticAnalysisResults"][0]["toolName"], "coverity");
}

#[actix_web::test]
#[serial]
async fn jenkins_contract_matches_django_service_behavior() {
    let pool = contract_pool().await;
    reset_contract_tables(&pool).await;
    let fixture = seed_jenkins_fixture(&pool).await;
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

    let list_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri("/api/v1/jenkins-jobs")
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(list_response.status(), StatusCode::OK);
    let list_payload: serde_json::Value = test::read_body_json(list_response).await;
    let jobs = list_payload.as_array().expect("jenkins jobs payload must be an array");
    assert_eq!(jobs.len(), 1);
    assert_eq!(jobs[0]["projectKey"], fixture.project_key);
    assert_eq!(jobs[0]["repositorySlug"], fixture.repo_slug);
    assert_eq!(jobs[0]["jobPath"], fixture.job_path);

    let pre_status_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/jenkins-jobs/{}/status", fixture.job_path))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(pre_status_response.status(), StatusCode::OK);
    let pre_status_payload: serde_json::Value = test::read_body_json(pre_status_response).await;
    if pre_status_payload["configured"] != true {
        assert_eq!(pre_status_payload["exists"], false);
        return;
    }
    assert_eq!(pre_status_payload["exists"], false);

    let configure_response = test::call_service(
        &app,
        test::TestRequest::post()
            .uri(&format!("/api/v1/jenkins-jobs/{}/configure", fixture.job_path))
            .insert_header(auth_header())
            .set_json(serde_json::json!({}))
            .to_request(),
    )
    .await;
    assert_eq!(configure_response.status(), StatusCode::OK);
    let configure_payload: serde_json::Value = test::read_body_json(configure_response).await;
    assert_eq!(configure_payload["configured"], true);
    assert_eq!(configure_payload["jobPath"], fixture.job_path);

    let status_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/jenkins-jobs/{}/status", fixture.job_path))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(status_response.status(), StatusCode::OK);
    let status_payload: serde_json::Value = test::read_body_json(status_response).await;
    assert_eq!(status_payload["configured"], true);
    assert_eq!(status_payload["exists"], true);
    assert!(
        status_payload["jobName"]
            .as_str()
            .unwrap_or("")
            .starts_with("jenkins-contract-")
    );

    let details_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/jenkins-jobs/{}/details", fixture.job_path))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(details_response.status(), StatusCode::OK);
    let details_payload: serde_json::Value = test::read_body_json(details_response).await;
    assert_eq!(details_payload["jobPath"], fixture.job_path);
    assert_eq!(details_payload["summary"]["fullName"], fixture.job_path);

    let executions_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri(&format!("/api/v1/jenkins-jobs/{}/executions", fixture.job_path))
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(executions_response.status(), StatusCode::OK);
    let executions_payload: serde_json::Value = test::read_body_json(executions_response).await;
    assert_eq!(executions_payload, serde_json::json!([]));

    let trigger_response = test::call_service(
        &app,
        test::TestRequest::post()
            .uri(&format!("/api/v1/jenkins-jobs/{}/trigger", fixture.job_path))
            .insert_header(auth_header())
            .set_json(serde_json::json!({}))
            .to_request(),
    )
    .await;
    let trigger_status = trigger_response.status();
    let trigger_payload: serde_json::Value = test::read_body_json(trigger_response).await;
    assert_eq!(trigger_status, StatusCode::OK, "unexpected trigger payload: {trigger_payload}");
    assert_eq!(trigger_payload["queued"], true);
    assert_eq!(trigger_payload["parameters"], serde_json::json!({}));

    let mut build_found = false;
    for _ in 0..30 {
        let build_response = test::call_service(
            &app,
            test::TestRequest::get()
                .uri(&format!("/api/v1/jenkins-jobs/{}/builds/1", fixture.job_path))
                .insert_header(auth_header())
                .to_request(),
        )
        .await;
        if build_response.status() == StatusCode::OK {
            let build_payload: serde_json::Value = test::read_body_json(build_response).await;
            assert_eq!(build_payload["jobPath"], fixture.job_path);
            assert_eq!(build_payload["buildNumber"], "1");
            build_found = true;
            break;
        }
        sleep(Duration::from_secs(1)).await;
    }
    assert!(build_found, "Jenkins build #1 was not visible within timeout");

    let system_status_response = test::call_service(
        &app,
        test::TestRequest::get()
            .uri("/api/v1/jenkins-jobs/system-status")
            .insert_header(auth_header())
            .to_request(),
    )
    .await;
    assert_eq!(system_status_response.status(), StatusCode::OK);
    let system_status_payload: serde_json::Value = test::read_body_json(system_status_response).await;
    assert_eq!(system_status_payload["connected"], true);
    assert!(system_status_payload["serverUrl"].as_str().unwrap_or("").starts_with("http"));

    delete_jenkins_job(&pool, &fixture.job_path).await;
}
