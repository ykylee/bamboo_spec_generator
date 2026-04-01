use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Row};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use uuid::Uuid;

pub struct ModuleUploadInput {
    pub asset_kind: String,
    pub provider_scope: String,
    pub module_id: String,
    pub filename: String,
    pub content: Vec<u8>,
    pub activate_after_upload: bool,
}

pub async fn list_modules(
    pool: &PgPool,
    asset_kind: &str,
    provider_scope: &str,
    status: &str,
) -> Result<Vec<Value>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            asset.id,
            asset.asset_kind,
            asset.provider_scope,
            asset.module_id,
            asset.display_name,
            asset.status,
            asset.active_version_id,
            asset.latest_version_id
        FROM buildmeta_module_asset asset
        WHERE ($1 = '' OR asset.asset_kind = $1)
          AND ($2 = '' OR asset.provider_scope = $2)
          AND ($3 = '' OR asset.status = $3)
        ORDER BY asset.asset_kind, asset.provider_scope, asset.module_id
        "#,
    )
    .bind(asset_kind)
    .bind(provider_scope)
    .bind(status)
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|row| {
            let asset_id: Uuid = row.get("id");
            let active_version_id: Option<Uuid> = row.get("active_version_id");
            let latest_version_id: Option<Uuid> = row.get("latest_version_id");
            json!({
                "assetId": asset_id.to_string(),
                "assetKind": row.get::<String, _>("asset_kind"),
                "providerScope": row.get::<String, _>("provider_scope"),
                "moduleId": row.get::<String, _>("module_id"),
                "displayName": row.get::<String, _>("display_name"),
                "status": row.get::<String, _>("status"),
                "activeVersionId": active_version_id.map(|value| value.to_string()).unwrap_or_default(),
                "latestVersionId": latest_version_id.map(|value| value.to_string()).unwrap_or_default(),
                "detailPath": format!("/settings/modules/{}/", asset_id),
            })
        })
        .collect())
}

pub async fn upload_module_asset(pool: &PgPool, input: ModuleUploadInput) -> Result<Value, String> {
    validate_upload_input(&input)?;
    validate_asset_scope(&input.asset_kind, &input.provider_scope)?;

    let mut tx = pool.begin().await.map_err(|e| e.to_string())?;
    let asset_row = sqlx::query(
        r#"
        SELECT id, display_name
        FROM buildmeta_module_asset
        WHERE asset_kind = $1 AND provider_scope = $2 AND module_id = $3
        "#,
    )
    .bind(&input.asset_kind)
    .bind(&input.provider_scope)
    .bind(input.module_id.trim())
    .fetch_optional(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;

    let asset_id = asset_row
        .as_ref()
        .map(|row| row.get::<Uuid, _>("id"))
        .unwrap_or_else(Uuid::new_v4);
    let version_number: i32 = sqlx::query_scalar(
        r#"
        SELECT COALESCE(MAX(version_number), 0) + 1
        FROM buildmeta_module_asset_version
        WHERE asset_id = $1
        "#,
    )
    .bind(asset_id)
    .fetch_one(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;

    let suffix = Path::new(&input.filename)
        .extension()
        .map(|ext| format!(".{}", ext.to_string_lossy().to_lowercase()))
        .unwrap_or_default();
    let validation = validate_asset_content(
        &input.asset_kind,
        &input.provider_scope,
        &suffix,
        &input.content,
    )?;
    let content_hash = format!("{:x}", Sha256::digest(&input.content));
    let storage_dir = module_storage_dir(
        &input.asset_kind,
        &input.provider_scope,
        input.module_id.trim(),
        version_number,
    );
    fs::create_dir_all(&storage_dir).map_err(|e| e.to_string())?;
    let storage_path = storage_dir.join(&input.filename);
    fs::write(&storage_path, &input.content).map_err(|e| e.to_string())?;

    if asset_row.is_none() {
        sqlx::query(
            r#"
            INSERT INTO buildmeta_module_asset (
                id, created_at, updated_at, asset_kind, provider_scope, module_id, display_name, status
            )
            VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, 'draft')
            "#,
        )
        .bind(asset_id)
        .bind(&input.asset_kind)
        .bind(&input.provider_scope)
        .bind(input.module_id.trim())
        .bind(input.module_id.trim())
        .execute(&mut *tx)
        .await
        .map_err(|e| e.to_string())?;
    }

    let version_id = Uuid::new_v4();
    sqlx::query(
        r#"
        INSERT INTO buildmeta_module_asset_version (
            id, created_at, updated_at, asset_id, version_number, source_filename, storage_path,
            content_hash, schema_version, validation_status, validation_message, parsed_metadata_json
        )
        VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, $6, $7, $8, $9, $10)
        "#,
    )
    .bind(version_id)
    .bind(asset_id)
    .bind(version_number)
    .bind(&input.filename)
    .bind(storage_path.to_string_lossy().to_string())
    .bind(&content_hash)
    .bind(validation.schema_version)
    .bind(&validation.status)
    .bind(&validation.message)
    .bind(validation.parsed_metadata.clone())
    .execute(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;

    let display_name = validation
        .parsed_metadata
        .get("metadata")
        .and_then(Value::as_object)
        .and_then(|metadata| metadata.get("name"))
        .and_then(Value::as_str)
        .unwrap_or(input.module_id.trim())
        .trim()
        .to_string();
    let asset_status = if validation.status == "invalid" {
        "invalid"
    } else {
        asset_row
            .as_ref()
            .map(|_| "draft")
            .unwrap_or("draft")
    };
    sqlx::query(
        r#"
        UPDATE buildmeta_module_asset
        SET latest_version_id = $1, display_name = $2, status = $3, updated_at = NOW()
        WHERE id = $4
        "#,
    )
    .bind(version_id)
    .bind(display_name)
    .bind(asset_status)
    .bind(asset_id)
    .execute(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;

    if input.activate_after_upload && validation.status == "valid" {
        activate_module_version_with_tx(
            &mut tx,
            asset_id,
            version_id,
            &input.asset_kind,
            &input.provider_scope,
            input.module_id.trim(),
            &storage_path,
        )
        .await?;
    }

    tx.commit().await.map_err(|e| e.to_string())?;

    Ok(json!({
        "assetId": asset_id.to_string(),
        "versionId": version_id.to_string(),
        "validationStatus": validation.status,
        "message": validation.message,
        "activated": input.activate_after_upload && validation.status == "valid",
    }))
}

pub async fn get_load_status(pool: &PgPool) -> Result<Value, sqlx::Error> {
    let active_asset_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM buildmeta_module_asset WHERE status = 'active'"
    )
    .fetch_one(pool)
    .await?;

    let snapshot = sqlx::query(
        r#"
        SELECT id, status, loaded_count, invalid_count, skipped_count, started_at, finished_at, summary_message
        FROM buildmeta_module_load_snapshot
        ORDER BY started_at DESC
        LIMIT 1
        "#,
    )
    .fetch_optional(pool)
    .await?;

    if let Some(snapshot) = snapshot {
        let snapshot_id: Uuid = snapshot.get("id");
        let recent_failures_rows = sqlx::query(
            r#"
            SELECT module_id, status, error_code, error_message
            FROM buildmeta_module_load_entry
            WHERE snapshot_id = $1 AND status = 'invalid'
            ORDER BY module_id
            LIMIT 20
            "#,
        )
        .bind(snapshot_id)
        .fetch_all(pool)
        .await?;
        Ok(json!({
            "lastSnapshot": {
                "snapshotId": snapshot_id.to_string(),
                "status": snapshot.get::<String, _>("status"),
                "loadedCount": snapshot.get::<i32, _>("loaded_count"),
                "invalidCount": snapshot.get::<i32, _>("invalid_count"),
                "skippedCount": snapshot.get::<i32, _>("skipped_count"),
                "startedAt": snapshot.get::<chrono::DateTime<chrono::Utc>, _>("started_at").to_rfc3339(),
                "finishedAt": snapshot.get::<Option<chrono::DateTime<chrono::Utc>>, _>("finished_at").map(|v| v.to_rfc3339()).unwrap_or_default(),
                "summaryMessage": snapshot.get::<String, _>("summary_message"),
            },
            "activeAssetCount": active_asset_count,
            "recentFailures": recent_failures_rows.into_iter().map(|row| {
                json!({
                    "moduleId": row.get::<String, _>("module_id"),
                    "status": row.get::<String, _>("status"),
                    "errorCode": row.get::<String, _>("error_code"),
                    "errorMessage": row.get::<String, _>("error_message"),
                })
            }).collect::<Vec<_>>(),
        }))
    } else {
        Ok(json!({
            "lastSnapshot": Value::Null,
            "activeAssetCount": active_asset_count,
            "recentFailures": Vec::<Value>::new(),
        }))
    }
}

pub async fn get_module_detail(
    pool: &PgPool,
    asset_id: Uuid,
    version_id: &str,
    compare_version_id: &str,
) -> Result<Option<Value>, sqlx::Error> {
    let asset = sqlx::query(
        r#"
        SELECT id, asset_kind, provider_scope, module_id, display_name, status, active_version_id, latest_version_id
        FROM buildmeta_module_asset
        WHERE id = $1
        "#,
    )
    .bind(asset_id)
    .fetch_optional(pool)
    .await?;
    let Some(asset) = asset else {
        return Ok(None);
    };

    let versions = sqlx::query(
        r#"
        SELECT id, version_number, source_filename, storage_path, validation_status, validation_message, created_at
        FROM buildmeta_module_asset_version
        WHERE asset_id = $1
        ORDER BY version_number DESC
        "#,
    )
    .bind(asset_id)
    .fetch_all(pool)
    .await?;

    let active_version_id: Option<Uuid> = asset.get("active_version_id");
    let latest_version_id: Option<Uuid> = asset.get("latest_version_id");
    let selected_version_row = if !version_id.trim().is_empty() {
        versions
            .iter()
            .find(|row| row.get::<Uuid, _>("id").to_string() == version_id)
    } else if let Some(active) = active_version_id {
        versions.iter().find(|row| row.get::<Uuid, _>("id") == active)
    } else if let Some(latest) = latest_version_id {
        versions.iter().find(|row| row.get::<Uuid, _>("id") == latest)
    } else {
        versions.first()
    };

    let compare_version_row = if !compare_version_id.trim().is_empty() {
        versions
            .iter()
            .find(|row| row.get::<Uuid, _>("id").to_string() == compare_version_id)
    } else {
        None
    };

    let preview_content = selected_version_row
        .map(read_version_content)
        .unwrap_or_default();
    let preview_language = selected_version_row
        .map(|row| infer_preview_language(&row.get::<String, _>("source_filename")))
        .unwrap_or_else(|| "text".to_string());
    let diff_content = match (compare_version_row, selected_version_row) {
        (Some(older), Some(newer)) => build_version_diff(older, newer),
        _ => String::new(),
    };

    let recent_issues = sqlx::query(
        r#"
        SELECT status, error_code, error_message, source_path, created_at
        FROM buildmeta_module_load_entry
        WHERE asset_id = $1 AND error_code <> ''
        ORDER BY created_at DESC
        LIMIT 10
        "#,
    )
    .bind(asset_id)
    .fetch_all(pool)
    .await?;

    Ok(Some(json!({
        "assetId": asset.get::<Uuid, _>("id").to_string(),
        "assetKind": asset.get::<String, _>("asset_kind"),
        "providerScope": asset.get::<String, _>("provider_scope"),
        "moduleId": asset.get::<String, _>("module_id"),
        "displayName": asset.get::<String, _>("display_name"),
        "status": asset.get::<String, _>("status"),
        "selectedVersionId": selected_version_row.map(|row| row.get::<Uuid, _>("id").to_string()).unwrap_or_default(),
        "compareVersionId": compare_version_row.map(|row| row.get::<Uuid, _>("id").to_string()).unwrap_or_default(),
        "previewContent": preview_content,
        "previewLanguage": preview_language,
        "diffContent": diff_content,
        "diffLanguage": "diff",
        "recentIssues": recent_issues.into_iter().map(|row| {
            json!({
                "status": row.get::<String, _>("status"),
                "errorCode": row.get::<String, _>("error_code"),
                "errorMessage": row.get::<String, _>("error_message"),
                "sourcePath": row.get::<String, _>("source_path"),
                "recordedAt": row.get::<chrono::DateTime<chrono::Utc>, _>("created_at").to_rfc3339(),
            })
        }).collect::<Vec<_>>(),
        "versions": versions.iter().map(|row| {
            let version_uuid: Uuid = row.get("id");
            json!({
                "versionId": version_uuid.to_string(),
                "versionNumber": row.get::<i32, _>("version_number"),
                "sourceFilename": row.get::<String, _>("source_filename"),
                "validationStatus": row.get::<String, _>("validation_status"),
                "validationMessage": row.get::<String, _>("validation_message"),
                "uploadedAt": row.get::<chrono::DateTime<chrono::Utc>, _>("created_at").to_rfc3339(),
                "isActive": active_version_id == Some(version_uuid),
                "isLatest": latest_version_id == Some(version_uuid),
            })
        }).collect::<Vec<_>>(),
    })))
}

pub async fn activate_module_version(pool: &PgPool, asset_id: Uuid, version_id: Uuid) -> Result<Value, String> {
    let mut tx = pool.begin().await.map_err(|e| e.to_string())?;
    let row = sqlx::query(
        r#"
        SELECT asset.id, asset.asset_kind, asset.provider_scope, asset.module_id, version.storage_path
        FROM buildmeta_module_asset asset
        JOIN buildmeta_module_asset_version version ON version.asset_id = asset.id
        WHERE asset.id = $1 AND version.id = $2
        "#,
    )
    .bind(asset_id)
    .bind(version_id)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;
    let Some(row) = row else {
        return Err("Module asset or version was not found.".to_string());
    };

    let asset_kind: String = row.get("asset_kind");
    let provider_scope: String = row.get("provider_scope");
    let module_id: String = row.get("module_id");
    let source_path = PathBuf::from(row.get::<String, _>("storage_path"));
    let target_path = activate_module_version_with_tx(
        &mut tx,
        asset_id,
        version_id,
        &asset_kind,
        &provider_scope,
        &module_id,
        &source_path,
    )
    .await?;

    tx.commit().await.map_err(|e| e.to_string())?;
    Ok(json!({
        "assetId": asset_id.to_string(),
        "versionId": version_id.to_string(),
        "activePath": target_path.to_string_lossy().to_string(),
    }))
}

pub async fn deactivate_module(pool: &PgPool, asset_id: Uuid) -> Result<Value, String> {
    let mut tx = pool.begin().await.map_err(|e| e.to_string())?;
    let activation = sqlx::query(
        "SELECT active_path FROM buildmeta_module_activation WHERE asset_id = $1"
    )
    .bind(asset_id)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;
    if let Some(row) = activation {
        let active_path: String = row.get("active_path");
        if !active_path.is_empty() {
            let path = PathBuf::from(&active_path);
            if path.exists() {
                let _ = fs::remove_file(path);
            }
        }
        sqlx::query(
            r#"
            UPDATE buildmeta_module_activation
            SET activation_status = 'inactive', active_path = '', updated_at = NOW()
            WHERE asset_id = $1
            "#,
        )
        .bind(asset_id)
        .execute(&mut *tx)
        .await
        .map_err(|e| e.to_string())?;
    }
    sqlx::query(
        r#"
        UPDATE buildmeta_module_asset
        SET active_version_id = NULL, status = 'inactive', updated_at = NOW()
        WHERE id = $1
        "#,
    )
    .bind(asset_id)
    .execute(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;
    tx.commit().await.map_err(|e| e.to_string())?;
    Ok(json!({
        "assetId": asset_id.to_string(),
        "status": "inactive",
    }))
}

pub async fn reload_modules(pool: &PgPool) -> Result<Value, String> {
    let mut tx = pool.begin().await.map_err(|e| e.to_string())?;
    let snapshot_id = Uuid::new_v4();
    sqlx::query(
        r#"
        INSERT INTO buildmeta_module_load_snapshot (
            id, created_at, updated_at, trigger_source, started_at, status, loaded_count, invalid_count, skipped_count, summary_message
        )
        VALUES ($1, NOW(), NOW(), 'api', NOW(), 'success', 0, 0, 0, '')
        "#,
    )
    .bind(snapshot_id)
    .execute(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;

    let assets = sqlx::query(
        r#"
        SELECT asset.id, asset.asset_kind, asset.provider_scope, asset.module_id, asset.active_version_id, activation.active_path
        FROM buildmeta_module_asset asset
        LEFT JOIN buildmeta_module_activation activation ON activation.asset_id = asset.id
        ORDER BY asset.asset_kind, asset.provider_scope, asset.module_id
        "#,
    )
    .fetch_all(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;

    let mut active_paths: HashMap<String, (Uuid, String, String, Option<Uuid>)> = HashMap::new();
    let mut skipped_count = 0;
    for row in &assets {
        let asset_id: Uuid = row.get("id");
        let active_version_id: Option<Uuid> = row.get("active_version_id");
        if active_version_id.is_none() {
            skipped_count += 1;
            insert_load_entry(&mut tx, snapshot_id, Some(asset_id), None, row.get("asset_kind"), row.get("module_id"), "", "skipped", "inactive", "No active version").await?;
            continue;
        }
        let active_path: String = row.get("active_path");
        if !active_path.is_empty() {
            let normalized_active_path = normalize_existing_path_text(&active_path);
            active_paths.insert(
                normalized_active_path,
                (asset_id, row.get("asset_kind"), row.get("module_id"), active_version_id),
            );
        }
    }

    let active_root = module_registry_root().join("active");
    let (loaded_paths, loaded_count, invalid_count_from_scan) = scan_active_registry(&mut tx, snapshot_id, &active_root, &active_paths).await?;
    let mut invalid_count = invalid_count_from_scan;

    for (active_path, (asset_id, asset_kind, module_id, active_version_id)) in &active_paths {
        if loaded_paths.contains(active_path) {
            continue;
        }
        invalid_count += 1;
        insert_load_entry(
            &mut tx,
            snapshot_id,
            Some(*asset_id),
            *active_version_id,
            asset_kind,
            module_id,
            active_path,
            "invalid",
            "unscanned_active_path",
            "Active path was not scanned by the module loader",
        )
        .await?;
    }

    let status = if invalid_count > 0 && loaded_count > 0 {
        "partial_success"
    } else if invalid_count > 0 {
        "failed"
    } else {
        "success"
    };

    sqlx::query(
        r#"
        UPDATE buildmeta_module_load_snapshot
        SET finished_at = NOW(),
            status = $1,
            loaded_count = $2,
            invalid_count = $3,
            skipped_count = $4,
            summary_message = $5,
            updated_at = NOW()
        WHERE id = $6
        "#,
    )
    .bind(status)
    .bind(loaded_count as i32)
    .bind(invalid_count as i32)
    .bind(skipped_count as i32)
    .bind(format!("loaded={} invalid={} skipped={}", loaded_count, invalid_count, skipped_count))
    .bind(snapshot_id)
    .execute(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;

    tx.commit().await.map_err(|e| e.to_string())?;
    Ok(json!({
        "snapshotId": snapshot_id.to_string(),
        "status": status,
        "loadedCount": loaded_count,
        "invalidCount": invalid_count,
        "skippedCount": skipped_count,
    }))
}

async fn scan_active_registry(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    snapshot_id: Uuid,
    active_root: &Path,
    active_paths: &HashMap<String, (Uuid, String, String, Option<Uuid>)>,
) -> Result<(HashSet<String>, usize, usize), String> {
    let mut loaded_paths = HashSet::new();
    let mut loaded_count = 0usize;
    let mut invalid_count = 0usize;

    let stage_dir = active_root.join("stages").join("common");
    scan_files(tx, snapshot_id, &stage_dir, "stage_module", active_paths, &mut loaded_paths, &mut loaded_count, &mut invalid_count).await?;
    let job_dir = active_root.join("jobs").join("common");
    scan_files(tx, snapshot_id, &job_dir, "job_module", active_paths, &mut loaded_paths, &mut loaded_count, &mut invalid_count).await?;
    for provider in ["bamboo", "jenkins"] {
        let task_dir = active_root.join("tasks").join(provider);
        scan_files(tx, snapshot_id, &task_dir, "task_module", active_paths, &mut loaded_paths, &mut loaded_count, &mut invalid_count).await?;
    }

    Ok((loaded_paths, loaded_count, invalid_count))
}

async fn scan_files(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    snapshot_id: Uuid,
    directory: &Path,
    module_kind: &str,
    active_paths: &HashMap<String, (Uuid, String, String, Option<Uuid>)>,
    loaded_paths: &mut HashSet<String>,
    loaded_count: &mut usize,
    invalid_count: &mut usize,
) -> Result<(), String> {
    if !directory.exists() {
        return Ok(());
    }
    let entries = fs::read_dir(directory).map_err(|e| e.to_string())?;
    let mut seen_module_ids = HashSet::new();
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let path_text = normalize_path_text(&path);
        let parsed = parse_module_file(&path, module_kind);
        match parsed {
            Ok(module_id) => {
                loaded_paths.insert(path_text.clone());
                if !seen_module_ids.insert(module_id.clone()) {
                    *invalid_count += 1;
                    let (asset_id, _, _, version_id) = active_paths.get(&path_text).cloned().unwrap_or((Uuid::nil(), "".to_string(), "".to_string(), None));
                    insert_load_entry(tx, snapshot_id, non_nil(asset_id), version_id, module_kind, &module_id, &path_text, "invalid", "duplicate_module_id", &format!("Duplicate {} id", module_kind)).await?;
                } else {
                    *loaded_count += 1;
                    let (asset_id, _, _, version_id) = active_paths.get(&path_text).cloned().unwrap_or((Uuid::nil(), "".to_string(), "".to_string(), None));
                    insert_load_entry(tx, snapshot_id, non_nil(asset_id), version_id, module_kind, &module_id, &path_text, "loaded", "", "").await?;
                }
            }
            Err((module_id, code, message)) => {
                loaded_paths.insert(path_text.clone());
                *invalid_count += 1;
                let (asset_id, _, _, version_id) = active_paths.get(&path_text).cloned().unwrap_or((Uuid::nil(), "".to_string(), "".to_string(), None));
                insert_load_entry(tx, snapshot_id, non_nil(asset_id), version_id, module_kind, &module_id, &path_text, "invalid", &code, &message).await?;
            }
        }
    }
    Ok(())
}

fn normalize_existing_path_text(path_text: &str) -> String {
    let path = Path::new(path_text);
    if path.is_absolute() {
        normalize_path_text(path)
    } else {
        normalize_path_text(&repo_root().join(path))
    }
}

fn normalize_path_text(path: &Path) -> String {
    fs::canonicalize(path)
        .unwrap_or_else(|_| path.to_path_buf())
        .to_string_lossy()
        .to_string()
}

async fn insert_load_entry(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    snapshot_id: Uuid,
    asset_id: Option<Uuid>,
    asset_version_id: Option<Uuid>,
    module_kind: &str,
    module_id: &str,
    source_path: &str,
    status: &str,
    error_code: &str,
    error_message: &str,
) -> Result<(), String> {
    sqlx::query(
        r#"
        INSERT INTO buildmeta_module_load_entry (
            id, created_at, updated_at, snapshot_id, asset_id, asset_version_id,
            module_kind, module_id, source_path, status, error_code, error_message
        )
        VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, $6, $7, $8, $9, $10)
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(snapshot_id)
    .bind(asset_id)
    .bind(asset_version_id)
    .bind(module_kind)
    .bind(module_id)
    .bind(source_path)
    .bind(status)
    .bind(error_code)
    .bind(error_message)
    .execute(&mut **tx)
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

fn parse_module_file(path: &Path, module_kind: &str) -> Result<String, (String, String, String)> {
    let suffix = path.extension().map(|ext| ext.to_string_lossy().to_lowercase()).unwrap_or_default();
    let text = fs::read_to_string(path).map_err(|e| ("".to_string(), "parse_failed".to_string(), format!("Failed to parse module file: {}", e)))?;
    if suffix == "json" {
        let payload: Value = serde_json::from_str(&text)
            .map_err(|e| ("".to_string(), "parse_failed".to_string(), format!("Failed to parse module file: {}", e)))?;
        let metadata = payload.get("metadata").and_then(Value::as_object).ok_or_else(|| ("".to_string(), "invalid_payload".to_string(), "Module payload must include metadata and spec".to_string()))?;
        let module_id = metadata.get("id").and_then(Value::as_str).unwrap_or("").trim().to_string();
        if module_id.is_empty() {
            return Err(("".to_string(), "invalid_schema".to_string(), format!("Invalid {}: metadata.id is required", module_kind)));
        }
        Ok(module_id)
    } else if suffix == "yaml" || suffix == "yml" {
        if text.contains("metadata:") && text.contains("spec:") {
            let module_id = extract_yaml_module_id(&text);
            if module_id.is_empty() {
                Err(("".to_string(), "invalid_schema".to_string(), format!("Invalid {}: metadata.id is required", module_kind)))
            } else {
                Ok(module_id)
            }
        } else {
            Err(("".to_string(), "invalid_payload".to_string(), "Module payload must include metadata and spec".to_string()))
        }
    } else {
        Err(("".to_string(), "unsupported_extension".to_string(), format!("Unsupported extension: .{}", suffix)))
    }
}

struct ValidationResult {
    status: String,
    message: String,
    parsed_metadata: Value,
    schema_version: String,
}

fn validate_upload_input(input: &ModuleUploadInput) -> Result<(), String> {
    if input.asset_kind.trim().is_empty() {
        return Err("assetKind is required".to_string());
    }
    if input.module_id.trim().is_empty() {
        return Err("moduleId is required".to_string());
    }
    if input.filename.trim().is_empty() {
        return Err("Uploaded filename is required".to_string());
    }
    if input.content.is_empty() {
        return Err("Uploaded file is empty".to_string());
    }
    Ok(())
}

fn validate_asset_content(
    asset_kind: &str,
    provider_scope: &str,
    suffix: &str,
    content: &[u8],
) -> Result<ValidationResult, String> {
    let allowed = allowed_suffixes(asset_kind);
    if !allowed.iter().any(|item| *item == suffix) {
        return Ok(ValidationResult {
            status: "invalid".to_string(),
            message: format!("Unsupported file extension: {}", suffix),
            parsed_metadata: json!({}),
            schema_version: String::new(),
        });
    }
    if asset_kind == "script_template" {
        return Ok(ValidationResult {
            status: "valid".to_string(),
            message: "Script template accepted".to_string(),
            parsed_metadata: json!({}),
            schema_version: String::new(),
        });
    }

    let text = String::from_utf8(content.to_vec()).map_err(|e| e.to_string())?;
    let payload = if suffix == ".json" {
        serde_json::from_str::<Value>(&text)
            .map_err(|e| e.to_string())?
    } else if suffix == ".yaml" || suffix == ".yml" {
        match serde_yaml::from_str::<serde_yaml::Value>(&text) {
            Ok(value) => serde_json::to_value(value).map_err(|e| e.to_string())?,
            Err(_) => {
                if text.contains("apiVersion:") && text.contains("kind:") && text.contains("metadata:") {
                    json!({})
                } else {
                    return Ok(ValidationResult {
                        status: "invalid".to_string(),
                        message: "Module definition could not be parsed".to_string(),
                        parsed_metadata: json!({}),
                        schema_version: String::new(),
                    });
                }
            }
        }
    } else {
        json!({})
    };

    if payload == json!({}) && (suffix == ".yaml" || suffix == ".yml") {
        return Ok(ValidationResult {
            status: "valid".to_string(),
            message: "Basic YAML structure accepted without parser support".to_string(),
            parsed_metadata: json!({}),
            schema_version: String::new(),
        });
    }

    let metadata = payload.get("metadata").and_then(Value::as_object).cloned().unwrap_or_else(Map::new);
    let module_id = metadata.get("id").and_then(Value::as_str).unwrap_or("").trim();
    if module_id.is_empty() {
        return Ok(ValidationResult {
            status: "invalid".to_string(),
            message: "metadata.id is required".to_string(),
            parsed_metadata: payload,
            schema_version: String::new(),
        });
    }

    let expected_kind = expected_kind(asset_kind, provider_scope);
    let actual_kind = payload.get("kind").and_then(Value::as_str).unwrap_or("").trim();
    let schema_version = payload
        .get("apiVersion")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    if let Some(expected_kind) = expected_kind {
        if expected_kind != actual_kind {
            return Ok(ValidationResult {
                status: "invalid".to_string(),
                message: format!("Unexpected kind: {}", actual_kind),
                parsed_metadata: payload,
                schema_version,
            });
        }
    }

    Ok(ValidationResult {
        status: "valid".to_string(),
        message: "Validation succeeded".to_string(),
        schema_version,
        parsed_metadata: payload,
    })
}

fn allowed_suffixes(asset_kind: &str) -> &'static [&'static str] {
    match asset_kind {
        "stage_module" | "job_module" | "task_module" => &[".yaml", ".yml", ".json"],
        "script_template" => &[".yaml", ".yml", ".json", ".py", ".sh", ".bat", ".ps1", ".template", ".txt"],
        _ => &[],
    }
}

fn validate_asset_scope(asset_kind: &str, provider_scope: &str) -> Result<(), String> {
    match asset_kind {
        "stage_module" | "job_module" | "script_template" => {
            if provider_scope != "common" {
                return Err(format!("providerScope must be common for {}", asset_kind));
            }
        }
        "task_module" => {
            if provider_scope != "common" && provider_scope != "bamboo" && provider_scope != "jenkins" {
                return Err("providerScope must be one of common, bamboo, jenkins".to_string());
            }
        }
        _ => return Err(format!("Unsupported assetKind: {}", asset_kind)),
    }
    Ok(())
}

fn expected_kind(asset_kind: &str, provider_scope: &str) -> Option<&'static str> {
    match (asset_kind, provider_scope) {
        ("stage_module", _) => Some("StageModule"),
        ("job_module", _) => Some("JobModule"),
        ("task_module", "bamboo") => Some("BambooTaskModule"),
        ("task_module", "jenkins") => Some("JenkinsTaskModule"),
        ("task_module", _) => None,
        _ => None,
    }
}

fn module_storage_dir(asset_kind: &str, provider_scope: &str, module_id: &str, version_number: i32) -> PathBuf {
    module_registry_root()
        .join("uploads")
        .join(asset_kind)
        .join(provider_scope)
        .join(safe_name(module_id))
        .join(format!("v{}", version_number))
}

async fn activate_module_version_with_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    asset_id: Uuid,
    version_id: Uuid,
    asset_kind: &str,
    provider_scope: &str,
    module_id: &str,
    source_path: &Path,
) -> Result<PathBuf, String> {
    let suffix = source_path
        .extension()
        .map(|ext| format!(".{}", ext.to_string_lossy()))
        .unwrap_or_default();
    let target_path = module_active_path(asset_kind, provider_scope, module_id, &suffix);
    remove_stale_active_files(asset_kind, provider_scope, module_id, &target_path)?;
    if let Some(parent) = target_path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::copy(source_path, &target_path).map_err(|e| e.to_string())?;

    sqlx::query(
        r#"
        INSERT INTO buildmeta_module_activation (
            id, created_at, updated_at, asset_id, activated_version_id, activation_status, activated_at, active_path, last_error
        )
        VALUES ($1, NOW(), NOW(), $2, $3, 'active', NOW(), $4, '')
        ON CONFLICT (asset_id)
        DO UPDATE SET activated_version_id = EXCLUDED.activated_version_id,
                      activation_status = 'active',
                      activated_at = NOW(),
                      active_path = EXCLUDED.active_path,
                      last_error = '',
                      updated_at = NOW()
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(asset_id)
    .bind(version_id)
    .bind(target_path.to_string_lossy().to_string())
    .execute(&mut **tx)
    .await
    .map_err(|e| e.to_string())?;

    sqlx::query(
        r#"
        UPDATE buildmeta_module_asset
        SET active_version_id = $1, status = 'active', updated_at = NOW()
        WHERE id = $2
        "#,
    )
    .bind(version_id)
    .bind(asset_id)
    .execute(&mut **tx)
    .await
    .map_err(|e| e.to_string())?;

    Ok(target_path)
}

fn extract_yaml_module_id(text: &str) -> String {
    for line in text.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix("id:") {
            return rest.trim().trim_matches('"').trim_matches('\'').to_string();
        }
    }
    String::new()
}

fn module_active_path(asset_kind: &str, provider_scope: &str, module_id: &str, suffix: &str) -> PathBuf {
    let subdir = match asset_kind {
        "stage_module" => "stages",
        "job_module" => "jobs",
        "task_module" => "tasks",
        "script_template" => "script_templates",
        _ => "misc",
    };
    let provider_segment = if asset_kind == "task_module" {
        provider_scope
    } else {
        "common"
    };
    module_registry_root()
        .join("active")
        .join(subdir)
        .join(provider_segment)
        .join(format!("{}{}", safe_name(module_id), suffix))
}

fn module_registry_root() -> PathBuf {
    if let Ok(path) = std::env::var("MODULE_REGISTRY_ROOT") {
        let trimmed = path.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    repo_root().join("managed_modules")
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap_or_else(|| Path::new(env!("CARGO_MANIFEST_DIR")))
        .to_path_buf()
}

fn remove_stale_active_files(
    asset_kind: &str,
    provider_scope: &str,
    module_id: &str,
    keep_path: &Path,
) -> Result<(), String> {
    let Some(active_dir) = keep_path.parent() else {
        return Err("Active path has no parent directory".to_string());
    };
    if !active_dir.exists() {
        return Ok(());
    }

    let safe_module_id = safe_name(module_id);
    for entry in fs::read_dir(active_dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if !path.is_file() || path == keep_path {
            continue;
        }
        let Some(stem) = path.file_stem().and_then(|value| value.to_str()) else {
            continue;
        };
        if stem != safe_module_id {
            continue;
        }
        let suffix = path
            .extension()
            .map(|ext| format!(".{}", ext.to_string_lossy()))
            .unwrap_or_default();
        if module_active_path(asset_kind, provider_scope, module_id, &suffix) == path {
            fs::remove_file(path).map_err(|e| e.to_string())?;
        }
    }

    Ok(())
}

fn safe_name(value: &str) -> String {
    let mut name = String::new();
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() || ch == '-' || ch == '_' || ch == '.' {
            name.push(ch);
        } else {
            name.push('-');
        }
    }
    let trimmed = name.trim_matches('-').to_string();
    if trimmed.is_empty() { "module".to_string() } else { trimmed }
}

#[cfg(test)]
mod tests {
    use super::{safe_name, validate_asset_content, validate_asset_scope, validate_upload_input, ModuleUploadInput};

    #[test]
    fn upload_scope_requires_common_for_stage_modules() {
        let error = validate_asset_scope("stage_module", "bamboo").unwrap_err();
        assert_eq!(error, "providerScope must be common for stage_module");
    }

    #[test]
    fn validate_asset_content_accepts_valid_stage_json() {
        let payload = br#"{"apiVersion":"buildmod/v1alpha1","kind":"StageModule","metadata":{"id":"prepare","name":"Prepare"},"spec":{"order":10,"enabled":true,"jobs":["prepare-linux"]}}"#;
        let result = validate_asset_content("stage_module", "common", ".json", payload).unwrap();
        assert_eq!(result.status, "valid");
        assert_eq!(result.message, "Validation succeeded");
        assert_eq!(result.schema_version, "buildmod/v1alpha1");
    }

    #[test]
    fn validate_asset_content_rejects_wrong_kind() {
        let payload = br#"{"apiVersion":"buildmod/v1alpha1","kind":"JobModule","metadata":{"id":"prepare"},"spec":{"order":10}}"#;
        let result = validate_asset_content("stage_module", "common", ".json", payload).unwrap();
        assert_eq!(result.status, "invalid");
        assert_eq!(result.message, "Unexpected kind: JobModule");
    }

    #[test]
    fn validate_upload_input_rejects_empty_content() {
        let input = ModuleUploadInput {
            asset_kind: "stage_module".to_string(),
            provider_scope: "common".to_string(),
            module_id: "prepare".to_string(),
            filename: "prepare.json".to_string(),
            content: Vec::new(),
            activate_after_upload: false,
        };
        let error = validate_upload_input(&input).unwrap_err();
        assert_eq!(error, "Uploaded file is empty");
    }

    #[test]
    fn safe_name_replaces_unsupported_characters() {
        assert_eq!(safe_name("prep are/1"), "prep-are-1");
    }
}

fn infer_preview_language(filename: &str) -> String {
    let suffix = Path::new(filename).extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
    match suffix.as_str() {
        "py" => "python".to_string(),
        "sh" => "shell".to_string(),
        "bat" => "batch".to_string(),
        "yaml" | "yml" => "yaml".to_string(),
        "json" => "json".to_string(),
        _ => "text".to_string(),
    }
}

fn read_version_content(row: &sqlx::postgres::PgRow) -> String {
    let path = PathBuf::from(row.get::<String, _>("storage_path"));
    fs::read_to_string(path).unwrap_or_default()
}

fn build_version_diff(older: &sqlx::postgres::PgRow, newer: &sqlx::postgres::PgRow) -> String {
    let old_content = read_version_content(older);
    let new_content = read_version_content(newer);
    let from = format!("{}@v{}", older.get::<String, _>("source_filename"), older.get::<i32, _>("version_number"));
    let to = format!("{}@v{}", newer.get::<String, _>("source_filename"), newer.get::<i32, _>("version_number"));
    let diff = similar::TextDiff::from_lines(&old_content, &new_content);
    diff.unified_diff().header(&from, &to).to_string()
}

fn non_nil(value: Uuid) -> Option<Uuid> {
    if value.is_nil() { None } else { Some(value) }
}
