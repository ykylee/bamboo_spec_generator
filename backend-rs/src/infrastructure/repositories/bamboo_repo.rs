use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{Datelike, Utc};
use serde_json::{json, Value};
use sqlx::{PgPool, Row};
use tokio::process::Command;
use uuid::Uuid;

use crate::infrastructure::external::bamboo_client::{BambooClient, BambooError};

const KEY_BAMBOO_SERVER_URL: &str = "bamboo.server.url";

#[derive(Debug, Clone)]
pub struct BambooQueueRequest {
    pub stage: String,
    pub execute_all_stages: bool,
    pub custom_revision: String,
    pub variables: BTreeMap<String, String>,
}

#[derive(Debug, Clone)]
struct BambooPlanRecord {
    build_unit_id: Uuid,
    project_key: String,
    plan_key: String,
    build_id: String,
    active_year: String,
}

#[derive(Debug, Clone)]
struct BambooConfig {
    server_url: String,
    token: String,
    token_file_path: Option<PathBuf>,
}

pub async fn get_plan_status(pool: &PgPool, plan_key: &str) -> Result<Value, String> {
    let Some(plan) = fetch_plan(pool, plan_key).await.map_err(|error| error.to_string())? else {
        return Ok(json!({
            "configured": false,
            "exists": false,
            "error": "Build plan not found.",
        }));
    };

    let identity = build_identity(&plan);
    let settings = get_bamboo_settings(pool).await.map_err(|error| error.to_string())?;
    if settings.server_url.is_empty() {
        return Ok(merge_identity(
            &identity,
            json!({
                "configured": false,
                "exists": false,
                "message": "Bamboo 서버 URL이 아직 설정되지 않았습니다.",
            }),
        ));
    }
    if settings.token.is_empty() {
        return Ok(merge_identity(
            &identity,
            json!({
                "configured": false,
                "exists": false,
                "message": "Bamboo 서버 토큰이 아직 설정되지 않았습니다.",
            }),
        ));
    }

    let client = BambooClient::new(&settings.server_url, &settings.token);
    let plan_payload = match client
        .get_plan(&plan.project_key, &plan.plan_key, None)
        .await
    {
        Ok(payload) => payload,
        Err(error) => {
            return Ok(merge_identity(
                &identity,
                json!({
                    "configured": true,
                    "exists": false,
                    "message": bamboo_error_summary(&error),
                    "detail": bamboo_error_detail(&error),
                }),
            ));
        }
    };

    let Some(plan_payload) = plan_payload else {
        return Ok(merge_identity(
            &identity,
            json!({
                "configured": true,
                "exists": false,
                "message": "Bamboo에 아직 등록되지 않았습니다.",
                "planUrl": plan_browse_url(&settings.server_url, &identity["fullPlanKey"].as_str().unwrap_or_default()),
            }),
        ));
    };

    let latest_result = client
        .get_latest_result(identity["fullPlanKey"].as_str().unwrap_or_default())
        .await
        .unwrap_or_else(|_| json!({}));
    let latest_result = extract_latest_result(&latest_result);

    Ok(merge_identity(&identity, json!({
        "configured": true,
        "exists": true,
        "message": "Bamboo에 등록되어 있습니다.",
        "planUrl": plan_browse_url(&settings.server_url, &identity["fullPlanKey"].as_str().unwrap_or_default()),
        "enabled": plan_payload.get("enabled").and_then(Value::as_bool).unwrap_or(true),
        "suspended": plan_payload.get("isSuspended").and_then(Value::as_bool).unwrap_or(false),
        "building": plan_payload.get("isBuilding").and_then(Value::as_bool).unwrap_or(false),
        "description": plan_payload.get("description").and_then(Value::as_str).unwrap_or_default(),
        "shortName": plan_payload.get("shortName").and_then(Value::as_str).unwrap_or_default(),
        "latestResultState": latest_result["state"].clone(),
        "latestBuildNumber": latest_result["number"].clone(),
        "latestResultKey": latest_result["key"].clone(),
        "latestResultUrl": latest_result["link"].clone(),
    })))
}

pub async fn get_plan_details(pool: &PgPool, plan_key: &str) -> Result<Value, String> {
    let Some(plan) = fetch_plan(pool, plan_key).await.map_err(|error| error.to_string())? else {
        return Err("Build plan을 찾지 못했습니다.".to_string());
    };
    let identity = build_identity(&plan);
    let settings = get_bamboo_settings(pool).await.map_err(|error| error.to_string())?;
    if settings.server_url.is_empty() {
        return Err("Bamboo 서버 URL이 아직 설정되지 않았습니다.".to_string());
    }
    if settings.token.is_empty() {
        return Err("Bamboo 서버 토큰이 아직 설정되지 않았습니다.".to_string());
    }

    let client = BambooClient::new(&settings.server_url, &settings.token);
    let Some(plan_payload) = client
        .get_plan(
            &plan.project_key,
            &plan.plan_key,
            Some("stages.stage.jobs.job,stages.stage.plans.plan,branches.branch,actions.action,variableContext"),
        )
        .await
        .map_err(|error| bamboo_error_summary(&error))?
    else {
        return Err("Bamboo에 해당 plan이 등록되어 있지 않습니다.".to_string());
    };

    Ok(merge_identity(&identity, json!({
        "planUrl": plan_browse_url(&settings.server_url, &identity["fullPlanKey"].as_str().unwrap_or_default()),
        "raw": plan_payload,
        "summary": {
            "shortName": plan_payload.get("shortName").and_then(Value::as_str).unwrap_or_default(),
            "description": plan_payload.get("description").and_then(Value::as_str).unwrap_or_default(),
            "enabled": plan_payload.get("enabled").and_then(Value::as_bool).unwrap_or(true),
            "suspended": plan_payload.get("isSuspended").and_then(Value::as_bool).unwrap_or(false),
            "building": plan_payload.get("isBuilding").and_then(Value::as_bool).unwrap_or(false),
        },
        "stages": extract_stages(&plan_payload),
        "branches": extract_named_items(plan_payload.get("branches"), "branch"),
        "actions": extract_named_items(plan_payload.get("actions"), "action"),
        "variables": extract_variables(plan_payload.get("variableContext")),
        "recentPublishExecutions": list_publish_executions(pool, &plan.plan_key).await.map_err(|error| error.to_string())?,
    })))
}

pub async fn queue_plan(
    pool: &PgPool,
    plan_key: &str,
    request: BambooQueueRequest,
) -> Result<Value, String> {
    let Some(plan) = fetch_plan(pool, plan_key).await.map_err(|error| error.to_string())? else {
        return Err("Build plan을 찾지 못했습니다.".to_string());
    };
    let identity = build_identity(&plan);
    let settings = get_bamboo_settings(pool).await.map_err(|error| error.to_string())?;
    if settings.server_url.is_empty() {
        return Err("Bamboo 서버 URL이 아직 설정되지 않았습니다.".to_string());
    }
    if settings.token.is_empty() {
        return Err("Bamboo 서버 토큰이 아직 설정되지 않았습니다.".to_string());
    }

    let client = BambooClient::new(&settings.server_url, &settings.token);
    let payload = client
        .queue_plan(
            identity["fullPlanKey"].as_str().unwrap_or_default(),
            &request.stage,
            request.execute_all_stages,
            &request.custom_revision,
            &request.variables,
        )
        .await
        .map_err(|error| bamboo_error_summary(&error))?;

    Ok(merge_identity(&identity, json!({
        "queued": true,
        "message": "Bamboo plan 실행을 요청했습니다.",
        "stage": request.stage,
        "executeAllStages": request.execute_all_stages,
        "customRevision": request.custom_revision,
        "variables": request.variables,
        "detail": format_queue_detail(&request),
        "raw": payload,
    })))
}

pub async fn publish_plan_specs(pool: &PgPool, plan_key: &str) -> Result<Value, String> {
    let Some(plan) = fetch_plan(pool, plan_key).await.map_err(|error| error.to_string())? else {
        return Err("Build plan을 찾지 못했습니다.".to_string());
    };
    let config = get_bamboo_settings(pool).await.map_err(|error| error.to_string())?;
    if config.server_url.is_empty() {
        record_publish_execution(
            pool,
            plan.build_unit_id,
            "failed",
            "Bamboo 서버 URL이 설정되지 않았습니다.",
            "",
            None,
        )
        .await
        .map_err(|error| error.to_string())?;
        return Err("Bamboo 서버 URL이 설정되지 않았습니다.".to_string());
    }
    if config.token.is_empty() {
        record_publish_execution(
            pool,
            plan.build_unit_id,
            "failed",
            "Bamboo 토큰이 설정되지 않았습니다.",
            "",
            None,
        )
        .await
        .map_err(|error| error.to_string())?;
        return Err("Bamboo 토큰이 설정되지 않았습니다.".to_string());
    }

    let repo_root = repo_root();
    let output_root = env::temp_dir().join(format!("bamboo-publish-{}-{}", plan_key.to_lowercase(), Uuid::new_v4()));
    let specs_root = output_root.join("bamboo-specs");

    let api_base_url = internal_api_base_url();
    let api_token = env::var("BAMBOO_API_TOKEN").unwrap_or_default();
    let mut generate_command = Command::new("python3");
    generate_command
        .current_dir(&repo_root)
        .env("PYTHONPATH", &repo_root)
        .env("BAMBOO_API_BASE_URL", api_base_url)
        .env("BAMBOO_API_TOKEN", api_token)
        .arg("-m")
        .arg("src.bamboo_spec_generator.cli")
        .arg("--api-plan-key")
        .arg(plan_key)
        .arg("--output-root")
        .arg(&specs_root);
    let generate_output = generate_command.output().await.map_err(|error| error.to_string())?;
    if !generate_output.status.success() {
        let output = join_output(&generate_output.stdout, &generate_output.stderr);
        record_publish_execution(
            pool,
            plan.build_unit_id,
            "failed",
            "Bamboo Specs 생성에 실패했습니다.",
            &output,
            generate_output.status.code(),
        )
        .await
        .map_err(|error| error.to_string())?;
        let _ = fs::remove_dir_all(&output_root);
        return Ok(json!({
            "success": false,
            "returnCode": generate_output.status.code(),
            "message": "Bamboo Specs 생성에 실패했습니다.",
            "output": output,
            "detail": output,
        }));
    }

    let (token_path, remove_token_file) = prepare_bamboo_token_file(&config).map_err(|error| error.to_string())?;
    let mut publish_command = Command::new("mvn");
    publish_command
        .current_dir(&specs_root)
        .env("BAMBOO_URL", &config.server_url)
        .env("BAMBOO_TOKEN_FILE", &token_path)
        .arg("-q")
        .arg("-DskipTests")
        .arg("compile")
        .arg("exec:java");
    let publish_output = publish_command.output().await.map_err(|error| error.to_string())?;
    let output = join_output(&publish_output.stdout, &publish_output.stderr);
    let success = publish_output.status.success();
    record_publish_execution(
        pool,
        plan.build_unit_id,
        if success { "successful" } else { "failed" },
        if success {
            "Bamboo Specs publish가 완료되었습니다."
        } else {
            "Bamboo Specs publish에 실패했습니다."
        },
        &output,
        publish_output.status.code(),
    )
    .await
    .map_err(|error| error.to_string())?;

    if remove_token_file {
        let _ = fs::remove_file(&token_path);
    }
    let _ = fs::remove_dir_all(&output_root);

    Ok(json!({
        "success": success,
        "returnCode": publish_output.status.code(),
        "message": if success { "Bamboo Specs publish가 완료되었습니다." } else { "Bamboo Specs publish에 실패했습니다." },
        "output": output,
        "detail": output,
    }))
}

async fn fetch_plan(pool: &PgPool, plan_key: &str) -> Result<Option<BambooPlanRecord>, sqlx::Error> {
    let row = sqlx::query(
        r#"
        SELECT
            bu.id AS build_unit_id,
            bamboo.plan_key,
            bamboo.build_id,
            COALESCE((
                SELECT def.year
                FROM buildmeta_build_unit_definition def
                WHERE def.build_unit_id = bu.id AND def.is_active = true
                ORDER BY def.created_at DESC
                LIMIT 1
            ), '') AS active_year
        FROM buildmeta_bamboo_build_unit bamboo
        JOIN buildmeta_build_unit bu ON bu.id = bamboo.build_unit_id
        WHERE bamboo.plan_key = $1
        "#,
    )
    .bind(plan_key)
    .fetch_optional(pool)
    .await?;

    Ok(row.map(|row| BambooPlanRecord {
        build_unit_id: row.get("build_unit_id"),
        project_key: resolve_bamboo_project_key(row.get::<String, _>("active_year")),
        plan_key: row.get("plan_key"),
        build_id: row.get("build_id"),
        active_year: row.get("active_year"),
    }))
}

async fn get_bamboo_settings(pool: &PgPool) -> Result<BambooConfig, sqlx::Error> {
    let configured_url = get_setting(pool, KEY_BAMBOO_SERVER_URL).await?;
    let server_url = if configured_url.trim().is_empty() {
        env::var("BAMBOO_URL").unwrap_or_default().trim().to_string()
    } else {
        configured_url.trim().to_string()
    };

    let env_declared = env::var_os("BAMBOO_SERVER_TOKEN").is_some();
    let env_token = env::var("BAMBOO_SERVER_TOKEN").unwrap_or_default();
    let file_path = repo_root().join("ops").join("credentials").join(".credentials");
    let file_token = if !env_declared && file_path.is_file() {
        fs::read_to_string(&file_path).unwrap_or_default()
    } else {
        String::new()
    };
    let api_token = if !env_declared && file_token.trim().is_empty() {
        env::var("BAMBOO_API_TOKEN")
            .or_else(|_| env::var("BAMBOO_TOKEN"))
            .unwrap_or_default()
    } else {
        String::new()
    };
    let token = normalize_bamboo_token(&(if !env_token.trim().is_empty() {
        env_token
    } else if !file_token.trim().is_empty() {
        file_token
    } else {
        api_token
    }));

    Ok(BambooConfig {
        server_url: server_url.trim_end_matches('/').to_string(),
        token,
        token_file_path: if !env_declared && file_path.is_file() {
            Some(file_path)
        } else {
            None
        },
    })
}

async fn get_setting(pool: &PgPool, key: &str) -> Result<String, sqlx::Error> {
    sqlx::query_scalar::<_, String>(
        "SELECT COALESCE(value, '') FROM buildmeta_systemsetting WHERE key = $1 LIMIT 1",
    )
    .bind(key)
    .fetch_optional(pool)
    .await
    .map(|value| value.unwrap_or_default())
}

async fn list_publish_executions(pool: &PgPool, plan_key: &str) -> Result<Vec<Value>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT execution.id, execution.status, execution.message, execution.output, execution.return_code, execution.created_at
        FROM buildmeta_bamboo_publish_execution execution
        JOIN buildmeta_bamboo_build_unit bamboo ON bamboo.build_unit_id = execution.build_unit_id
        WHERE bamboo.plan_key = $1
        ORDER BY execution.created_at DESC
        LIMIT 5
        "#,
    )
    .bind(plan_key)
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|row| {
            json!({
                "publishExecutionId": row.get::<Uuid, _>("id").to_string(),
                "status": row.get::<String, _>("status"),
                "message": row.get::<String, _>("message"),
                "output": row.get::<String, _>("output"),
                "returnCode": row.get::<Option<i32>, _>("return_code"),
                "triggerSource": "api",
                "requestedBy": "",
                "createdAt": row.get::<chrono::DateTime<Utc>, _>("created_at").to_rfc3339(),
            })
        })
        .collect())
}

async fn record_publish_execution(
    pool: &PgPool,
    build_unit_id: Uuid,
    status: &str,
    message: &str,
    output: &str,
    return_code: Option<i32>,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        r#"
        INSERT INTO buildmeta_bamboo_publish_execution (
            id, created_at, updated_at, build_unit_id, status, message, output,
            snapshot_preview_json, snapshot_export_draft_json, return_code
        )
        VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, NULL, NULL, $6)
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(build_unit_id)
    .bind(status)
    .bind(message)
    .bind(output)
    .bind(return_code)
    .execute(pool)
    .await?;
    Ok(())
}

fn build_identity(plan: &BambooPlanRecord) -> Value {
    json!({
        "projectKey": plan.project_key,
        "planKey": plan.plan_key,
        "buildId": plan.build_id,
        "fullPlanKey": format!("{}-{}", plan.project_key, plan.plan_key),
        "year": if plan.active_year.trim().is_empty() { Utc::now().year().to_string() } else { plan.active_year.clone() },
    })
}

fn merge_identity(identity: &Value, payload: Value) -> Value {
    let mut merged = identity.as_object().cloned().unwrap_or_default();
    if let Some(payload) = payload.as_object() {
        for (key, value) in payload {
            merged.insert(key.clone(), value.clone());
        }
    }
    Value::Object(merged)
}

fn resolve_bamboo_project_key(active_year: String) -> String {
    if active_year.trim().is_empty() {
        format!("Y{}", Utc::now().year())
    } else {
        format!("Y{}", active_year.trim())
    }
}

fn plan_browse_url(server_url: &str, full_plan_key: &str) -> String {
    if server_url.trim().is_empty() {
        return String::new();
    }
    format!("{}/browse/{}", server_url.trim_end_matches('/'), full_plan_key)
}

fn bamboo_error_summary(error: &BambooError) -> String {
    match error {
        BambooError::AuthFailed(_) => "Bamboo 인증에 실패했습니다.".to_string(),
        BambooError::NotFound(message) => message.clone(),
        BambooError::Api(message) => format!("Bamboo API 요청이 실패했습니다. {}", message).trim().to_string(),
        BambooError::Request(message) => format!("Bamboo API 연결에 실패했습니다. {}", message).trim().to_string(),
    }
}

fn bamboo_error_detail(error: &BambooError) -> String {
    match error {
        BambooError::AuthFailed(message) => message.clone(),
        BambooError::NotFound(message) => message.clone(),
        BambooError::Api(message) => message.clone(),
        BambooError::Request(message) => message.to_string(),
    }
}

fn extract_latest_result(payload: &Value) -> Value {
    let result = payload
        .get("results")
        .and_then(|value| value.get("result"))
        .and_then(|value| value.as_array())
        .and_then(|items| items.first().cloned())
        .or_else(|| payload.get("result").and_then(Value::as_object).map(|_| payload["result"].clone()))
        .unwrap_or_else(|| json!({}));

    let link = result
        .get("link")
        .and_then(|value| {
            value
                .get("href")
                .and_then(Value::as_str)
                .or_else(|| value.get("url").and_then(Value::as_str))
                .or_else(|| value.as_str())
        })
        .unwrap_or_default()
        .to_string();
    let normalized_key = result
        .get("key")
        .and_then(Value::as_str)
        .or_else(|| {
            result
                .get("planResultKey")
                .and_then(|value| value.get("key"))
                .and_then(Value::as_str)
        })
        .unwrap_or_default()
        .to_string();
    json!({
        "state": result.get("state").or_else(|| result.get("buildState")).and_then(Value::as_str).unwrap_or_default(),
        "number": result.get("number").or_else(|| result.get("buildNumber")).map(|value| {
            value.as_str().map(ToString::to_string).unwrap_or_else(|| value.to_string())
        }).unwrap_or_default(),
        "key": normalized_key,
        "link": link,
    })
}

fn extract_stages(payload: &Value) -> Vec<Value> {
    let stage_items = payload
        .get("stages")
        .and_then(|value| value.get("stage").or(Some(value)))
        .cloned()
        .unwrap_or_else(|| json!([]));
    let stages = if let Some(items) = stage_items.as_array() {
        items.clone()
    } else if stage_items.is_object() {
        vec![stage_items]
    } else {
        Vec::new()
    };
    stages
        .into_iter()
        .filter_map(|stage| {
            let jobs = extract_stage_jobs(&stage)
                .into_iter()
                .filter_map(|job| {
                    Some(json!({
                        "key": job.get("key")?.as_str().unwrap_or_default(),
                        "name": job.get("name").and_then(Value::as_str).unwrap_or_default(),
                    }))
                })
                .collect::<Vec<_>>();
            Some(json!({
                "name": stage.get("name").and_then(Value::as_str).unwrap_or_default(),
                "description": stage.get("description").and_then(Value::as_str).unwrap_or_default(),
                "jobs": jobs,
            }))
        })
        .collect()
}

fn extract_stage_jobs(stage: &Value) -> Vec<Value> {
    if let Some(items) = stage.get("jobs").and_then(|value| value.get("job")) {
        if let Some(items) = items.as_array() {
            return items.clone();
        }
        if items.is_object() {
            return vec![items.clone()];
        }
    }
    if let Some(items) = stage.get("plans").and_then(|value| value.get("plan").or(Some(value))) {
        if let Some(items) = items.as_array() {
            return items.clone();
        }
        if items.is_object() {
            return vec![items.clone()];
        }
    }
    Vec::new()
}

fn extract_named_items(container: Option<&Value>, item_key: &str) -> Vec<Value> {
    let Some(container) = container else {
        return Vec::new();
    };
    let items = container.get(item_key).unwrap_or(container);
    let items = if let Some(items) = items.as_array() {
        items.clone()
    } else if items.is_object() {
        vec![items.clone()]
    } else {
        Vec::new()
    };
    items
        .into_iter()
        .filter_map(|item| {
            let mut payload = json!({
                "name": item.get("name").and_then(Value::as_str).unwrap_or_default(),
            });
            if let Some(key) = item.get("key").and_then(Value::as_str) {
                payload["key"] = Value::String(key.to_string());
            }
            Some(payload)
        })
        .collect()
}

fn extract_variables(container: Option<&Value>) -> Vec<Value> {
    let Some(container) = container else {
        return Vec::new();
    };
    let mut variables = container.get("variable").cloned();
    if variables.is_none() {
        variables = container
            .get("variables")
            .and_then(|value| value.get("variable").or(Some(value)))
            .cloned();
    }
    let items = if let Some(variables) = variables {
        if let Some(items) = variables.as_array() {
            items.clone()
        } else if variables.is_object() {
            vec![variables]
        } else {
            Vec::new()
        }
    } else if let Some(object) = container.as_object() {
        return object
            .iter()
            .filter(|(_, value)| !value.is_object())
            .map(|(key, value)| {
                json!({
                    "key": key,
                    "value": value.as_str().map(ToString::to_string).unwrap_or_else(|| value.to_string()),
                })
            })
            .collect();
    } else {
        Vec::new()
    };
    let mut mapped = items
        .into_iter()
        .map(|item| {
            json!({
                "key": item.get("key").or_else(|| item.get("name")).and_then(Value::as_str).unwrap_or_default(),
                "value": item
                    .get("value")
                    .or_else(|| item.get("valueAsString"))
                    .map(|value| value.as_str().map(ToString::to_string).unwrap_or_else(|| value.to_string()))
                    .unwrap_or_default(),
            })
        })
        .collect::<Vec<_>>();
    mapped.sort_by(|left, right| left["key"].as_str().cmp(&right["key"].as_str()));
    mapped
}

fn format_queue_detail(request: &BambooQueueRequest) -> String {
    let mut lines = vec![
        format!(
            "stage={}",
            if request.stage.trim().is_empty() {
                "-"
            } else {
                request.stage.trim()
            }
        ),
        format!(
            "executeAllStages={}",
            if request.execute_all_stages { "true" } else { "false" }
        ),
        format!(
            "customRevision={}",
            if request.custom_revision.trim().is_empty() {
                "-"
            } else {
                request.custom_revision.trim()
            }
        ),
    ];
    if !request.variables.is_empty() {
        lines.push("variables=".to_string());
        for (key, value) in &request.variables {
            lines.push(format!("  {}={}", key, value));
        }
    }
    lines.join("\n")
}

fn normalize_bamboo_token(value: &str) -> String {
    let trimmed = value.trim();
    if let Some(token) = trimmed.strip_prefix("token=") {
        token.trim().to_string()
    } else {
        trimmed.to_string()
    }
}

fn prepare_bamboo_token_file(config: &BambooConfig) -> Result<(PathBuf, bool), std::io::Error> {
    if let Some(path) = config.token_file_path.clone().filter(|path| path.is_file()) {
        return Ok((path, false));
    }
    let path = env::temp_dir().join(format!("bamboo-token-{}.txt", Uuid::new_v4()));
    fs::write(&path, &config.token)?;
    Ok((path, true))
}

fn join_output(stdout: &[u8], stderr: &[u8]) -> String {
    let stdout = String::from_utf8_lossy(stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(stderr).trim().to_string();
    [stdout, stderr]
        .into_iter()
        .filter(|value| !value.is_empty())
        .collect::<Vec<_>>()
        .join("\n")
}

fn internal_api_base_url() -> String {
    let port = env::var("SERVER_PORT").unwrap_or_else(|_| "8080".to_string());
    let scheme = env::var("SERVER_SCHEME").unwrap_or_else(|_| "http".to_string());
    format!("{}://127.0.0.1:{}", scheme, port)
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."))
}
