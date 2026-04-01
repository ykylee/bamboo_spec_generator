use serde_json::{json, Value};
use sqlx::{PgPool, Row};
use uuid::Uuid;

const KEY_COVERITY_CONNECT_URL: &str = "coverity.connect.url";
const KEY_COVERITY_ON_NEW_CERT: &str = "coverity.connect.on_new_cert";
const KEY_COVERITY_COMMIT_ENABLED: &str = "coverity.commit.enabled";
const KEY_GIT_CLONE_URL_TEMPLATE: &str = "repository.git.clone_url_template";
const KEY_REPOSITORY_LINKAGE_MODE: &str = "repository.linkage_mode";
const KEY_BAMBOO_SERVER_URL: &str = "bamboo.server.url";
const KEY_BAMBOO_TOKEN: &str = "bamboo.server.token";
const KEY_JENKINS_SERVER_URL: &str = "jenkins.server.url";
const KEY_JENKINS_USERNAME: &str = "jenkins.server.username";
const KEY_JENKINS_TOKEN: &str = "jenkins.server.token";
const KEY_GITHUB_SERVER_URL: &str = "github.server.url";
const KEY_GITHUB_TOKEN: &str = "github.token";
const KEY_BITBUCKET_SERVER_URL: &str = "bitbucket.server.url";
const KEY_BITBUCKET_TOKEN: &str = "bitbucket.token";
const KEY_GITEA_SERVER_URL: &str = "gitea.server.url";
const KEY_GITEA_TOKEN: &str = "gitea.token";

pub async fn get_coverity_settings(pool: &PgPool) -> Result<Value, sqlx::Error> {
    let commit_enabled = matches!(
        get_setting(pool, KEY_COVERITY_COMMIT_ENABLED)
            .await?
            .trim()
            .to_lowercase()
            .as_str(),
        "1" | "true" | "yes" | "on"
    );
    let on_new_cert = {
        let value = get_setting(pool, KEY_COVERITY_ON_NEW_CERT).await?;
        if value.trim().is_empty() {
            "trust".to_string()
        } else {
            value
        }
    };
    Ok(json!({
        "connectUrl": get_setting(pool, KEY_COVERITY_CONNECT_URL).await?,
        "onNewCert": on_new_cert,
        "commitEnabled": commit_enabled,
        "gitCloneUrlTemplate": get_setting(pool, KEY_GIT_CLONE_URL_TEMPLATE).await?,
        "repositoryLinkageMode": normalize_linkage_mode(&get_setting(pool, KEY_REPOSITORY_LINKAGE_MODE).await?),
    }))
}

pub async fn update_coverity_settings(
    pool: &PgPool,
    connect_url: &str,
    on_new_cert: &str,
    commit_enabled: bool,
    git_clone_url_template: &str,
    repository_linkage_mode: &str,
) -> Result<Value, sqlx::Error> {
    upsert_setting(pool, KEY_COVERITY_CONNECT_URL, connect_url, "Coverity Connect URL").await?;
    upsert_setting(pool, KEY_COVERITY_ON_NEW_CERT, on_new_cert, "Coverity on-new-cert policy").await?;
    upsert_setting(
        pool,
        KEY_COVERITY_COMMIT_ENABLED,
        if commit_enabled { "true" } else { "false" },
        "Coverity commit enabled flag",
    )
    .await?;
    upsert_setting(pool, KEY_GIT_CLONE_URL_TEMPLATE, git_clone_url_template, "Git clone URL template").await?;
    upsert_setting(
        pool,
        KEY_REPOSITORY_LINKAGE_MODE,
        &normalize_linkage_mode(repository_linkage_mode),
        "Repository linkage mode",
    )
    .await?;
    get_coverity_settings(pool).await
}

pub async fn get_bamboo_settings(pool: &PgPool) -> Result<Value, sqlx::Error> {
    let token = get_setting(pool, KEY_BAMBOO_TOKEN).await?;
    Ok(json!({
        "serverUrl": get_setting(pool, KEY_BAMBOO_SERVER_URL).await?,
        "tokenConfigured": !token.trim().is_empty(),
        "tokenMasked": mask_secret(&token),
    }))
}

pub async fn update_bamboo_settings(
    pool: &PgPool,
    server_url: &str,
    token: Option<&str>,
) -> Result<Value, sqlx::Error> {
    upsert_setting(pool, KEY_BAMBOO_SERVER_URL, server_url, "Bamboo server URL").await?;
    if let Some(raw_token) = token {
        let trimmed = raw_token.trim();
        if !trimmed.is_empty() {
            upsert_setting(pool, KEY_BAMBOO_TOKEN, trimmed, "Bamboo token").await?;
        }
    }
    get_bamboo_settings(pool).await
}

pub async fn initialize_specs_draft_data(pool: &PgPool, reset_existing: bool) -> Result<Value, String> {
    let plan_rows = sqlx::query(
        r#"
        SELECT
            bamboo.build_unit_id,
            bamboo.plan_key,
            bamboo.build_id,
            bu.compiler,
            bu.runtime_stack,
            project.project_key,
            repo.id AS repository_id,
            COALESCE(repo.coverity_stream, '') AS coverity_stream
        FROM buildmeta_bamboo_build_unit bamboo
        JOIN buildmeta_build_unit bu ON bu.id = bamboo.build_unit_id
        JOIN buildmeta_project project ON project.id = bu.project_id
        LEFT JOIN buildmeta_repository repo ON repo.id = bu.repository_id
        ORDER BY bamboo.plan_key
        "#,
    )
    .fetch_all(pool)
    .await
    .map_err(|e| e.to_string())?;

    initialize_specs_for_rows(pool, plan_rows, reset_existing).await
}

pub async fn initialize_specs_draft_for_plan(
    pool: &PgPool,
    plan_key: &str,
    reset_existing: bool,
) -> Result<Value, String> {
    let plan_rows = sqlx::query(
        r#"
        SELECT
            bamboo.build_unit_id,
            bamboo.plan_key,
            bamboo.build_id,
            bu.compiler,
            bu.runtime_stack,
            project.project_key,
            repo.id AS repository_id,
            COALESCE(repo.coverity_stream, '') AS coverity_stream
        FROM buildmeta_bamboo_build_unit bamboo
        JOIN buildmeta_build_unit bu ON bu.id = bamboo.build_unit_id
        JOIN buildmeta_project project ON project.id = bu.project_id
        LEFT JOIN buildmeta_repository repo ON repo.id = bu.repository_id
        WHERE bamboo.plan_key = $1
        "#,
    )
    .bind(plan_key)
    .fetch_all(pool)
    .await
    .map_err(|e| e.to_string())?;

    initialize_specs_for_rows(pool, plan_rows, reset_existing).await
}

async fn initialize_specs_for_rows(
    pool: &PgPool,
    plan_rows: Vec<sqlx::postgres::PgRow>,
    reset_existing: bool,
) -> Result<Value, String> {
    let mut tx = pool.begin().await.map_err(|e| e.to_string())?;
    let mut initialized_count = 0;
    let mut updated_count = 0;
    let removed_count = 0;
    let mut skipped_count = 0;

    for row in plan_rows {
        let build_unit_id: Uuid = row.get("build_unit_id");
        let build_id: String = row.get("build_id");
        let compiler: String = row.get("compiler");
        let runtime_stack: String = row.get("runtime_stack");
        let project_key: String = row.get("project_key");
        let repository_id: Option<Uuid> = row.get("repository_id");
        let coverity_stream: String = row.get("coverity_stream");

        if project_key.starts_with("DETACHED-") && repository_id.is_none() {
            skipped_count += 1;
            continue;
        }

        let existing_rows = sqlx::query(
            r#"
            SELECT id, build_key, operating_system, pre_process, build_command, clean_command,
                   language, compiler, analysis_excluded_files, coverity_stream, build_sub_path
            FROM buildmeta_bamboo_build_info
            WHERE bamboo_build_unit_id = $1
            ORDER BY build_key
            "#,
        )
        .bind(build_unit_id)
        .fetch_all(&mut *tx)
        .await
        .map_err(|e| e.to_string())?;

        let (inferred_language, inferred_compiler) = infer_language_and_compiler(&compiler, &runtime_stack);
        if existing_rows.is_empty() {
            sqlx::query(
                r#"
                INSERT INTO buildmeta_bamboo_build_info (
                    id, created_at, updated_at, bamboo_build_unit_id, build_key, operating_system,
                    pre_process, build_command, clean_command, language, compiler,
                    analysis_excluded_files, coverity_stream, build_sub_path
                )
                VALUES ($1, NOW(), NOW(), $2, $3, 'linux', '', '', '', $4, $5, '', $6, '.')
                "#,
            )
            .bind(Uuid::new_v4())
            .bind(build_unit_id)
            .bind(default_build_key(&build_id, "linux"))
            .bind(inferred_language)
            .bind(inferred_compiler)
            .bind(coverity_stream)
            .execute(&mut *tx)
            .await
            .map_err(|e| e.to_string())?;
            initialized_count += 1;
            continue;
        }

        for existing in existing_rows {
            let info_id: Uuid = existing.get("id");
            let operating_system = normalize_or_default(existing.get::<String, _>("operating_system"), "linux");
            let language = normalize_or_default(existing.get::<String, _>("language"), inferred_language);
            let compiler_value = normalize_or_default(existing.get::<String, _>("compiler"), inferred_compiler);
            let stream = normalize_or_default(existing.get::<String, _>("coverity_stream"), &coverity_stream);
            let build_sub_path = normalize_build_sub_path(existing.get("build_sub_path"));
            let pre_process = if reset_existing { String::new() } else { existing.get("pre_process") };
            let build_command = if reset_existing { String::new() } else { existing.get("build_command") };
            let clean_command = if reset_existing { String::new() } else { existing.get("clean_command") };
            let analysis_excluded_files = if reset_existing {
                String::new()
            } else {
                existing.get("analysis_excluded_files")
            };

            let changed = existing.get::<String, _>("operating_system") != operating_system
                || existing.get::<String, _>("language") != language
                || existing.get::<String, _>("compiler") != compiler_value
                || existing.get::<String, _>("coverity_stream") != stream
                || existing.get::<String, _>("build_sub_path") != build_sub_path
                || (reset_existing
                    && (!existing.get::<String, _>("pre_process").is_empty()
                        || !existing.get::<String, _>("build_command").is_empty()
                        || !existing.get::<String, _>("clean_command").is_empty()
                        || !existing
                            .get::<String, _>("analysis_excluded_files")
                            .is_empty()));
            if !changed {
                continue;
            }

            sqlx::query(
                r#"
                UPDATE buildmeta_bamboo_build_info
                SET operating_system = $1,
                    pre_process = $2,
                    build_command = $3,
                    clean_command = $4,
                    language = $5,
                    compiler = $6,
                    analysis_excluded_files = $7,
                    coverity_stream = $8,
                    build_sub_path = $9,
                    updated_at = NOW()
                WHERE id = $10
                "#,
            )
            .bind(operating_system)
            .bind(pre_process)
            .bind(build_command)
            .bind(clean_command)
            .bind(language)
            .bind(compiler_value)
            .bind(analysis_excluded_files)
            .bind(stream)
            .bind(build_sub_path)
            .bind(info_id)
            .execute(&mut *tx)
            .await
            .map_err(|e| e.to_string())?;
            updated_count += 1;
        }
    }

    tx.commit().await.map_err(|e| e.to_string())?;

    Ok(json!({
        "initializedCount": initialized_count,
        "updatedCount": updated_count,
        "removedCount": removed_count,
        "skippedCount": skipped_count,
    }))
}

async fn get_setting(pool: &PgPool, key: &str) -> Result<String, sqlx::Error> {
    let row = sqlx::query("SELECT value FROM buildmeta_systemsetting WHERE key = $1")
        .bind(key)
        .fetch_optional(pool)
        .await?;
    Ok(row.map(|row| row.get::<String, _>("value")).unwrap_or_default())
}

async fn upsert_setting(pool: &PgPool, key: &str, value: &str, description: &str) -> Result<(), sqlx::Error> {
    sqlx::query(
        r#"
        INSERT INTO buildmeta_systemsetting (id, created_at, updated_at, key, value, description)
        VALUES ($1, NOW(), NOW(), $2, $3, $4)
        ON CONFLICT (key)
        DO UPDATE SET value = EXCLUDED.value, description = EXCLUDED.description, updated_at = NOW()
        "#,
    )
    .bind(uuid::Uuid::new_v4())
    .bind(key)
    .bind(value)
    .bind(description)
    .execute(pool)
    .await?;
    Ok(())
}

fn normalize_linkage_mode(value: &str) -> String {
    if value.trim().eq_ignore_ascii_case("create_if_missing") {
        "create_if_missing".to_string()
    } else {
        "linked".to_string()
    }
}

pub async fn get_jenkins_settings(pool: &PgPool) -> Result<Value, sqlx::Error> {
    let env_token = std::env::var("JENKINS_TOKEN").unwrap_or_default();
    let settings_token = get_setting(pool, KEY_JENKINS_TOKEN).await?;
    let env_token = env_token.trim().to_string();
    let settings_token = settings_token.trim().to_string();
    let effective_token = if !env_token.is_empty() {
        env_token.clone()
    } else {
        settings_token.clone()
    };
    Ok(json!({
        "serverUrl": get_setting(pool, KEY_JENKINS_SERVER_URL).await?,
        "username": get_setting(pool, KEY_JENKINS_USERNAME).await?,
        "tokenConfigured": !effective_token.is_empty() || !settings_token.trim().is_empty(),
        "tokenSource": if !env_token.is_empty() { "env" } else if !settings_token.is_empty() { "settings" } else { "" },
        "tokenMasked": mask_secret(&effective_token),
    }))
}

pub async fn update_jenkins_settings(
    pool: &PgPool,
    server_url: &str,
    username: &str,
    token: Option<&str>,
) -> Result<Value, sqlx::Error> {
    upsert_setting(pool, KEY_JENKINS_SERVER_URL, server_url, "Jenkins server URL").await?;
    upsert_setting(pool, KEY_JENKINS_USERNAME, username, "Jenkins username").await?;
    if let Some(raw_token) = token {
        let trimmed = raw_token.trim();
        if !trimmed.is_empty() {
            upsert_setting(pool, KEY_JENKINS_TOKEN, trimmed, "Jenkins token").await?;
        }
    }
    get_jenkins_settings(pool).await
}

pub async fn get_github_settings(pool: &PgPool) -> Result<Value, sqlx::Error> {
    let token = get_setting(pool, KEY_GITHUB_TOKEN).await?;
    Ok(json!({
        "serverUrl": get_setting(pool, KEY_GITHUB_SERVER_URL).await?,
        "tokenConfigured": !token.trim().is_empty(),
        "tokenMasked": mask_secret(&token),
    }))
}

pub async fn update_github_settings(
    pool: &PgPool,
    server_url: &str,
    token: Option<&str>,
) -> Result<Value, sqlx::Error> {
    upsert_setting(pool, KEY_GITHUB_SERVER_URL, server_url, "GitHub server URL").await?;
    if let Some(raw_token) = token {
        let trimmed = raw_token.trim();
        if !trimmed.is_empty() {
            upsert_setting(pool, KEY_GITHUB_TOKEN, trimmed, "GitHub token").await?;
        }
    }
    get_github_settings(pool).await
}

pub async fn get_bitbucket_settings(pool: &PgPool) -> Result<Value, sqlx::Error> {
    let token = get_setting(pool, KEY_BITBUCKET_TOKEN).await?;
    Ok(json!({
        "serverUrl": get_setting(pool, KEY_BITBUCKET_SERVER_URL).await?,
        "tokenConfigured": !token.trim().is_empty(),
        "tokenMasked": mask_secret(&token),
    }))
}

pub async fn update_bitbucket_settings(
    pool: &PgPool,
    server_url: &str,
    token: Option<&str>,
) -> Result<Value, sqlx::Error> {
    upsert_setting(pool, KEY_BITBUCKET_SERVER_URL, server_url, "Bitbucket server URL").await?;
    if let Some(raw_token) = token {
        let trimmed = raw_token.trim();
        if !trimmed.is_empty() {
            upsert_setting(pool, KEY_BITBUCKET_TOKEN, trimmed, "Bitbucket token").await?;
        }
    }
    get_bitbucket_settings(pool).await
}

pub async fn get_gitea_settings(pool: &PgPool) -> Result<Value, sqlx::Error> {
    let token = get_setting(pool, KEY_GITEA_TOKEN).await?;
    Ok(json!({
        "serverUrl": get_setting(pool, KEY_GITEA_SERVER_URL).await?,
        "tokenConfigured": !token.trim().is_empty(),
        "tokenMasked": mask_secret(&token),
    }))
}

pub async fn update_gitea_settings(
    pool: &PgPool,
    server_url: &str,
    token: Option<&str>,
) -> Result<Value, sqlx::Error> {
    upsert_setting(pool, KEY_GITEA_SERVER_URL, server_url, "Gitea server URL").await?;
    if let Some(raw_token) = token {
        let trimmed = raw_token.trim();
        if !trimmed.is_empty() {
            upsert_setting(pool, KEY_GITEA_TOKEN, trimmed, "Gitea token").await?;
        }
    }
    get_gitea_settings(pool).await
}

pub async fn get_jenkins_token_value(pool: &PgPool) -> Result<String, sqlx::Error> {
    get_setting(pool, KEY_JENKINS_TOKEN).await
}

fn default_build_key(build_id: &str, operating_system: &str) -> String {
    format!(
        "{}-{}",
        slugify(build_id),
        slugify(if operating_system.trim().is_empty() { "linux" } else { operating_system })
    )
}

fn normalize_build_sub_path(value: String) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        ".".to_string()
    } else {
        trimmed.to_string()
    }
}

fn normalize_or_default(value: String, fallback: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        fallback.to_string()
    } else {
        trimmed.to_string()
    }
}

fn infer_language_and_compiler(compiler: &str, runtime_stack: &str) -> (&'static str, &'static str) {
    let normalized_compiler = compiler.trim().to_lowercase();
    let normalized_runtime = runtime_stack.trim().to_lowercase();

    if normalized_compiler == "gradle" {
        return ("java", "gradle");
    }
    if normalized_compiler == "maven" || normalized_runtime.contains("java") {
        return ("java", if normalized_compiler == "maven" { "maven" } else { "java" });
    }
    if matches!(normalized_compiler.as_str(), "node" | "javascript" | "typescript" | "node.js")
        || normalized_runtime.contains("node")
    {
        return ("javascript", "node.js");
    }
    if normalized_compiler == "python" || normalized_runtime.contains("python") {
        return ("python", "python");
    }
    if normalized_compiler == "dotnet" || normalized_runtime.contains(".net") {
        return ("csharp", "dotnet");
    }
    ("", "")
}

fn slugify(value: &str) -> String {
    let mut slug = String::new();
    let mut last_dash = false;
    for ch in value.trim().to_lowercase().chars() {
        if ch.is_ascii_alphanumeric() {
            slug.push(ch);
            last_dash = false;
        } else if !last_dash {
            slug.push('-');
            last_dash = true;
        }
    }
    slug.trim_matches('-').to_string()
}

fn mask_secret(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    if trimmed.len() <= 4 {
        return "*".repeat(trimmed.len());
    }
    format!("{}{}", "*".repeat(trimmed.len() - 4), &trimmed[trimmed.len() - 4..])
}

#[cfg(test)]
mod tests {
    use super::{
        default_build_key, infer_language_and_compiler, mask_secret, normalize_build_sub_path,
        normalize_linkage_mode,
    };

    #[test]
    fn default_build_key_normalizes_text() {
        assert_eq!(default_build_key("Tooling API", "linux"), "tooling-api-linux");
    }

    #[test]
    fn build_sub_path_defaults_to_dot() {
        assert_eq!(normalize_build_sub_path(" ".to_string()), ".");
    }

    #[test]
    fn infer_dotnet_language_and_compiler() {
        assert_eq!(infer_language_and_compiler("dotnet", ".NET 8"), ("csharp", "dotnet"));
    }

    #[test]
    fn linkage_mode_defaults_to_linked() {
        assert_eq!(normalize_linkage_mode("invalid"), "linked");
    }

    #[test]
    fn mask_secret_hides_all_but_last_four_chars() {
        assert_eq!(mask_secret("abcd1234"), "****1234");
        assert_eq!(mask_secret("abc"), "***");
        assert_eq!(mask_secret(""), "");
    }
}
