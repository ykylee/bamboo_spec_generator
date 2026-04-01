use serde_json::{json, Value};
use sqlx::{PgPool, Row};
use uuid::Uuid;

use crate::infrastructure::external::jenkins_client::JenkinsClient;
use crate::infrastructure::repositories::settings_repo;

pub async fn list_jenkins_job_summaries(pool: &PgPool) -> Result<Vec<Value>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            project.project_key,
            bu.id AS build_unit_id,
            bu.display_name,
            bu.compiler,
            bu.runtime_stack,
            bu.external_key,
            COALESCE(repo.repo_slug, '') AS repository_slug,
            COALESCE(jenkins.job_path, '') AS job_path,
            COALESCE(jenkins.job_type, '') AS job_type,
            COALESCE(jenkins.folder_path, '') AS folder_path,
            COALESCE(jenkins.pipeline_kind, '') AS pipeline_kind,
            COALESCE(ver.version_text, '') AS latest_version,
            ver.latest_success,
            COALESCE(exec.status, '') AS latest_execution_status,
            COALESCE(exec.summary, '') AS latest_execution_summary
        FROM buildmeta_build_unit bu
        JOIN buildmeta_project project ON project.id = bu.project_id
        LEFT JOIN buildmeta_repository repo ON repo.id = bu.repository_id
        LEFT JOIN buildmeta_jenkins_build_unit jenkins ON jenkins.build_unit_id = bu.id
        LEFT JOIN buildmeta_build_version ver ON ver.id = bu.latest_version_id
        LEFT JOIN buildmeta_build_execution exec ON exec.id = ver.latest_execution_id
        WHERE bu.ci_provider = 'jenkins'
        ORDER BY project.project_key, bu.display_name, bu.external_key
        "#,
    )
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|row| {
            let project_key: String = row.get("project_key");
            let job_path = effective_job_path(&row);
            json!({
                "projectKey": project_key,
                "buildName": row.get::<String, _>("display_name"),
                "buildType": row.get::<String, _>("compiler"),
                "runtimeStack": row.get::<String, _>("runtime_stack"),
                "jobPath": job_path,
                "jobType": row.get::<String, _>("job_type"),
                "folderPath": row.get::<String, _>("folder_path"),
                "pipelineKind": row.get::<String, _>("pipeline_kind"),
                "repositorySlug": row.get::<String, _>("repository_slug"),
                "latestVersion": row.get::<String, _>("latest_version"),
                "latestSuccess": row.get::<Option<bool>, _>("latest_success"),
                "resultStatus": legacy_result_status(&row.get::<String, _>("latest_execution_status")),
                "summaryMessage": row.get::<String, _>("latest_execution_summary"),
                "detailUrl": format!("/projects/{}/jenkins-jobs/{}/", project_key, job_path),
            })
        })
        .collect())
}

pub async fn get_jenkins_job_status(pool: &PgPool, job_path: &str) -> Result<Option<Value>, String> {
    let row = fetch_job_row(pool, job_path).await.map_err(|e| e.to_string())?;
    let Some(row) = row else {
        return Ok(None);
    };

    let settings = settings_repo::get_jenkins_settings(pool)
        .await
        .map_err(|e| e.to_string())?;
    let server_url = settings.get("serverUrl").and_then(Value::as_str).unwrap_or("");
    let token_configured = settings
        .get("tokenConfigured")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let identity = job_identity(&row);

    if server_url.trim().is_empty() {
        return Ok(Some(with_identity(identity, json!({
            "configured": false,
            "exists": false,
            "message": "Jenkins 서버 URL이 아직 설정되지 않았습니다."
        }))));
    }
    if !token_configured {
        return Ok(Some(with_identity(identity, json!({
            "configured": false,
            "exists": false,
            "message": "Jenkins 서버 토큰이 아직 설정되지 않았습니다."
        }))));
    }

    let full_name = identity
        .get("jobPath")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let client = build_jenkins_client(pool).await?;
    let job_payload = client
        .get_job(&full_name, 0)
        .await
        .map_err(|e| e.to_string())?;
    let Some(job_payload) = job_payload else {
        return Ok(Some(with_identity(identity, json!({
            "configured": true,
            "exists": false,
            "message": "Jenkins에 아직 등록되지 않았습니다.",
            "jobUrl": build_job_url(server_url, &full_name),
        }))));
    };

    let last_build = job_payload.get("lastBuild").cloned().unwrap_or(Value::Null);
    let last_completed = job_payload.get("lastCompletedBuild").cloned().unwrap_or(Value::Null);
    let last_failed = job_payload.get("lastFailedBuild").cloned().unwrap_or(Value::Null);
    let last_successful = job_payload.get("lastSuccessfulBuild").cloned().unwrap_or(Value::Null);
    Ok(Some(with_identity(identity, json!({
        "configured": true,
        "exists": true,
        "message": "Jenkins에 등록되어 있습니다.",
        "jobUrl": build_job_url(server_url, &full_name),
        "displayName": string_field(&job_payload, "displayName"),
        "fullName": full_name,
        "description": string_field(&job_payload, "description"),
        "building": bool_field(&job_payload, "inQueue") || build_number(&last_build).is_some() && build_number(&last_completed) != build_number(&last_build),
        "latestBuildNumber": build_number_text(&last_build),
        "lastBuildResult": build_result(&last_build),
        "lastCompletedBuildNumber": build_number_text(&last_completed),
        "lastCompletedBuildResult": build_result(&last_completed),
        "lastFailedBuildNumber": build_number_text(&last_failed),
        "lastSuccessfulBuildNumber": build_number_text(&last_successful),
        "inQueue": bool_field(&job_payload, "inQueue"),
        "color": string_field(&job_payload, "color"),
    }))))
}

pub async fn get_jenkins_job_details(pool: &PgPool, job_path: &str) -> Result<Option<Value>, String> {
    let row = fetch_job_row(pool, job_path).await.map_err(|e| e.to_string())?;
    let Some(row) = row else {
        return Ok(None);
    };
    let identity = job_identity(&row);
    let client = build_jenkins_client(pool).await?;
    let full_name = identity
        .get("jobPath")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let job_payload = client
        .get_job(&full_name, 1)
        .await
        .map_err(|e| e.to_string())?;
    let Some(job_payload) = job_payload else {
        return Ok(None);
    };

    Ok(Some(with_identity(identity, json!({
        "jobUrl": string_field(&job_payload, "url"),
        "raw": job_payload.clone(),
        "summary": {
            "displayName": string_field(&job_payload, "displayName"),
            "fullName": full_name,
            "description": string_field(&job_payload, "description"),
            "building": bool_field(&job_payload, "inQueue"),
        },
        "builds": extract_build_summaries(job_payload.get("builds")),
        "lastBuild": extract_build_summary(job_payload.get("lastBuild")),
        "lastCompletedBuild": extract_build_summary(job_payload.get("lastCompletedBuild")),
        "lastFailedBuild": extract_build_summary(job_payload.get("lastFailedBuild")),
        "lastSuccessfulBuild": extract_build_summary(job_payload.get("lastSuccessfulBuild")),
        "lastStableBuild": extract_build_summary(job_payload.get("lastStableBuild")),
        "lastUnstableBuild": Value::Null,
    }))))
}

pub async fn list_executions_by_job_path(pool: &PgPool, job_path: &str) -> Result<Vec<Value>, String> {
    let row = fetch_job_row(pool, job_path).await.map_err(|e| e.to_string())?;
    let Some(row) = row else {
        return Err("Jenkins job was not found.".to_string());
    };
    let build_unit_id: Uuid = row.get("build_unit_id");
    let exec_rows = sqlx::query(
        r#"
        SELECT
            exec.id,
            exec.build_version_id,
            exec.external_execution_key,
            exec.execution_number,
            exec.commit_hash,
            exec.status,
            exec.summary,
            exec.stage_name,
            exec.job_name,
            exec.task_name,
            exec.started_at,
            exec.finished_at,
            exec.created_at,
            COALESCE(ver.version_text, '') AS version_text
        FROM buildmeta_build_execution exec
        LEFT JOIN buildmeta_build_version ver ON ver.id = exec.build_version_id
        WHERE exec.build_unit_id = $1
        ORDER BY exec.created_at DESC
        "#,
    )
    .bind(build_unit_id)
    .fetch_all(pool)
    .await
    .map_err(|e| e.to_string())?;

    Ok(exec_rows
        .into_iter()
        .map(|exec| {
            let build_version_id: Option<Uuid> = exec.get("build_version_id");
            let status: String = exec.get("status");
            json!({
                "buildExecutionId": exec.get::<Uuid, _>("id").to_string(),
                "buildVersionId": build_version_id.map(|v| v.to_string()).unwrap_or_default(),
                "buildKey": exec.get::<String, _>("external_execution_key"),
                "version": exec.get::<String, _>("version_text"),
                "buildNumber": exec.get::<String, _>("execution_number"),
                "commitHash": exec.get::<String, _>("commit_hash"),
                "success": status == "success",
                "resultStatus": legacy_result_status(&status),
                "summaryMessage": exec.get::<String, _>("summary"),
                "stageName": exec.get::<String, _>("stage_name"),
                "jobName": exec.get::<String, _>("job_name"),
                "taskName": exec.get::<String, _>("task_name"),
                "startedAt": exec.get::<Option<chrono::DateTime<chrono::Utc>>, _>("started_at").map(|v| v.to_rfc3339()),
                "finishedAt": exec.get::<Option<chrono::DateTime<chrono::Utc>>, _>("finished_at").map(|v| v.to_rfc3339()),
                "createdAt": exec.get::<chrono::DateTime<chrono::Utc>, _>("created_at").to_rfc3339(),
            })
        })
        .collect())
}

pub async fn get_jenkins_build_details(pool: &PgPool, job_path: &str, build_number: &str) -> Result<Option<Value>, String> {
    let row = fetch_job_row(pool, job_path).await.map_err(|e| e.to_string())?;
    let Some(row) = row else {
        return Ok(None);
    };
    let identity = job_identity(&row);
    let full_name = identity
        .get("jobPath")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let client = build_jenkins_client(pool).await?;
    let build_payload = client
        .get_build(&full_name, build_number)
        .await
        .map_err(|e| e.to_string())?;
    let Some(build_payload) = build_payload else {
        return Ok(None);
    };

    Ok(Some(with_identity(identity, json!({
        "buildNumber": build_number,
        "raw": build_payload.clone(),
        "summary": {
            "result": string_field(&build_payload, "result"),
            "number": build_payload.get("number").cloned().unwrap_or(Value::String(build_number.to_string())),
            "displayName": string_field(&build_payload, "displayName"),
            "building": bool_field(&build_payload, "building"),
            "duration": build_payload.get("duration").cloned().unwrap_or(Value::from(0)),
            "estimatedDuration": build_payload.get("estimatedDuration").cloned().unwrap_or(Value::from(0)),
            "timestamp": build_payload.get("timestamp").cloned().unwrap_or(Value::from(0)),
            "url": build_payload.get("url").cloned().unwrap_or(Value::Null),
        },
        "actions": extract_actions(build_payload.get("actions")),
        "artifacts": build_payload.get("artifacts").cloned().unwrap_or_else(|| Value::Array(Vec::new())),
    }))))
}

pub async fn get_jenkins_system_status(pool: &PgPool) -> Result<Value, String> {
    let settings = settings_repo::get_jenkins_settings(pool).await.map_err(|e| e.to_string())?;
    let client = build_jenkins_client(pool).await?;
    let computers = client.get_computer_list().await.map_err(|e| e.to_string())?;
    let queue = client.get_queue().await.map_err(|e| e.to_string())?;
    Ok(json!({
        "serverUrl": settings.get("serverUrl").cloned().unwrap_or(Value::String(String::new())),
        "connected": true,
        "nodes": computers.iter().map(|node| {
            let executors = node.get("executors").and_then(Value::as_array).cloned().unwrap_or_default();
            let busy = executors.iter().filter(|executor| !executor.get("currentExecutable").unwrap_or(&Value::Null).is_null()).count();
            json!({
                "resourceName": string_field(node, "displayName"),
                "labels": node.get("assignedLabels").and_then(Value::as_array).cloned().unwrap_or_default().into_iter().filter_map(|label| label.get("name").and_then(Value::as_str).map(|v| Value::String(v.to_string()))).collect::<Vec<_>>(),
                "executorCount": executors.len(),
                "busyExecutors": busy,
                "offline": bool_field(node, "offline"),
                "offlineReason": string_field(node, "offlineCauseReason"),
            })
        }).collect::<Vec<_>>(),
        "queue": queue.iter().map(|item| {
            json!({
                "queueItemKey": item.get("id").cloned().unwrap_or(Value::String(String::new())),
                "jobPath": item.get("task").and_then(Value::as_object).and_then(|task| task.get("name")).cloned().unwrap_or(Value::String(String::new())),
                "status": string_field(item, "why"),
                "inQueueSince": item.get("inQueueSince").cloned().unwrap_or(Value::Null),
            })
        }).collect::<Vec<_>>(),
        "nodeCount": computers.len(),
        "queueSize": queue.len(),
    }))
}

pub async fn trigger_jenkins_job(
    pool: &PgPool,
    job_path: &str,
    parameters: &Value,
) -> Result<Option<Value>, String> {
    let row = fetch_job_row(pool, job_path).await.map_err(|e| e.to_string())?;
    let Some(row) = row else {
        return Ok(None);
    };
    let identity = job_identity(&row);
    let client = build_jenkins_client(pool).await?;
    let params = parameters.as_object().cloned().unwrap_or_default();
    let queue_item = client
        .build_job(job_path, &params)
        .await
        .map_err(|e| e.to_string())?;

    Ok(Some(with_identity(
        identity,
        json!({
            "queued": true,
            "message": "Jenkins job 실행을 요청했습니다.",
            "queueId": queue_item.number,
            "parameters": params,
        }),
    )))
}

pub async fn configure_jenkins_job(pool: &PgPool, job_path: &str) -> Result<Option<Value>, String> {
    let row = sqlx::query(
        r#"
        SELECT
            bu.id AS build_unit_id,
            bu.display_name,
            bu.description,
            bu.language,
            bu.compiler,
            bu.runtime_stack,
            project.project_key,
            bu.external_key,
            COALESCE(jenkins.job_path, '') AS job_path,
            COALESCE(repo.clone_url, '') AS clone_url,
            COALESCE(repo.default_branch, '') AS default_branch
        FROM buildmeta_build_unit bu
        JOIN buildmeta_project project ON project.id = bu.project_id
        LEFT JOIN buildmeta_repository repo ON repo.id = bu.repository_id
        LEFT JOIN buildmeta_jenkins_build_unit jenkins ON jenkins.build_unit_id = bu.id
        WHERE bu.ci_provider = 'jenkins'
          AND (jenkins.job_path = $1 OR bu.external_key = $1)
        LIMIT 1
        "#,
    )
    .bind(job_path)
    .fetch_optional(pool)
    .await
    .map_err(|e| e.to_string())?;
    let Some(row) = row else {
        return Ok(None);
    };

    let identity = job_identity(&row);
    let project_key: String = row.get("project_key");
    let full_job_path = identity
        .get("jobPath")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let pipeline_script = build_pipeline_script(
        &row.get::<String, _>("clone_url"),
        &row.get::<String, _>("default_branch"),
        &row.get::<String, _>("language"),
        &row.get::<String, _>("compiler"),
        &row.get::<String, _>("runtime_stack"),
    );
    let description = format!("Auto managed by CI Ops Console ({})", project_key);
    let client = build_jenkins_client(pool).await?;
    let applied = client
        .create_or_update_pipeline_job(&full_job_path, &pipeline_script, &description)
        .await
        .map_err(|e| e.to_string())?;

    Ok(Some(with_identity(
        identity,
        json!({
            "configured": true,
            "created": applied.created,
            "updated": applied.updated,
            "message": "Jenkins job 구성을 반영했습니다.",
            "detail": if applied.created { "created" } else { "updated" },
        }),
    )))
}

async fn fetch_job_row(pool: &PgPool, job_path: &str) -> Result<Option<sqlx::postgres::PgRow>, sqlx::Error> {
    sqlx::query(
        r#"
        SELECT
            bu.id AS build_unit_id,
            bu.external_key,
            bu.display_name,
            bu.description,
            jenkins.job_path,
            COALESCE((
                SELECT exec.execution_number
                FROM buildmeta_build_execution exec
                WHERE exec.build_unit_id = bu.id
                ORDER BY exec.created_at DESC
                LIMIT 1
            ), '') AS latest_execution_number,
            COALESCE((
                SELECT exec.status
                FROM buildmeta_build_execution exec
                WHERE exec.build_unit_id = bu.id
                ORDER BY exec.created_at DESC
                LIMIT 1
            ), '') AS latest_execution_status,
            COALESCE((
                SELECT exec.execution_number
                FROM buildmeta_build_execution exec
                WHERE exec.build_unit_id = bu.id AND exec.finished_at IS NOT NULL
                ORDER BY exec.created_at DESC
                LIMIT 1
            ), '') AS last_completed_build_number,
            COALESCE((
                SELECT exec.status
                FROM buildmeta_build_execution exec
                WHERE exec.build_unit_id = bu.id AND exec.finished_at IS NOT NULL
                ORDER BY exec.created_at DESC
                LIMIT 1
            ), '') AS last_completed_build_status,
            COALESCE((
                SELECT exec.execution_number
                FROM buildmeta_build_execution exec
                WHERE exec.build_unit_id = bu.id AND exec.status = 'failed'
                ORDER BY exec.created_at DESC
                LIMIT 1
            ), '') AS last_failed_build_number,
            COALESCE((
                SELECT exec.execution_number
                FROM buildmeta_build_execution exec
                WHERE exec.build_unit_id = bu.id AND exec.status = 'success'
                ORDER BY exec.created_at DESC
                LIMIT 1
            ), '') AS last_successful_build_number
        FROM buildmeta_build_unit bu
        LEFT JOIN buildmeta_jenkins_build_unit jenkins ON jenkins.build_unit_id = bu.id
        WHERE bu.ci_provider = 'jenkins'
          AND (jenkins.job_path = $1 OR bu.external_key = $1)
        LIMIT 1
        "#,
    )
    .bind(job_path)
    .fetch_optional(pool)
    .await
}

fn effective_job_path(row: &sqlx::postgres::PgRow) -> String {
    let path: String = row.get("job_path");
    if path.is_empty() {
        row.get("external_key")
    } else {
        path
    }
}

fn job_identity(row: &sqlx::postgres::PgRow) -> serde_json::Map<String, Value> {
    let job_path = effective_job_path(row);
    serde_json::Map::from_iter([
        ("jobPath".to_string(), Value::String(job_path.clone())),
        (
            "jobName".to_string(),
            Value::String(job_path.split('/').last().unwrap_or("").to_string()),
        ),
    ])
}

fn legacy_result_status(status: &str) -> String {
    if status.trim().eq_ignore_ascii_case("success") {
        "successful".to_string()
    } else {
        status.trim().to_lowercase()
    }
}

fn build_job_url(server_url: &str, job_path: &str) -> String {
    let segments = job_path
        .split('/')
        .filter(|segment| !segment.trim().is_empty())
        .map(|segment| format!("job/{}", segment))
        .collect::<Vec<_>>();
    if segments.is_empty() {
        server_url.trim_end_matches('/').to_string()
    } else {
        format!("{}/{}", server_url.trim_end_matches('/'), segments.join("/"))
    }
}

async fn build_jenkins_client(pool: &PgPool) -> Result<JenkinsClient, String> {
    let settings = settings_repo::get_jenkins_settings(pool)
        .await
        .map_err(|e| e.to_string())?;
    let server_url = settings
        .get("serverUrl")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string();
    if server_url.is_empty() {
        return Err("Jenkins 서버 URL이 설정되지 않았습니다.".to_string());
    }

    let username = std::env::var("JENKINS_USERNAME").unwrap_or_else(|_| "admin".to_string());
    let token = if let Some(token) = std::env::var("JENKINS_TOKEN")
        .ok()
        .filter(|value| !value.trim().is_empty())
    {
        token
    } else {
        settings_repo::get_jenkins_token_value(pool)
            .await
            .map_err(|e| e.to_string())?
            .trim()
            .to_string()
    };
    let token = if token.is_empty() {
        return Err("Jenkins 토큰이 설정되지 않았습니다.".to_string());
    } else {
        token
    };

    Ok(JenkinsClient::new(server_url, username, token))
}

fn build_pipeline_script(
    clone_url: &str,
    default_branch: &str,
    language: &str,
    compiler: &str,
    runtime_stack: &str,
) -> String {
    let normalized_branch = if default_branch.trim().is_empty() {
        "main"
    } else {
        default_branch.trim()
    }
    .replace('\'', "\\'");
    let normalized_clone_url = clone_url.trim().replace('\'', "\\'");
    let checkout_stage = if normalized_clone_url.is_empty() {
        "        echo 'Repository clone URL not configured'".to_string()
    } else {
        format!(
            "        git branch: '{}', url: '{}'",
            normalized_branch, normalized_clone_url
        )
    };
    let stage_commands = default_pipeline_stage_commands(language, compiler, runtime_stack);
    let mut stages = stage_commands
        .into_iter()
        .map(|(stage_name, commands)| pipeline_stage_shell_block(stage_name, &commands))
        .collect::<Vec<_>>();
    if stages.is_empty() {
        stages.push(pipeline_stage_shell_block(
            "Build",
            &["echo 'No build command configured'".to_string()],
        ));
    }

    format!(
        "pipeline {{\n  agent any\n  options {{ timestamps() }}\n  stages {{\n    stage('Checkout') {{\n      steps {{\n{}\n      }}\n    }}\n{}  }}\n}}\n",
        checkout_stage,
        stages.join("")
    )
}

fn default_pipeline_stage_commands(
    language: &str,
    compiler: &str,
    runtime_stack: &str,
) -> Vec<(&'static str, Vec<String>)> {
    let signal = format!(
        "{} {} {}",
        language.trim().to_lowercase(),
        compiler.trim().to_lowercase(),
        runtime_stack.trim().to_lowercase()
    );

    if signal.contains("maven") || signal.contains("java") {
        return vec![
            ("Install", vec!["echo 'Using Maven wrapper/config from repository'".to_string()]),
            ("Build", vec!["mvn -B -DskipTests package".to_string()]),
            ("Test", vec!["mvn -B test".to_string()]),
            ("Static Analysis", vec!["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'".to_string()]),
        ];
    }
    if signal.contains("gradle") {
        return vec![
            ("Install", vec!["echo 'Using Gradle wrapper from repository'".to_string()]),
            ("Build", vec!["./gradlew build -x test".to_string()]),
            ("Test", vec!["./gradlew test".to_string()]),
            ("Static Analysis", vec!["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'".to_string()]),
        ];
    }
    if signal.contains("node") || signal.contains("npm") {
        return vec![
            ("Install", vec!["npm ci || npm install".to_string()]),
            ("Build", vec!["npm run build --if-present".to_string()]),
            ("Test", vec!["npm test --if-present".to_string()]),
            ("Static Analysis", vec!["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'".to_string()]),
        ];
    }
    if signal.contains("dotnet") || signal.contains(".net") {
        return vec![
            ("Install", vec!["dotnet restore".to_string()]),
            ("Build", vec!["dotnet build -c Release --no-restore".to_string()]),
            ("Test", vec!["dotnet test -c Release --no-build".to_string()]),
            ("Static Analysis", vec!["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'".to_string()]),
        ];
    }

    vec![
        (
            "Install",
            vec![
                "python3 -m pip install -U pip".to_string(),
                "if [ -f requirements.txt ]; then pip3 install -r requirements.txt; fi".to_string(),
            ],
        ),
        ("Build", vec!["python3 -m compileall .".to_string()]),
        (
            "Test",
            vec!["if [ -d tests ]; then python3 -m unittest discover -s tests; else echo 'No tests directory'; fi".to_string()],
        ),
        ("Static Analysis", vec!["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'".to_string()]),
    ]
}

fn pipeline_stage_shell_block(stage_name: &'static str, commands: &[String]) -> String {
    let command_block = if commands.is_empty() {
        "echo 'No command configured'".to_string()
    } else {
        commands.join("\n")
    };
    format!(
        "    stage('{}') {{\n      steps {{\n        sh '''\n{}\n        '''\n      }}\n    }}\n",
        stage_name, command_block
    )
}

fn with_identity(
    mut identity: serde_json::Map<String, Value>,
    extra: Value,
) -> Value {
    if let Value::Object(extra_object) = extra {
        identity.extend(extra_object);
    }
    Value::Object(identity)
}

fn string_field(payload: &Value, key: &str) -> String {
    payload.get(key).and_then(Value::as_str).unwrap_or("").to_string()
}

fn bool_field(payload: &Value, key: &str) -> bool {
    payload.get(key).and_then(Value::as_bool).unwrap_or(false)
}

fn build_number(payload: &Value) -> Option<i64> {
    payload.get("number").and_then(Value::as_i64)
}

fn build_number_text(payload: &Value) -> String {
    build_number(payload).map(|v| v.to_string()).unwrap_or_default()
}

fn build_result(payload: &Value) -> String {
    if let Some(result) = payload.get("result").and_then(Value::as_str) {
        return result.to_string();
    }
    if payload.get("building").and_then(Value::as_bool).unwrap_or(false) {
        return "BUILDING".to_string();
    }
    String::new()
}

fn extract_build_summary(value: Option<&Value>) -> Value {
    let Some(value) = value else {
        return Value::Null;
    };
    if value.is_null() {
        return Value::Null;
    }
    json!({
        "number": value.get("number").cloned().unwrap_or(Value::Null),
        "url": value.get("url").cloned().unwrap_or(Value::String(String::new())),
        "result": value.get("result").cloned().unwrap_or(Value::String(String::new())),
    })
}

fn extract_build_summaries(value: Option<&Value>) -> Vec<Value> {
    value
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .take(10)
        .map(|item| {
            json!({
                "number": item.get("number").cloned().unwrap_or(Value::Null),
                "url": item.get("url").cloned().unwrap_or(Value::String(String::new())),
            })
        })
        .collect()
}

fn extract_actions(value: Option<&Value>) -> Vec<Value> {
    value
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter_map(|item| {
            item.as_object().map(|action| {
                json!({
                    "className": action.get("_class").cloned().unwrap_or(Value::String(String::new())),
                    "cause": action.get("causes")
                        .and_then(Value::as_array)
                        .and_then(|causes| causes.first())
                        .and_then(|cause| cause.get("shortDescription"))
                        .cloned()
                        .unwrap_or(Value::String(String::new())),
                })
            })
        })
        .collect()
}
