use chrono::{DateTime, Utc};
use serde_json::{json, Value};
use sqlx::{PgPool, Row};
use uuid::Uuid;

const BRANCH_KIND_MASTER: &str = "master";
const BRANCH_KIND_RELEASE: &str = "release";
const BRANCH_KIND_DEV: &str = "dev";

pub async fn start_execution(
    pool: &PgPool,
    plan_key: &str,
    branch_kind: &str,
    commit_hash: &str,
    build_number: &str,
    build_key: &str,
    started_at: Option<DateTime<Utc>>,
) -> Result<Value, String> {
    let mut tx = pool.begin().await.map_err(|error| error.to_string())?;

    let bamboo_row = sqlx::query(
        r#"
        SELECT
            bamboo.build_unit_id,
            bamboo.plan_key,
            bu.latest_version_id
        FROM buildmeta_bamboo_build_unit bamboo
        JOIN buildmeta_build_unit bu ON bu.id = bamboo.build_unit_id
        WHERE bamboo.plan_key = $1
        FOR UPDATE
        "#,
    )
    .bind(plan_key)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|error| error.to_string())?;
    let Some(bamboo_row) = bamboo_row else {
        return Err(format!("Build plan '{}' was not found.", plan_key));
    };

    let build_unit_id: Uuid = bamboo_row.get("build_unit_id");
    let normalized_build_key = build_key.trim().to_string();
    if !normalized_build_key.is_empty() {
        let exists = sqlx::query(
            r#"
            SELECT build_key
            FROM buildmeta_bamboo_build_info
            WHERE bamboo_build_unit_id = $1 AND build_key = $2
            "#,
        )
        .bind(build_unit_id)
        .bind(&normalized_build_key)
        .fetch_optional(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;
        if exists.is_none() {
            return Err(format!(
                "Build info '{}' is not registered for plan '{}'.",
                normalized_build_key, plan_key
            ));
        }
    }

    let existing_execution = sqlx::query(
        r#"
        SELECT id, build_version_id, commit_hash
        FROM buildmeta_build_execution
        WHERE build_unit_id = $1
          AND execution_number = $2
          AND external_execution_key = $3
        ORDER BY created_at DESC
        LIMIT 1
        "#,
    )
    .bind(build_unit_id)
    .bind(build_number)
    .bind(&normalized_build_key)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|error| error.to_string())?;

    if let Some(row) = existing_execution {
        let existing_commit_hash: String = row.get("commit_hash");
        if existing_commit_hash != commit_hash {
            return Err(format!(
                "Build number '{}' for plan '{}' is already associated with a different commit.",
                build_number, plan_key
            ));
        }
        let build_version_id: Option<Uuid> = row.get("build_version_id");
        let execution_id: Uuid = row.get("id");
        if let Some(version_id) = build_version_id {
            sqlx::query(
                r#"
                UPDATE buildmeta_build_version
                SET latest_execution_id = $1, updated_at = NOW()
                WHERE id = $2
                "#,
            )
            .bind(execution_id)
            .bind(version_id)
            .execute(&mut *tx)
            .await
            .map_err(|error| error.to_string())?;

            let version_text: String = sqlx::query("SELECT version_text FROM buildmeta_build_version WHERE id = $1")
                .bind(version_id)
                .fetch_one(&mut *tx)
                .await
                .map_err(|error| error.to_string())?
                .get("version_text");

            tx.commit().await.map_err(|error| error.to_string())?;
            return Ok(json!({
                "buildVersionId": version_id.to_string(),
                "buildExecutionId": execution_id.to_string(),
                "version": version_text,
                "buildKey": normalized_build_key,
                "reusedExistingVersion": true,
            }));
        }
        tx.commit().await.map_err(|error| error.to_string())?;
        return Ok(json!({
            "buildVersionId": "",
            "buildExecutionId": execution_id.to_string(),
            "version": "",
            "buildKey": normalized_build_key,
            "reusedExistingVersion": true,
        }));
    }

    let version_row = sqlx::query(
        r#"
        SELECT id, version_text
        FROM buildmeta_build_version
        WHERE build_unit_id = $1 AND commit_hash = $2
        ORDER BY version_major DESC, version_minor DESC, version_patch DESC, created_at DESC
        LIMIT 1
        "#,
    )
    .bind(build_unit_id)
    .bind(commit_hash)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|error| error.to_string())?;

    let reused_existing_version = version_row.is_some();
    let (version_id, version_text) = if let Some(row) = version_row {
        (row.get("id"), row.get("version_text"))
    } else {
        let latest_version_row = if let Some(latest_version_id) = bamboo_row.get::<Option<Uuid>, _>("latest_version_id") {
            sqlx::query(
                r#"
                SELECT version_major, version_minor, version_patch
                FROM buildmeta_build_version
                WHERE id = $1
                "#,
            )
            .bind(latest_version_id)
            .fetch_optional(&mut *tx)
            .await
            .map_err(|error| error.to_string())?
        } else {
            None
        };

        let (major, minor, patch) = next_version_numbers(latest_version_row, branch_kind);
        sqlx::query(
            r#"
            UPDATE buildmeta_build_version
            SET is_latest = false
            WHERE build_unit_id = $1 AND is_latest = true
            "#,
        )
        .bind(build_unit_id)
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;

        let version_text = format!("v{}.{}.{}", major, minor, patch);
        let version_id: Uuid = sqlx::query_scalar(
            r#"
            INSERT INTO buildmeta_build_version (
                id, created_at, updated_at, build_unit_id,
                version_text, version_major, version_minor, version_patch,
                commit_hash, branch_name, branch_kind, is_latest
            )
            VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, $6, $7, $8, $9, true)
            RETURNING id
            "#,
        )
        .bind(Uuid::new_v4())
        .bind(build_unit_id)
        .bind(&version_text)
        .bind(major)
        .bind(minor)
        .bind(patch)
        .bind(commit_hash)
        .bind(branch_kind.trim())
        .bind(normalize_branch_kind(branch_kind))
        .fetch_one(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;

        sqlx::query(
            r#"
            UPDATE buildmeta_build_unit
            SET latest_version_id = $1, updated_at = NOW()
            WHERE id = $2
            "#,
        )
        .bind(version_id)
        .bind(build_unit_id)
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;

        (version_id, version_text)
    };

    let execution_id = Uuid::new_v4();
    sqlx::query(
        r#"
        INSERT INTO buildmeta_build_execution (
            id, build_unit_id, build_version_id, execution_number, external_execution_key,
            trigger_type, trigger_actor, branch_name, commit_hash, status, summary,
            stage_name, job_name, task_name, queued_at, started_at, finished_at, created_at
        )
        VALUES ($1, $2, $3, $4, $5, 'build', '', $6, $7, 'running', '', '', '', '', NULL, $8, NULL, NOW())
        "#,
    )
    .bind(execution_id)
    .bind(build_unit_id)
    .bind(version_id)
    .bind(build_number)
    .bind(&normalized_build_key)
    .bind(branch_kind.trim())
    .bind(commit_hash)
    .bind(started_at)
    .execute(&mut *tx)
    .await
    .map_err(|error| error.to_string())?;

    sqlx::query(
        r#"
        UPDATE buildmeta_build_version
        SET latest_execution_id = $1, updated_at = NOW()
        WHERE id = $2
        "#,
    )
    .bind(execution_id)
    .bind(version_id)
    .execute(&mut *tx)
    .await
    .map_err(|error| error.to_string())?;

    tx.commit().await.map_err(|error| error.to_string())?;

    Ok(json!({
        "buildVersionId": version_id.to_string(),
        "buildExecutionId": execution_id.to_string(),
        "version": version_text,
        "buildKey": normalized_build_key,
        "reusedExistingVersion": reused_existing_version,
    }))
}

pub async fn record_static_analysis_results(
    pool: &PgPool,
    execution_id: Uuid,
    static_analysis_results: &[Value],
) -> Result<Value, String> {
    let mut tx = pool.begin().await.map_err(|error| error.to_string())?;
    let exists = sqlx::query("SELECT id FROM buildmeta_build_execution WHERE id = $1")
        .bind(execution_id)
        .fetch_optional(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;
    if exists.is_none() {
        return Err(format!("Build execution '{}' was not found.", execution_id));
    }
    let updated_count = upsert_static_analysis_results(&mut tx, execution_id, static_analysis_results).await?;
    tx.commit().await.map_err(|error| error.to_string())?;
    Ok(json!({
        "buildExecutionId": execution_id.to_string(),
        "updatedCount": updated_count,
    }))
}

pub async fn finish_execution(
    pool: &PgPool,
    execution_id: Uuid,
    success: bool,
    result_status: &str,
    summary_message: &str,
    stage_name: &str,
    job_name: &str,
    task_name: &str,
    finished_at: Option<DateTime<Utc>>,
    static_analysis_results: &[Value],
) -> Result<Value, String> {
    let mut tx = pool.begin().await.map_err(|error| error.to_string())?;
    let row = sqlx::query(
        r#"
        SELECT id, build_unit_id, build_version_id, status, finished_at
        FROM buildmeta_build_execution
        WHERE id = $1
        "#,
    )
    .bind(execution_id)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|error| error.to_string())?;
    let Some(row) = row else {
        return Err(format!("Build execution '{}' was not found.", execution_id));
    };

    let build_unit_id: Uuid = row.get("build_unit_id");
    let build_version_id: Option<Uuid> = row.get("build_version_id");
    let current_status: String = row.get("status");
    let current_finished_at: Option<DateTime<Utc>> = row.get("finished_at");

    upsert_static_analysis_results(&mut tx, execution_id, static_analysis_results).await?;

    let normalized_status = normalize_execution_status(result_status, success);
    if should_apply_execution_finish(&current_status, current_finished_at, success) {
        sqlx::query(
            r#"
            UPDATE buildmeta_build_execution
            SET status = $1, summary = $2, stage_name = $3, job_name = $4, task_name = $5, finished_at = $6
            WHERE id = $7
            "#,
        )
        .bind(&normalized_status)
        .bind(summary_message)
        .bind(stage_name)
        .bind(job_name)
        .bind(task_name)
        .bind(finished_at)
        .bind(execution_id)
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;
    }

    if let Some(version_id) = build_version_id {
        sqlx::query(
            r#"
            UPDATE buildmeta_build_version
            SET latest_execution_id = $1, latest_success = $2, updated_at = NOW()
            WHERE id = $3
            "#,
        )
        .bind(execution_id)
        .bind(success)
        .bind(version_id)
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;

        let is_latest: bool = sqlx::query("SELECT is_latest FROM buildmeta_build_version WHERE id = $1")
            .bind(version_id)
            .fetch_one(&mut *tx)
            .await
            .map_err(|error| error.to_string())?
            .get("is_latest");

        if is_latest {
            sqlx::query(
                r#"
                UPDATE buildmeta_build_unit
                SET latest_version_id = $1, updated_at = NOW()
                WHERE id = $2
                "#,
            )
            .bind(version_id)
            .bind(build_unit_id)
            .execute(&mut *tx)
            .await
            .map_err(|error| error.to_string())?;
        }
    }

    tx.commit().await.map_err(|error| error.to_string())?;
    Ok(json!({
        "buildExecutionId": execution_id.to_string(),
        "buildVersionId": build_version_id.map(|value| value.to_string()).unwrap_or_default(),
        "resultStatus": result_status,
        "success": normalized_status == "success",
    }))
}

async fn upsert_static_analysis_results(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    execution_id: Uuid,
    static_analysis_results: &[Value],
) -> Result<usize, String> {
    let mut updated_count = 0usize;
    for result in static_analysis_results {
        let tool_name = result.get("toolName").and_then(Value::as_str).unwrap_or_default();
        let status = result.get("status").and_then(Value::as_str).unwrap_or_default();
        let summary = result.get("summary").and_then(Value::as_str).unwrap_or_default();
        let metrics_json = result.get("metricsJson").cloned().unwrap_or(Value::Null);

        sqlx::query(
            r#"
            INSERT INTO buildmeta_static_analysis_result (
                id, created_at, updated_at, build_execution_id, tool_name, status, summary, metrics_json
            )
            VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, $6)
            ON CONFLICT (build_execution_id, tool_name)
            DO UPDATE SET status = EXCLUDED.status, summary = EXCLUDED.summary, metrics_json = EXCLUDED.metrics_json, updated_at = NOW()
            "#,
        )
        .bind(Uuid::new_v4())
        .bind(execution_id)
        .bind(tool_name)
        .bind(status)
        .bind(summary)
        .bind(metrics_json)
        .execute(&mut **tx)
        .await
        .map_err(|error| error.to_string())?;
        updated_count += 1;
    }
    Ok(updated_count)
}

fn normalize_branch_kind(branch_kind: &str) -> &'static str {
    match branch_kind.trim().to_lowercase().as_str() {
        BRANCH_KIND_MASTER => BRANCH_KIND_MASTER,
        BRANCH_KIND_RELEASE => BRANCH_KIND_RELEASE,
        _ => BRANCH_KIND_DEV,
    }
}

fn next_version_numbers(
    latest_version_row: Option<sqlx::postgres::PgRow>,
    branch_kind: &str,
) -> (i32, i32, i32) {
    let normalized = normalize_branch_kind(branch_kind);
    if let Some(row) = latest_version_row {
        let major: i32 = row.get("version_major");
        let minor: i32 = row.get("version_minor");
        let patch: i32 = row.get("version_patch");
        match normalized {
            BRANCH_KIND_MASTER => (major + 1, 0, 0),
            BRANCH_KIND_RELEASE => (major, minor + 1, 0),
            _ => (major, minor, patch + 1),
        }
    } else {
        match normalized {
            BRANCH_KIND_MASTER => (1, 0, 0),
            BRANCH_KIND_RELEASE => (0, 1, 0),
            _ => (0, 0, 1),
        }
    }
}

fn normalize_execution_status(result_status: &str, success: bool) -> String {
    let normalized = result_status.trim().to_lowercase();
    match normalized.as_str() {
        "queued" | "running" | "success" | "failed" | "canceled" => normalized,
        _ if success => "success".to_string(),
        _ => "failed".to_string(),
    }
}

fn should_apply_execution_finish(current_status: &str, current_finished_at: Option<DateTime<Utc>>, success: bool) -> bool {
    let is_terminal = current_finished_at.is_some() || current_status != "running";
    if !is_terminal {
        return true;
    }
    !(current_status == "failed" && success)
}
