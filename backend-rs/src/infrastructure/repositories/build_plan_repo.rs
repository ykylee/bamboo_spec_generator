use chrono::Datelike;
use serde_json::{json, Value};
use sqlx::{PgPool, Row};
use uuid::Uuid;

#[derive(Debug, Clone)]
struct BuildPlanSummaryRecord {
    project_key: String,
    ci_provider: String,
    build_name: String,
    language: String,
    compiler: String,
    runtime_stack: String,
    external_key: String,
    plan_key: String,
    build_id: String,
    job_path: String,
    static_analysis_tool_version: String,
    coverity_project: String,
    repository_slug: String,
    latest_version: String,
    latest_success: Option<bool>,
    latest_status: String,
    latest_summary: String,
    build_info_count: i64,
}

#[derive(Debug, Clone)]
struct PlanRecord {
    build_unit_id: Uuid,
    project_key: String,
    representative_repo_slug: String,
    representative_repo_key: String,
    build_name: String,
    language: String,
    compiler: String,
    runtime_stack: String,
    plan_key: String,
    build_id: String,
    application_link: String,
    repository_linkage_mode: String,
    repository_id: Option<Uuid>,
    repository_slug: String,
    repository_repo_key: String,
    repository_clone_url: String,
    repository_coverity_project: String,
    repository_coverity_stream: String,
    repository_is_representative: bool,
}

#[derive(Debug, Clone)]
struct RepositoryRecord {
    repo_slug: String,
    repo_key: String,
    clone_url: String,
    coverity_project: String,
    coverity_stream: String,
    is_representative: bool,
}

#[derive(Debug, Clone)]
struct BuildInfoRecord {
    build_key: String,
    operating_system: String,
    pre_process: String,
    build_command: String,
    language: String,
    compiler: String,
    build_sub_path: String,
}

pub async fn list_build_plan_summaries(
    pool: &PgPool,
    ci_provider: Option<&str>,
) -> Result<Vec<Value>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            project.project_key,
            bu.ci_provider,
            bu.display_name AS build_name,
            bu.language,
            bu.compiler,
            bu.runtime_stack,
            bu.external_key,
            COALESCE(bamboo.plan_key, '') AS plan_key,
            COALESCE(bamboo.build_id, '') AS build_id,
            COALESCE(jenkins.job_path, '') AS job_path,
            COALESCE(bamboo.static_analysis_tool_version, '') AS static_analysis_tool_version,
            COALESCE(bamboo.coverity_project, '') AS coverity_project,
            COALESCE(repo.repo_slug, '') AS repository_slug,
            COALESCE(ver.version_text, '') AS latest_version,
            ver.latest_success,
            COALESCE(exec.status, '') AS latest_status,
            COALESCE(exec.summary, '') AS latest_summary,
            COALESCE((
                SELECT COUNT(*)
                FROM buildmeta_bamboo_build_info info
                WHERE info.bamboo_build_unit_id = bu.id
            ), 0) AS build_info_count
        FROM buildmeta_build_unit bu
        JOIN buildmeta_project project ON project.id = bu.project_id
        LEFT JOIN buildmeta_repository repo ON repo.id = bu.repository_id
        LEFT JOIN buildmeta_bamboo_build_unit bamboo ON bamboo.build_unit_id = bu.id
        LEFT JOIN buildmeta_jenkins_build_unit jenkins ON jenkins.build_unit_id = bu.id
        LEFT JOIN buildmeta_build_version ver ON ver.id = bu.latest_version_id
        LEFT JOIN buildmeta_build_execution exec ON exec.id = ver.latest_execution_id
        WHERE ($1::text IS NULL OR bu.ci_provider = $1)
        ORDER BY project.project_key, bu.display_name, bu.external_key
        "#,
    )
    .bind(ci_provider)
    .fetch_all(pool)
    .await?;

    let summaries = rows
        .into_iter()
        .map(|row| BuildPlanSummaryRecord {
            project_key: row.get("project_key"),
            ci_provider: row.get("ci_provider"),
            build_name: row.get("build_name"),
            language: row.get("language"),
            compiler: row.get("compiler"),
            runtime_stack: row.get("runtime_stack"),
            external_key: row.get("external_key"),
            plan_key: row.get("plan_key"),
            build_id: row.get("build_id"),
            job_path: row.get("job_path"),
            static_analysis_tool_version: row.get("static_analysis_tool_version"),
            coverity_project: row.get("coverity_project"),
            repository_slug: row.get("repository_slug"),
            latest_version: row.get("latest_version"),
            latest_success: row.get("latest_success"),
            latest_status: row.get("latest_status"),
            latest_summary: row.get("latest_summary"),
            build_info_count: row.get("build_info_count"),
        })
        .map(|row| {
            let detail_url = if row.ci_provider == "jenkins" {
                let job_path = if row.job_path.is_empty() {
                    row.external_key.clone()
                } else {
                    row.job_path.clone()
                };
                format!("/projects/{}/jenkins-jobs/{}/", row.project_key, job_path)
            } else {
                let plan_key = if row.plan_key.is_empty() {
                    row.external_key.clone()
                } else {
                    row.plan_key.clone()
                };
                format!("/projects/{}/builds/{}/", row.project_key, plan_key)
            };
            let build_info_url = if row.ci_provider == "jenkins" {
                String::new()
            } else {
                let plan_key = if row.plan_key.is_empty() {
                    row.external_key.clone()
                } else {
                    row.plan_key.clone()
                };
                format!("/projects/{}/builds/{}/infos/", row.project_key, plan_key)
            };

            json!({
                "projectKey": row.project_key,
                "ciProvider": row.ci_provider,
                "buildName": row.build_name,
                "language": row.language,
                "compiler": row.compiler,
                "buildType": row.compiler,
                "runtimeStack": row.runtime_stack,
                "planKey": if row.plan_key.is_empty() { row.external_key.clone() } else { row.plan_key },
                "buildId": if row.build_id.is_empty() { row.external_key.clone() } else { row.build_id },
                "staticAnalysisToolVersion": row.static_analysis_tool_version,
                "coverityProject": row.coverity_project,
                "repositorySlug": row.repository_slug,
                "latestVersion": row.latest_version,
                "latestSuccess": row.latest_success,
                "resultStatus": legacy_result_status(&row.latest_status),
                "summaryMessage": row.latest_summary,
                "buildInfoCount": row.build_info_count,
                "detailUrl": detail_url,
                "buildInfoUrl": build_info_url,
            })
        })
        .collect();
    Ok(summaries)
}

pub async fn get_active_definition(pool: &PgPool, plan_key: &str) -> Result<Option<Value>, sqlx::Error> {
    let Some(plan) = fetch_plan(pool, plan_key).await? else {
        return Ok(None);
    };

    let active_definition = sqlx::query(
        r#"
        SELECT year, version, definition_json
        FROM buildmeta_build_unit_definition
        WHERE build_unit_id = $1 AND is_active = true
        ORDER BY created_at
        LIMIT 1
        "#,
    )
    .bind(plan.build_unit_id)
    .fetch_optional(pool)
    .await?;

    if let Some(row) = active_definition {
        let year: String = row.get("year");
        let version: i32 = row.get("version");
        let definition: Value = row.get("definition_json");
        return Ok(Some(json!({
            "planKey": plan.plan_key,
            "buildId": plan.build_id,
            "year": year,
            "definitionVersion": version.to_string(),
            "definition": definition,
        })));
    }

    let build_infos = fetch_build_infos(pool, plan.build_unit_id).await?;
    let fallback = build_infos.first().cloned().unwrap_or(BuildInfoRecord {
        build_key: String::new(),
        operating_system: "linux".to_string(),
        pre_process: String::new(),
        build_command: String::new(),
        language: String::new(),
        compiler: String::new(),
        build_sub_path: ".".to_string(),
    });
    let linkage_mode = resolve_linkage_mode(pool, &plan).await?;
    let clone_url = resolve_clone_url(pool, &plan).await?;
    let definition = json!({
        "buildId": plan.build_id,
        "buildKey": fallback.build_key,
        "name": if fallback.build_key.is_empty() {
            plan.build_name.clone()
        } else {
            format!("{} {}", plan.build_name, fallback.build_key)
        },
        "planKey": plan.plan_key,
        "description": plan.build_name,
        "language": if fallback.language.is_empty() {
            if plan.runtime_stack.is_empty() { "python".to_string() } else { plan.runtime_stack.clone() }
        } else {
            fallback.language.clone()
        },
        "compiler": if fallback.compiler.is_empty() {
            if plan.compiler.is_empty() { "script".to_string() } else { plan.compiler.clone() }
        } else {
            fallback.compiler.clone()
        },
        "repository": {
            "provider": "bitbucket",
            "projectKey": if plan.repository_repo_key.is_empty() {
                plan.representative_repo_key.clone()
            } else {
                plan.repository_repo_key.clone()
            },
            "repoSlug": plan.repository_slug,
            "linkageMode": linkage_mode,
            "applicationLink": default_application_link(&plan.application_link),
            "cloneUrl": clone_url,
            "branches": ["dev", "release", "master"],
        },
        "requirements": {
            "os": normalize_operating_system(&fallback.operating_system),
            "extraCapabilities": [],
        },
        "build": {
            "subPath": normalize_build_sub_path(&fallback.build_sub_path),
            "prepareCommand": fallback.pre_process,
            "buildCommand": fallback.build_command,
            "staticAnalysis": {
                "customTool": {
                    "commands": ["custom-tool analyze {buildCommand}"],
                }
            },
            "runtimeRequirements": {
                "commands": default_runtime_commands(&fallback.language, &fallback.compiler, &plan.runtime_stack, &plan.compiler),
                "envVars": default_runtime_env_vars(&fallback.language, &fallback.compiler, &plan.runtime_stack, &plan.compiler),
            },
            "postBuildTrigger": {
                "type": "plan",
                "targetPlanKey": "",
            }
        },
    });
    Ok(Some(json!({
        "planKey": plan.plan_key,
        "buildId": plan.build_id,
        "year": chrono::Utc::now().year().to_string(),
        "definitionVersion": "",
        "definition": definition,
    })))
}

pub async fn get_prepare_context(pool: &PgPool, plan_key: &str) -> Result<Option<Value>, sqlx::Error> {
    let Some(plan) = fetch_plan(pool, plan_key).await? else {
        return Ok(None);
    };
    let repositories = fetch_repositories(pool, plan.build_unit_id).await?;
    let current_repository = pick_current_repository(&plan, &repositories);
    let clone_url = resolve_clone_url(pool, &plan).await?;
    let linkage_mode = resolve_linkage_mode(pool, &plan).await?;
    let application_link = default_application_link(&plan.application_link);

    Ok(Some(json!({
        "planKey": plan.plan_key,
        "project": {
            "jiraProjectKey": plan.project_key,
            "bitbucketProjectKey": current_repository.as_ref().map(|repo| repo.repo_key.clone()).unwrap_or_default(),
            "representativeRepoSlug": plan.representative_repo_slug,
        },
        "currentRepository": {
            "repoSlug": current_repository.as_ref().map(|repo| repo.repo_slug.clone()).unwrap_or_default(),
            "coverityProject": current_repository.as_ref().map(|repo| repo.coverity_project.clone()).unwrap_or_default(),
            "coverityStream": current_repository.as_ref().map(|repo| repo.coverity_stream.clone()).unwrap_or_default(),
            "applicationLink": application_link,
            "cloneUrl": clone_url,
            "linkageMode": linkage_mode,
        },
        "projectBuild": {
            "buildName": plan.build_name,
            "language": plan.language,
            "compiler": plan.compiler,
            "buildType": plan.compiler,
        },
        "repositories": repositories.iter().map(|repo| {
            json!({
                "repoSlug": repo.repo_slug,
                "isRepresentative": repo.is_representative,
            })
        }).collect::<Vec<_>>(),
        "variables": {
            "JIRA_PROJECT_KEY": plan.project_key,
            "BITBUCKET_PROJECT_KEY": current_repository.as_ref().map(|repo| repo.repo_key.clone()).unwrap_or_default(),
            "BITBUCKET_REPO_SLUG": current_repository.as_ref().map(|repo| repo.repo_slug.clone()).unwrap_or_default(),
            "BITBUCKET_APPLICATION_LINK": application_link,
            "BITBUCKET_CLONE_URL": clone_url,
            "REPRESENTATIVE_REPO_SLUG": plan.representative_repo_slug,
            "COVERITY_PROJECT": current_repository.as_ref().map(|repo| repo.coverity_project.clone()).unwrap_or_default(),
            "COVERITY_STREAM": current_repository.as_ref().map(|repo| repo.coverity_stream.clone()).unwrap_or_default(),
            "PROJECT_BUILD_NAME": plan.build_name,
            "PROJECT_BUILD_TYPE": plan.compiler,
            "currentRepository.linkageMode": linkage_mode,
        },
    })))
}

pub async fn get_executions(pool: &PgPool, plan_key: &str) -> Result<Option<Vec<Value>>, sqlx::Error> {
    let Some(plan) = fetch_plan(pool, plan_key).await? else {
        return Ok(None);
    };
    let execution_rows = sqlx::query(
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
    .bind(plan.build_unit_id)
    .fetch_all(pool)
    .await?;

    let mut executions = Vec::with_capacity(execution_rows.len());
    for row in execution_rows {
        let execution_id: Uuid = row.get("id");
        let static_analysis_rows = sqlx::query(
            r#"
            SELECT tool_name, status, summary, metrics_json
            FROM buildmeta_static_analysis_result
            WHERE build_execution_id = $1
            ORDER BY tool_name
            "#,
        )
        .bind(execution_id)
        .fetch_all(pool)
        .await?;
        let static_analysis_results = static_analysis_rows
            .into_iter()
            .map(|result| {
                let metrics_json: Option<Value> = result.get("metrics_json");
                json!({
                    "toolName": result.get::<String, _>("tool_name"),
                    "status": result.get::<String, _>("status"),
                    "summary": result.get::<String, _>("summary"),
                    "metricsJson": metrics_json,
                })
            })
            .collect::<Vec<_>>();
        let status: String = row.get("status");
        executions.push(json!({
            "buildExecutionId": execution_id.to_string(),
            "buildVersionId": row.get::<Option<Uuid>, _>("build_version_id").map(|value| value.to_string()).unwrap_or_default(),
            "buildKey": row.get::<String, _>("external_execution_key"),
            "version": row.get::<String, _>("version_text"),
            "buildNumber": row.get::<String, _>("execution_number"),
            "commitHash": row.get::<String, _>("commit_hash"),
            "success": status == "success",
            "resultStatus": legacy_result_status(&status),
            "summaryMessage": row.get::<String, _>("summary"),
            "stageName": row.get::<String, _>("stage_name"),
            "jobName": row.get::<String, _>("job_name"),
            "taskName": row.get::<String, _>("task_name"),
            "startedAt": row.get::<Option<chrono::DateTime<chrono::Utc>>, _>("started_at"),
            "finishedAt": row.get::<Option<chrono::DateTime<chrono::Utc>>, _>("finished_at"),
            "createdAt": row.get::<chrono::DateTime<chrono::Utc>, _>("created_at"),
            "staticAnalysisResults": static_analysis_results,
        }));
    }
    Ok(Some(executions))
}

async fn fetch_plan(pool: &PgPool, plan_key: &str) -> Result<Option<PlanRecord>, sqlx::Error> {
    let row = sqlx::query(
        r#"
        SELECT
            bu.id AS build_unit_id,
            project.project_key,
            COALESCE(rep.repo_slug, '') AS representative_repo_slug,
            COALESCE(rep.repo_key, '') AS representative_repo_key,
            bu.display_name AS build_name,
            bu.language,
            bu.compiler,
            bu.runtime_stack,
            bamboo.plan_key,
            bamboo.build_id,
            bamboo.application_link,
            bamboo.repository_linkage_mode,
            repo.id AS repository_id,
            COALESCE(repo.repo_slug, '') AS repository_slug,
            COALESCE(repo.repo_key, '') AS repository_repo_key,
            COALESCE(repo.clone_url, '') AS repository_clone_url,
            COALESCE(repo.coverity_project, '') AS repository_coverity_project,
            COALESCE(repo.coverity_stream, '') AS repository_coverity_stream,
            COALESCE(repo.is_representative, false) AS repository_is_representative
        FROM buildmeta_bamboo_build_unit bamboo
        JOIN buildmeta_build_unit bu ON bu.id = bamboo.build_unit_id
        JOIN buildmeta_project project ON project.id = bu.project_id
        LEFT JOIN buildmeta_repository repo ON repo.id = bu.repository_id
        LEFT JOIN buildmeta_repository rep ON rep.id = project.representative_repository_id
        WHERE bamboo.plan_key = $1
        "#,
    )
    .bind(plan_key)
    .fetch_optional(pool)
    .await?;
    Ok(row.map(|row| PlanRecord {
        build_unit_id: row.get("build_unit_id"),
        project_key: row.get("project_key"),
        representative_repo_slug: row.get("representative_repo_slug"),
        representative_repo_key: row.get("representative_repo_key"),
        build_name: row.get("build_name"),
        language: row.get("language"),
        compiler: row.get("compiler"),
        runtime_stack: row.get("runtime_stack"),
        plan_key: row.get("plan_key"),
        build_id: row.get("build_id"),
        application_link: row.get("application_link"),
        repository_linkage_mode: row.get("repository_linkage_mode"),
        repository_id: row.get("repository_id"),
        repository_slug: row.get("repository_slug"),
        repository_repo_key: row.get("repository_repo_key"),
        repository_clone_url: row.get("repository_clone_url"),
        repository_coverity_project: row.get("repository_coverity_project"),
        repository_coverity_stream: row.get("repository_coverity_stream"),
        repository_is_representative: row.get("repository_is_representative"),
    }))
}

async fn fetch_build_infos(pool: &PgPool, build_unit_id: Uuid) -> Result<Vec<BuildInfoRecord>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            build_key,
            operating_system,
            pre_process,
            build_command,
            language,
            compiler,
            coverity_stream,
            build_sub_path
        FROM buildmeta_bamboo_build_info
        WHERE bamboo_build_unit_id = $1
        ORDER BY build_key
        "#,
    )
    .bind(build_unit_id)
    .fetch_all(pool)
    .await?;
    Ok(rows.into_iter().map(|row| BuildInfoRecord {
        build_key: row.get("build_key"),
        operating_system: row.get("operating_system"),
        pre_process: row.get("pre_process"),
        build_command: row.get("build_command"),
        language: row.get("language"),
        compiler: row.get("compiler"),
        build_sub_path: row.get("build_sub_path"),
    }).collect())
}

async fn fetch_repositories(pool: &PgPool, build_unit_id: Uuid) -> Result<Vec<RepositoryRecord>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            repo.repo_slug,
            repo.repo_key,
            repo.clone_url,
            repo.coverity_project,
            repo.coverity_stream,
            repo.is_representative
        FROM buildmeta_build_unit bu
        JOIN buildmeta_project project ON project.id = bu.project_id
        JOIN buildmeta_repository repo ON repo.project_id = project.id
        WHERE bu.id = $1
        ORDER BY repo.repo_slug
        "#,
    )
    .bind(build_unit_id)
    .fetch_all(pool)
    .await?;
    Ok(rows.into_iter().map(|row| RepositoryRecord {
        repo_slug: row.get("repo_slug"),
        repo_key: row.get("repo_key"),
        clone_url: row.get("clone_url"),
        coverity_project: row.get("coverity_project"),
        coverity_stream: row.get("coverity_stream"),
        is_representative: row.get("is_representative"),
    }).collect())
}

fn pick_current_repository(plan: &PlanRecord, repositories: &[RepositoryRecord]) -> Option<RepositoryRecord> {
    if plan.repository_id.is_some() {
        return Some(RepositoryRecord {
            repo_slug: plan.repository_slug.clone(),
            repo_key: plan.repository_repo_key.clone(),
            clone_url: plan.repository_clone_url.clone(),
            coverity_project: plan.repository_coverity_project.clone(),
            coverity_stream: plan.repository_coverity_stream.clone(),
            is_representative: plan.repository_is_representative,
        });
    }
    repositories
        .iter()
        .find(|repo| repo.is_representative)
        .cloned()
        .or_else(|| repositories.first().cloned())
}

async fn resolve_clone_url(pool: &PgPool, plan: &PlanRecord) -> Result<String, sqlx::Error> {
    let current_repository = pick_current_repository(plan, &fetch_repositories(pool, plan.build_unit_id).await?);
    if let Some(repository) = current_repository {
        if !repository.clone_url.trim().is_empty() {
            return Ok(repository.clone_url.trim().to_string());
        }
        let template = get_setting(pool, "repository.git.clone_url_template").await?;
        if !template.is_empty() {
            let project_key = if repository.repo_key.is_empty() {
                plan.representative_repo_key.clone()
            } else {
                repository.repo_key
            };
            return Ok(template
                .replace("{project_key}", &project_key)
                .replace("{repo_slug}", &repository.repo_slug)
                .replace("{project_key_lower}", &project_key.to_lowercase())
                .replace("{repo_slug_lower}", &repository.repo_slug.to_lowercase())
                .trim()
                .to_string());
        }
    }
    Ok(String::new())
}

async fn resolve_linkage_mode(pool: &PgPool, plan: &PlanRecord) -> Result<String, sqlx::Error> {
    if !plan.repository_linkage_mode.trim().is_empty() {
        return Ok(plan.repository_linkage_mode.trim().to_string());
    }
    let configured = get_setting(pool, "repository.linkage_mode").await?;
    if configured.trim() == "create_if_missing" {
        Ok("create_if_missing".to_string())
    } else {
        Ok("linked".to_string())
    }
}

async fn get_setting(pool: &PgPool, key: &str) -> Result<String, sqlx::Error> {
    let row = sqlx::query("SELECT value FROM buildmeta_systemsetting WHERE key = $1")
        .bind(key)
        .fetch_optional(pool)
        .await?;
    Ok(row.map(|row| row.get::<String, _>("value")).unwrap_or_default())
}

fn normalize_operating_system(value: &str) -> String {
    let normalized = value.trim().to_lowercase();
    if normalized.is_empty() {
        "linux".to_string()
    } else {
        normalized
    }
}

fn normalize_build_sub_path(value: &str) -> String {
    let normalized = value.trim();
    if normalized.is_empty() {
        ".".to_string()
    } else {
        normalized.to_string()
    }
}

fn default_runtime_commands(language: &str, compiler: &str, runtime_stack: &str, build_compiler: &str) -> Vec<String> {
    let language = if language.trim().is_empty() { runtime_stack } else { language }.to_lowercase();
    let compiler = if compiler.trim().is_empty() { build_compiler } else { compiler }.to_lowercase();
    let mut commands = Vec::new();
    if language == "java" || compiler == "maven" {
        commands.push("mvn".to_string());
    }
    if ["node", "node.js", "javascript", "typescript"].contains(&language.as_str()) {
        commands.push("npm".to_string());
    }
    commands.push("coverity".to_string());
    commands
}

fn default_runtime_env_vars(language: &str, compiler: &str, runtime_stack: &str, build_compiler: &str) -> Vec<String> {
    let language = if language.trim().is_empty() { runtime_stack } else { language }.to_lowercase();
    let compiler = if compiler.trim().is_empty() { build_compiler } else { compiler }.to_lowercase();
    if language == "java" || compiler == "maven" {
        vec!["JAVA_HOME".to_string()]
    } else {
        vec!["PATH".to_string()]
    }
}

fn default_application_link(value: &str) -> String {
    if value.trim().is_empty() {
        "BITBUCKET_SERVER".to_string()
    } else {
        value.trim().to_string()
    }
}

fn legacy_result_status(status: &str) -> String {
    if status.trim().eq_ignore_ascii_case("success") {
        "successful".to_string()
    } else {
        status.trim().to_lowercase()
    }
}
