use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::{PgPool, Row};
use uuid::Uuid;

const PROVIDER_BAMBOO: &str = "bamboo";
const PROVIDER_JENKINS: &str = "jenkins";
const STATUS_ACTIVE: &str = "active";
const BUILD_TYPE: &str = "build";

#[derive(Debug, Clone)]
struct ProjectRecord {
    id: Uuid,
    project_key: String,
    name: String,
    description: String,
    owner_team: String,
    service_type: String,
    ci_provider: String,
    status: String,
    representative_repository_id: Option<Uuid>,
    representative_repo_slug: String,
    representative_repo_key: String,
}

#[derive(Debug, Clone)]
struct RepositoryRecord {
    repo_slug: String,
    repository_type: String,
    repository_provider: String,
    repo_type: String,
    repo_key: String,
    clone_url: String,
    default_branch: String,
    coverity_project: String,
    coverity_stream: String,
    is_representative: bool,
}

#[derive(Debug, Clone)]
struct BuildUnitRecord {
    ci_provider: String,
    external_key: String,
    display_name: String,
    description: String,
    unit_type: String,
    repository_slug: String,
    language: String,
    compiler: String,
    runtime_stack: String,
    lifecycle_status: String,
    is_enabled: bool,
    latest_version: String,
    latest_success: Option<bool>,
    plan_key: String,
    build_id: String,
    bamboo_project_key: String,
    repository_linkage_mode: String,
    static_analysis_tool_version: String,
    coverity_project: String,
    build_info_count: i64,
    job_path: String,
    job_type: String,
    folder_path: String,
    pipeline_kind: String,
    active_definition_count: i64,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ProjectRepositoryInput {
    pub repo_slug: String,
    #[serde(default = "default_repository_type")]
    pub repository_type: String,
    #[serde(default = "default_repository_provider")]
    pub repository_provider: String,
    #[serde(default = "default_legacy_repo_type")]
    pub repo_type: String,
    #[serde(default)]
    pub repo_key: String,
    #[serde(default)]
    pub clone_url: String,
    #[serde(default)]
    pub default_branch: String,
    #[serde(default)]
    pub coverity_project: String,
    #[serde(default)]
    pub coverity_stream: String,
    #[serde(default)]
    pub is_representative: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ProjectBuildInput {
    #[serde(default)]
    pub build_name: String,
    #[serde(default)]
    pub language: String,
    #[serde(default, alias = "buildType")]
    pub compiler: String,
    #[serde(default)]
    pub runtime_stack: String,
    #[serde(default)]
    pub build_id: String,
    #[serde(default)]
    pub plan_key: String,
    #[serde(default)]
    pub repository_slug: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct BuildUnitProviderDetailsInput {
    #[serde(default)]
    pub plan_key: String,
    #[serde(default)]
    pub build_id: String,
    #[serde(default)]
    pub bamboo_project_key: String,
    #[serde(default)]
    pub repository_linkage_mode: String,
    #[serde(default)]
    pub application_link: String,
    #[serde(default)]
    pub static_analysis_tool_version: String,
    #[serde(default)]
    pub coverity_project: String,
    #[serde(default)]
    pub job_path: String,
    #[serde(default)]
    pub job_type: String,
    #[serde(default)]
    pub folder_path: String,
    #[serde(default)]
    pub pipeline_kind: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ProjectBuildUnitInput {
    #[serde(default)]
    pub external_key: String,
    #[serde(default)]
    pub display_name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_build_unit_type")]
    pub unit_type: String,
    #[serde(default)]
    pub repository_slug: String,
    #[serde(default)]
    pub language: String,
    #[serde(default)]
    pub compiler: String,
    #[serde(default)]
    pub runtime_stack: String,
    #[serde(default = "default_lifecycle_status")]
    pub lifecycle_status: String,
    #[serde(default = "default_is_enabled")]
    pub is_enabled: bool,
    #[serde(default)]
    pub provider_details: Option<BuildUnitProviderDetailsInput>,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ProjectCreateInput {
    #[serde(default)]
    pub project_key: String,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub owner_team: String,
    #[serde(default)]
    pub service_type: String,
    #[serde(default = "default_ci_provider")]
    pub ci_provider: String,
    #[serde(default = "default_status")]
    pub status: String,
    #[serde(default)]
    pub jira_project_key: String,
    #[serde(default)]
    pub bitbucket_project_key: String,
    #[serde(default)]
    pub representative_repo_slug: String,
    #[serde(default)]
    pub repositories: Vec<ProjectRepositoryInput>,
    #[serde(default)]
    pub builds: Vec<ProjectBuildInput>,
    #[serde(default)]
    pub build_units: Vec<ProjectBuildUnitInput>,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ProjectUpdateInput {
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub owner_team: String,
    #[serde(default)]
    pub service_type: String,
    #[serde(default = "default_ci_provider")]
    pub ci_provider: String,
    #[serde(default = "default_status")]
    pub status: String,
    #[serde(default)]
    pub bitbucket_project_key: String,
    #[serde(default)]
    pub representative_repo_slug: String,
    #[serde(default)]
    pub repositories: Vec<ProjectRepositoryInput>,
    #[serde(default)]
    pub builds: Vec<ProjectBuildInput>,
    #[serde(default)]
    pub build_units: Vec<ProjectBuildUnitInput>,
}

pub async fn list_project_summaries(pool: &PgPool, ci_provider: Option<&str>) -> Result<Vec<Value>, sqlx::Error> {
    let projects = fetch_projects(pool, ci_provider).await?;
    let mut summaries = Vec::with_capacity(projects.len());
    for project in projects {
        let repositories = fetch_repositories(pool, project.id).await?;
        let build_units = fetch_build_units(pool, project.id).await?;
        let generation = build_generation_status(&project, &repositories, &build_units);
        let missing_coverity_count = repositories
            .iter()
            .filter(|repo| repo.coverity_project.is_empty() || repo.coverity_stream.is_empty())
            .count();
        let failed_build_count = build_units
            .iter()
            .filter(|build| matches!(build.latest_success, Some(false)))
            .count();
        let mut warning_tags = generation
            .get("generationReadinessIssues")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        if missing_coverity_count > 0 {
            warning_tags.push(json!(format!("Coverity 미지정 {}", missing_coverity_count)));
        }
        if failed_build_count > 0 {
            warning_tags.push(json!(format!("마지막 빌드 실패 {}", failed_build_count)));
        }
        summaries.push(json!({
            "projectKey": project.project_key,
            "name": project.name,
            "description": project.description,
            "ownerTeam": project.owner_team,
            "serviceType": project.service_type,
            "ciProvider": project.ci_provider,
            "status": project.status,
            "representativeRepoSlug": project.representative_repo_slug,
            "repositoryCount": repositories.len(),
            "repositorySlugs": sorted_repository_slugs(&repositories),
            "buildUnitCount": build_units.len(),
            "buildCount": build_units.len(),
            "generationReady": generation["generationReady"],
            "generationReadinessIssues": generation["generationReadinessIssues"],
            "readyBuildCount": generation["readyBuildCount"],
            "activeDefinitionCount": generation["activeDefinitionCount"],
            "missingCoverityCount": missing_coverity_count,
            "failedBuildCount": failed_build_count,
            "warningTags": warning_tags,
            "metadataWarningTags": warning_tags,
            "needsAttention": !warning_tags.is_empty(),
            "jiraProjectKey": project.project_key,
            "bitbucketProjectKey": project.representative_repo_key,
        }));
    }
    Ok(summaries)
}

pub async fn get_project_detail(
    pool: &PgPool,
    project_key: &str,
    ci_provider: Option<&str>,
) -> Result<Option<Value>, sqlx::Error> {
    let Some(project) = fetch_project_by_key(pool, project_key, ci_provider).await? else {
        return Ok(None);
    };
    let repositories = fetch_repositories(pool, project.id).await?;
    let build_units = fetch_build_units(pool, project.id).await?;
    let generation = build_generation_status(&project, &repositories, &build_units);
    let mut repositories_sorted = repositories.clone();
    repositories_sorted.sort_by(|left, right| left.repo_slug.cmp(&right.repo_slug));
    let mut build_units_sorted = build_units.clone();
    build_units_sorted.sort_by(|left, right| left.display_name.cmp(&right.display_name));

    Ok(Some(json!({
        "projectKey": project.project_key,
        "name": project.name,
        "description": project.description,
        "ownerTeam": project.owner_team,
        "serviceType": project.service_type,
        "ciProvider": project.ci_provider,
        "status": project.status,
        "representativeRepoSlug": project.representative_repo_slug,
        "generation": generation,
        "repositories": repositories_sorted.iter().map(serialize_repository).collect::<Vec<_>>(),
        "buildUnits": build_units_sorted.iter().map(serialize_build_unit).collect::<Vec<_>>(),
        "jiraProjectKey": project.project_key,
        "bitbucketProjectKey": project.representative_repo_key,
        "builds": build_units_sorted.iter().map(|build| serialize_legacy_build(build, project_key)).collect::<Vec<_>>(),
    })))
}

pub async fn create_project(pool: &PgPool, payload: &ProjectCreateInput) -> Result<Value, String> {
    let project_key = resolve_project_key(&payload.project_key, &payload.jira_project_key);
    let ci_provider = normalize_ci_provider(&payload.ci_provider);
    if project_key.is_empty() {
        return Err("projectKey is required.".to_string());
    }
    let exists = sqlx::query(
        "SELECT id FROM buildmeta_project WHERE project_key = $1 AND ci_provider = $2 LIMIT 1",
    )
    .bind(&project_key)
    .bind(&ci_provider)
    .fetch_optional(pool)
    .await
    .map_err(|error| error.to_string())?;
    if exists.is_some() {
        return Err(format!("Project '{}:{}' already exists.", ci_provider, project_key));
    }
    save_project(pool, None, &project_key, payload).await
}

pub async fn update_project(
    pool: &PgPool,
    project_key: &str,
    payload: &ProjectUpdateInput,
) -> Result<Option<Value>, String> {
    let ci_provider = normalize_ci_provider(&payload.ci_provider);
    let existing = sqlx::query(
        r#"
        SELECT id
        FROM buildmeta_project
        WHERE project_key = $1 AND ci_provider = $2
        LIMIT 1
        "#,
    )
    .bind(project_key)
    .bind(&ci_provider)
    .fetch_optional(pool)
    .await
    .map_err(|error| error.to_string())?;
    let Some(existing) = existing else {
        return Ok(None);
    };
    let project_id: Uuid = existing.get("id");
    save_project(pool, Some(project_id), project_key, payload).await.map(Some)
}

async fn save_project<T>(pool: &PgPool, existing_project_id: Option<Uuid>, project_key: &str, payload: &T) -> Result<Value, String>
where
    T: ProjectPayload,
{
    let repositories = payload.repositories();
    let build_units = payload.build_units();
    validate_repositories(&repositories)?;
    validate_build_units(&build_units, &repositories)?;

    let ci_provider = normalize_ci_provider(payload.ci_provider());
    let mut tx = pool.begin().await.map_err(|error| error.to_string())?;

    let project_id = if let Some(project_id) = existing_project_id {
        sqlx::query(
            r#"
            UPDATE buildmeta_project
            SET name = $1, description = $2, owner_team = $3, service_type = $4, status = $5, updated_at = NOW()
            WHERE id = $6
            "#,
        )
        .bind(resolve_project_name(payload.name(), project_key))
        .bind(payload.description())
        .bind(payload.owner_team())
        .bind(payload.service_type())
        .bind(normalize_status(payload.status()))
        .bind(project_id)
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;
        project_id
    } else {
        let project_id = Uuid::new_v4();
        sqlx::query(
            r#"
            INSERT INTO buildmeta_project (
                id, created_at, updated_at, project_key, name, description, owner_team, service_type,
                ci_provider, status, representative_repository_id
            )
            VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, $6, $7, $8, NULL)
            "#,
        )
        .bind(project_id)
        .bind(project_key)
        .bind(resolve_project_name(payload.name(), project_key))
        .bind(payload.description())
        .bind(payload.owner_team())
        .bind(payload.service_type())
        .bind(&ci_provider)
        .bind(normalize_status(payload.status()))
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;
        project_id
    };

    sqlx::query(
        "UPDATE buildmeta_repository SET is_representative = false, updated_at = NOW() WHERE project_id = $1",
    )
    .bind(project_id)
    .execute(&mut *tx)
    .await
    .map_err(|error| error.to_string())?;

    let default_repo_key = payload.bitbucket_project_key().trim().to_string();
    let mut repository_ids = Vec::new();
    let mut representative_repository_id: Option<Uuid> = None;

    for repository in &repositories {
        let repo_slug = repository.repo_slug.trim();
        let repo_id = sqlx::query(
            "SELECT id FROM buildmeta_repository WHERE project_id = $1 AND repo_slug = $2 LIMIT 1",
        )
        .bind(project_id)
        .bind(repo_slug)
        .fetch_optional(&mut *tx)
        .await
        .map_err(|error| error.to_string())?
        .map(|row| row.get("id"))
        .unwrap_or_else(Uuid::new_v4);

        let repo_key = first_non_empty(&[
            repository.repo_key.trim(),
            default_repo_key.as_str(),
        ]);

        sqlx::query(
            r#"
            INSERT INTO buildmeta_repository (
                id, created_at, updated_at, project_id, repository_type, repository_provider, repo_type,
                repo_key, repo_slug, clone_url, default_branch, is_representative, coverity_project, coverity_stream
            )
            VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (id)
            DO UPDATE SET
                updated_at = NOW(),
                repository_type = EXCLUDED.repository_type,
                repository_provider = EXCLUDED.repository_provider,
                repo_type = EXCLUDED.repo_type,
                repo_key = EXCLUDED.repo_key,
                clone_url = EXCLUDED.clone_url,
                default_branch = EXCLUDED.default_branch,
                is_representative = EXCLUDED.is_representative,
                coverity_project = EXCLUDED.coverity_project,
                coverity_stream = EXCLUDED.coverity_stream
            "#,
        )
        .bind(repo_id)
        .bind(project_id)
        .bind(normalize_repository_type(&repository.repository_type))
        .bind(normalize_repository_provider(&repository.repository_provider, &repository.repo_type))
        .bind(normalize_legacy_repo_type(&repository.repo_type))
        .bind(repo_key)
        .bind(repo_slug)
        .bind(repository.clone_url.trim())
        .bind(repository.default_branch.trim())
        .bind(repository.is_representative)
        .bind(repository.coverity_project.trim())
        .bind(repository.coverity_stream.trim())
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;

        if repository.is_representative {
            representative_repository_id = Some(repo_id);
        }
        repository_ids.push((repo_slug.to_string(), repo_id));
    }

    if representative_repository_id.is_none() {
        if !payload.representative_repo_slug().trim().is_empty() {
            representative_repository_id = repository_ids
                .iter()
                .find(|(slug, _)| slug == payload.representative_repo_slug().trim())
                .map(|(_, id)| *id);
        }
        if representative_repository_id.is_none() {
            representative_repository_id = repository_ids.first().map(|(_, id)| *id);
        }
    }

    sqlx::query(
        "UPDATE buildmeta_project SET representative_repository_id = $1, updated_at = NOW() WHERE id = $2",
    )
    .bind(representative_repository_id)
    .bind(project_id)
    .execute(&mut *tx)
    .await
    .map_err(|error| error.to_string())?;

    if !default_repo_key.is_empty() {
        sqlx::query(
            "UPDATE buildmeta_repository SET repo_key = $1, updated_at = NOW() WHERE project_id = $2",
        )
        .bind(&default_repo_key)
        .bind(project_id)
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;
    }

    let repository_map = repository_ids
        .iter()
        .map(|(slug, id)| (slug.clone(), *id))
        .collect::<std::collections::HashMap<_, _>>();

    let mut incoming_external_keys = Vec::new();
    for build_unit in &build_units {
        let external_key = build_unit.external_key.trim();
        incoming_external_keys.push(external_key.to_string());
        let existing_build = sqlx::query(
            "SELECT id, project_id FROM buildmeta_build_unit WHERE ci_provider = $1 AND external_key = $2 LIMIT 1",
        )
        .bind(&ci_provider)
        .bind(external_key)
        .fetch_optional(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;
        let build_unit_id = if let Some(existing_build) = existing_build {
            let existing_project_id: Uuid = existing_build.get("project_id");
            if existing_project_id != project_id {
                let message = if ci_provider == PROVIDER_BAMBOO {
                    format!("Build plan '{}' is already linked to another project.", external_key)
                } else {
                    format!("BuildUnit '{}:{}' is already linked to another project.", ci_provider, external_key)
                };
                return Err(message);
            }
            existing_build.get("id")
        } else {
            Uuid::new_v4()
        };
        let repository_id = if build_unit.repository_slug.trim().is_empty() {
            None
        } else {
            repository_map.get(build_unit.repository_slug.trim()).copied()
        };

        sqlx::query(
            r#"
            INSERT INTO buildmeta_build_unit (
                id, created_at, updated_at, project_id, repository_id, ci_provider, unit_type, external_key,
                display_name, description, language, compiler, runtime_stack, lifecycle_status, is_enabled, latest_version_id
            )
            VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NULL)
            ON CONFLICT (id)
            DO UPDATE SET
                updated_at = NOW(),
                project_id = EXCLUDED.project_id,
                repository_id = EXCLUDED.repository_id,
                unit_type = EXCLUDED.unit_type,
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                language = EXCLUDED.language,
                compiler = EXCLUDED.compiler,
                runtime_stack = EXCLUDED.runtime_stack,
                lifecycle_status = EXCLUDED.lifecycle_status,
                is_enabled = EXCLUDED.is_enabled
            "#,
        )
        .bind(build_unit_id)
        .bind(project_id)
        .bind(repository_id)
        .bind(&ci_provider)
        .bind(normalize_unit_type(&build_unit.unit_type))
        .bind(external_key)
        .bind(build_unit.display_name.trim())
        .bind(build_unit.description.trim())
        .bind(build_unit.language.trim())
        .bind(build_unit.compiler.trim())
        .bind(build_unit.runtime_stack.trim())
        .bind(normalize_status(&build_unit.lifecycle_status))
        .bind(build_unit.is_enabled)
        .execute(&mut *tx)
        .await
        .map_err(|error| error.to_string())?;

        if ci_provider == PROVIDER_BAMBOO {
            upsert_bamboo_build_unit(&mut tx, build_unit_id, build_unit).await?;
        } else if ci_provider == PROVIDER_JENKINS {
            upsert_jenkins_build_unit(&mut tx, build_unit_id, build_unit).await?;
        }
    }

    prune_removed_build_units(&mut tx, project_id, &incoming_external_keys).await?;
    prune_removed_repositories(&mut tx, project_id, repositories.iter().map(|repo| repo.repo_slug.trim().to_string()).collect()).await?;

    tx.commit().await.map_err(|error| error.to_string())?;

    get_project_detail(pool, project_key, Some(&ci_provider))
        .await
        .map_err(|error| error.to_string())?
        .ok_or_else(|| format!("Project '{}:{}' could not be loaded after save.", ci_provider, project_key))
}

async fn fetch_projects(pool: &PgPool, ci_provider: Option<&str>) -> Result<Vec<ProjectRecord>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            p.id,
            p.project_key,
            p.name,
            p.description,
            p.owner_team,
            p.service_type,
            p.ci_provider,
            p.status,
            p.representative_repository_id,
            COALESCE(rr.repo_slug, '') AS representative_repo_slug,
            COALESCE(rr.repo_key, '') AS representative_repo_key
        FROM buildmeta_project p
        LEFT JOIN buildmeta_repository rr ON rr.id = p.representative_repository_id
        WHERE ($1::text IS NULL OR p.ci_provider = $1)
        ORDER BY p.ci_provider, p.project_key
        "#,
    )
    .bind(ci_provider)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|row| ProjectRecord {
            id: row.get("id"),
            project_key: row.get("project_key"),
            name: row.get("name"),
            description: row.get("description"),
            owner_team: row.get("owner_team"),
            service_type: row.get("service_type"),
            ci_provider: row.get("ci_provider"),
            status: row.get("status"),
            representative_repository_id: row.get("representative_repository_id"),
            representative_repo_slug: row.get("representative_repo_slug"),
            representative_repo_key: row.get("representative_repo_key"),
        })
        .collect())
}

async fn fetch_project_by_key(
    pool: &PgPool,
    project_key: &str,
    ci_provider: Option<&str>,
) -> Result<Option<ProjectRecord>, sqlx::Error> {
    let row = sqlx::query(
        r#"
        SELECT
            p.id,
            p.project_key,
            p.name,
            p.description,
            p.owner_team,
            p.service_type,
            p.ci_provider,
            p.status,
            p.representative_repository_id,
            COALESCE(rr.repo_slug, '') AS representative_repo_slug,
            COALESCE(rr.repo_key, '') AS representative_repo_key
        FROM buildmeta_project p
        LEFT JOIN buildmeta_repository rr ON rr.id = p.representative_repository_id
        WHERE p.project_key = $1
          AND ($2::text IS NULL OR p.ci_provider = $2)
        LIMIT 1
        "#,
    )
    .bind(project_key)
    .bind(ci_provider)
    .fetch_optional(pool)
    .await?;
    Ok(row.map(|row| ProjectRecord {
        id: row.get("id"),
        project_key: row.get("project_key"),
        name: row.get("name"),
        description: row.get("description"),
        owner_team: row.get("owner_team"),
        service_type: row.get("service_type"),
        ci_provider: row.get("ci_provider"),
        status: row.get("status"),
        representative_repository_id: row.get("representative_repository_id"),
        representative_repo_slug: row.get("representative_repo_slug"),
        representative_repo_key: row.get("representative_repo_key"),
    }))
}

async fn fetch_repositories(pool: &PgPool, project_id: Uuid) -> Result<Vec<RepositoryRecord>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            repo_slug,
            repository_type,
            repository_provider,
            repo_type,
            repo_key,
            clone_url,
            default_branch,
            coverity_project,
            coverity_stream,
            is_representative
        FROM buildmeta_repository
        WHERE project_id = $1
        ORDER BY repo_slug
        "#,
    )
    .bind(project_id)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|row| RepositoryRecord {
            repo_slug: row.get("repo_slug"),
            repository_type: row.get("repository_type"),
            repository_provider: row.get("repository_provider"),
            repo_type: row.get("repo_type"),
            repo_key: row.get("repo_key"),
            clone_url: row.get("clone_url"),
            default_branch: row.get("default_branch"),
            coverity_project: row.get("coverity_project"),
            coverity_stream: row.get("coverity_stream"),
            is_representative: row.get("is_representative"),
        })
        .collect())
}

async fn fetch_build_units(pool: &PgPool, project_id: Uuid) -> Result<Vec<BuildUnitRecord>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            bu.ci_provider,
            bu.external_key,
            bu.display_name,
            bu.description,
            bu.unit_type,
            COALESCE(repo.repo_slug, '') AS repository_slug,
            bu.language,
            bu.compiler,
            bu.runtime_stack,
            bu.lifecycle_status,
            bu.is_enabled,
            COALESCE(ver.version_text, '') AS latest_version,
            ver.latest_success,
            COALESCE(bamboo.plan_key, '') AS plan_key,
            COALESCE(bamboo.build_id, '') AS build_id,
            COALESCE(bamboo.bamboo_project_key, '') AS bamboo_project_key,
            COALESCE(bamboo.repository_linkage_mode, '') AS repository_linkage_mode,
            COALESCE(bamboo.static_analysis_tool_version, '') AS static_analysis_tool_version,
            COALESCE(bamboo.coverity_project, '') AS coverity_project,
            COALESCE((
                SELECT COUNT(*)
                FROM buildmeta_bamboo_build_info info
                WHERE info.bamboo_build_unit_id = bu.id
            ), 0) AS build_info_count,
            COALESCE(jenkins.job_path, '') AS job_path,
            COALESCE(jenkins.job_type, '') AS job_type,
            COALESCE(jenkins.folder_path, '') AS folder_path,
            COALESCE(jenkins.pipeline_kind, '') AS pipeline_kind,
            COALESCE((
                SELECT COUNT(*)
                FROM buildmeta_build_unit_definition def
                WHERE def.build_unit_id = bu.id AND def.is_active = true
            ), 0) AS active_definition_count
        FROM buildmeta_build_unit bu
        LEFT JOIN buildmeta_repository repo ON repo.id = bu.repository_id
        LEFT JOIN buildmeta_build_version ver ON ver.id = bu.latest_version_id
        LEFT JOIN buildmeta_bamboo_build_unit bamboo ON bamboo.build_unit_id = bu.id
        LEFT JOIN buildmeta_jenkins_build_unit jenkins ON jenkins.build_unit_id = bu.id
        WHERE bu.project_id = $1
        ORDER BY bu.display_name
        "#,
    )
    .bind(project_id)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|row| BuildUnitRecord {
            ci_provider: row.get("ci_provider"),
            external_key: row.get("external_key"),
            display_name: row.get("display_name"),
            description: row.get("description"),
            unit_type: row.get("unit_type"),
            repository_slug: row.get("repository_slug"),
            language: row.get("language"),
            compiler: row.get("compiler"),
            runtime_stack: row.get("runtime_stack"),
            lifecycle_status: row.get("lifecycle_status"),
            is_enabled: row.get("is_enabled"),
            latest_version: row.get("latest_version"),
            latest_success: row.get("latest_success"),
            plan_key: row.get("plan_key"),
            build_id: row.get("build_id"),
            bamboo_project_key: row.get("bamboo_project_key"),
            repository_linkage_mode: row.get("repository_linkage_mode"),
            static_analysis_tool_version: row.get("static_analysis_tool_version"),
            coverity_project: row.get("coverity_project"),
            build_info_count: row.get("build_info_count"),
            job_path: row.get("job_path"),
            job_type: row.get("job_type"),
            folder_path: row.get("folder_path"),
            pipeline_kind: row.get("pipeline_kind"),
            active_definition_count: row.get("active_definition_count"),
        })
        .collect())
}

fn sorted_repository_slugs(repositories: &[RepositoryRecord]) -> Vec<String> {
    let mut slugs = repositories
        .iter()
        .map(|repo| repo.repo_slug.clone())
        .collect::<Vec<_>>();
    slugs.sort();
    slugs
}

fn build_generation_status(
    project: &ProjectRecord,
    repositories: &[RepositoryRecord],
    build_units: &[BuildUnitRecord],
) -> Value {
    let mut issues = Vec::new();
    if repositories.is_empty() {
        issues.push("저장소 없음".to_string());
    }
    if build_units.is_empty() {
        issues.push("빌드 단위 없음".to_string());
    }
    if project.representative_repository_id.is_none() {
        if repositories.is_empty() {
            issues.push("대표 저장소 없음".to_string());
        } else {
            issues.push("대표 저장소 메타데이터 불일치".to_string());
        }
    }
    let unlinked_build_count = build_units.iter().filter(|build| build.repository_slug.is_empty()).count();
    let builds_without_definition = if project.ci_provider == "bamboo" {
        build_units.iter().filter(|build| build.build_info_count == 0).count()
    } else {
        build_units
            .iter()
            .filter(|build| build.active_definition_count == 0)
            .count()
    };
    if unlinked_build_count > 0 {
        issues.push(format!("저장소 연결 없는 빌드 단위 {}", unlinked_build_count));
    }
    if builds_without_definition > 0 {
        let message = if project.ci_provider == "bamboo" {
            "빌드 정보 없음"
        } else {
            "활성 정의 없음"
        };
        issues.push(format!("{} {}", message, builds_without_definition));
    }
    let active_definition_count: i64 = build_units.iter().map(|build| build.active_definition_count).sum();
    json!({
        "generationReady": build_units.len() > 0 && issues.is_empty(),
        "generationReadinessIssues": issues,
        "readyBuildCount": (build_units.len() as i64) - (unlinked_build_count as i64) - (builds_without_definition as i64),
        "activeDefinitionCount": active_definition_count,
        "totalBuildCount": build_units.len(),
    })
}

fn serialize_repository(repository: &RepositoryRecord) -> Value {
    json!({
        "repoSlug": repository.repo_slug,
        "repositoryType": repository.repository_type,
        "repositoryProvider": repository.repository_provider,
        "repoType": repository.repo_type,
        "repoKey": repository.repo_key,
        "cloneUrl": repository.clone_url,
        "defaultBranch": repository.default_branch,
        "coverityProject": repository.coverity_project,
        "coverityStream": repository.coverity_stream,
        "isRepresentative": repository.is_representative,
    })
}

fn serialize_build_unit(build: &BuildUnitRecord) -> Value {
    let provider_details = if build.ci_provider == "jenkins" {
        json!({
            "jobPath": build.job_path,
            "jobType": build.job_type,
            "folderPath": build.folder_path,
            "pipelineKind": build.pipeline_kind,
        })
    } else {
        json!({
            "planKey": build.plan_key,
            "buildId": build.build_id,
            "bambooProjectKey": build.bamboo_project_key,
        })
    };
    json!({
        "externalKey": build.external_key,
        "displayName": build.display_name,
        "description": build.description,
        "unitType": build.unit_type,
        "repositorySlug": build.repository_slug,
        "language": build.language,
        "compiler": build.compiler,
        "runtimeStack": build.runtime_stack,
        "lifecycleStatus": build.lifecycle_status,
        "isEnabled": build.is_enabled,
        "latestVersion": build.latest_version,
        "latestSuccess": build.latest_success,
        "providerDetails": provider_details,
    })
}

fn serialize_legacy_build(build: &BuildUnitRecord, project_key: &str) -> Value {
    let detail_url = if build.ci_provider == "jenkins" {
        let job_path = if build.job_path.is_empty() {
            &build.external_key
        } else {
            &build.job_path
        };
        format!("/projects/{}/jenkins-jobs/{}/", project_key, job_path)
    } else {
        let plan_key = if build.plan_key.is_empty() {
            &build.external_key
        } else {
            &build.plan_key
        };
        format!("/projects/{}/builds/{}/", project_key, plan_key)
    };
    json!({
        "buildName": build.display_name,
        "language": build.language,
        "compiler": build.compiler,
        "buildType": build.compiler,
        "runtimeStack": build.runtime_stack,
        "repositorySlug": build.repository_slug,
        "planKey": if build.plan_key.is_empty() { build.external_key.clone() } else { build.plan_key.clone() },
        "buildId": if build.build_id.is_empty() { build.external_key.clone() } else { build.build_id.clone() },
        "jobPath": if build.job_path.is_empty() { build.external_key.clone() } else { build.job_path.clone() },
        "jobType": build.job_type,
        "folderPath": build.folder_path,
        "pipelineKind": build.pipeline_kind,
        "externalKey": build.external_key,
        "generationReady": true,
        "activeDefinitionYear": "",
        "staticAnalysisToolVersion": build.static_analysis_tool_version,
        "coverityProject": build.coverity_project,
        "repositoryLinkageModeOverride": build.repository_linkage_mode,
        "buildInfoCount": build.build_info_count,
        "latestVersion": build.latest_version,
        "latestSuccess": build.latest_success,
        "buildInfoUrl": "",
        "detailUrl": detail_url,
        "ciProvider": build.ci_provider,
    })
}

trait ProjectPayload {
    fn name(&self) -> &str;
    fn description(&self) -> &str;
    fn owner_team(&self) -> &str;
    fn service_type(&self) -> &str;
    fn ci_provider(&self) -> &str;
    fn status(&self) -> &str;
    fn bitbucket_project_key(&self) -> &str;
    fn representative_repo_slug(&self) -> &str;
    fn repositories(&self) -> Vec<ProjectRepositoryInput>;
    fn build_units(&self) -> Vec<ProjectBuildUnitInput>;
}

impl ProjectPayload for ProjectCreateInput {
    fn name(&self) -> &str { &self.name }
    fn description(&self) -> &str { &self.description }
    fn owner_team(&self) -> &str { &self.owner_team }
    fn service_type(&self) -> &str { &self.service_type }
    fn ci_provider(&self) -> &str { &self.ci_provider }
    fn status(&self) -> &str { &self.status }
    fn bitbucket_project_key(&self) -> &str { &self.bitbucket_project_key }
    fn representative_repo_slug(&self) -> &str { &self.representative_repo_slug }
    fn repositories(&self) -> Vec<ProjectRepositoryInput> { self.repositories.clone() }
    fn build_units(&self) -> Vec<ProjectBuildUnitInput> { normalize_build_units(&self.build_units, &self.builds) }
}

impl ProjectPayload for ProjectUpdateInput {
    fn name(&self) -> &str { &self.name }
    fn description(&self) -> &str { &self.description }
    fn owner_team(&self) -> &str { &self.owner_team }
    fn service_type(&self) -> &str { &self.service_type }
    fn ci_provider(&self) -> &str { &self.ci_provider }
    fn status(&self) -> &str { &self.status }
    fn bitbucket_project_key(&self) -> &str { &self.bitbucket_project_key }
    fn representative_repo_slug(&self) -> &str { &self.representative_repo_slug }
    fn repositories(&self) -> Vec<ProjectRepositoryInput> { self.repositories.clone() }
    fn build_units(&self) -> Vec<ProjectBuildUnitInput> { normalize_build_units(&self.build_units, &self.builds) }
}

fn default_ci_provider() -> String {
    PROVIDER_BAMBOO.to_string()
}

fn default_status() -> String {
    STATUS_ACTIVE.to_string()
}

fn default_repository_type() -> String {
    "git".to_string()
}

fn default_repository_provider() -> String {
    "bitbucket".to_string()
}

fn default_legacy_repo_type() -> String {
    "bitbucket".to_string()
}

fn default_build_unit_type() -> String {
    BUILD_TYPE.to_string()
}

fn default_lifecycle_status() -> String {
    STATUS_ACTIVE.to_string()
}

fn default_is_enabled() -> bool {
    true
}

fn resolve_project_key(project_key: &str, jira_project_key: &str) -> String {
    first_non_empty(&[project_key.trim(), jira_project_key.trim()]).to_string()
}

fn resolve_project_name(name: &str, project_key: &str) -> String {
    first_non_empty(&[name.trim(), project_key.trim()]).to_string()
}

fn normalize_ci_provider(value: &str) -> String {
    match value.trim().to_lowercase().as_str() {
        PROVIDER_JENKINS => PROVIDER_JENKINS.to_string(),
        _ => PROVIDER_BAMBOO.to_string(),
    }
}

fn normalize_status(value: &str) -> String {
    if value.trim().is_empty() {
        STATUS_ACTIVE.to_string()
    } else {
        value.trim().to_string()
    }
}

fn normalize_repository_type(value: &str) -> String {
    if value.trim().eq_ignore_ascii_case("svn") {
        "svn".to_string()
    } else {
        "git".to_string()
    }
}

fn normalize_repository_provider(provider: &str, legacy_repo_type: &str) -> String {
    let normalized = provider.trim().to_lowercase();
    if ["generic_git", "github", "bitbucket", "gitea", "generic_svn"].contains(&normalized.as_str()) {
        return normalized;
    }
    if normalize_repository_type(legacy_repo_type) == "svn" {
        "generic_svn".to_string()
    } else if legacy_repo_type.trim().eq_ignore_ascii_case("bitbucket") {
        "bitbucket".to_string()
    } else {
        "generic_git".to_string()
    }
}

fn normalize_legacy_repo_type(value: &str) -> String {
    if value.trim().eq_ignore_ascii_case("bitbucket") {
        "bitbucket".to_string()
    } else {
        "git".to_string()
    }
}

fn normalize_unit_type(value: &str) -> String {
    if value.trim().is_empty() {
        BUILD_TYPE.to_string()
    } else {
        value.trim().to_string()
    }
}

fn normalize_build_units(
    explicit: &[ProjectBuildUnitInput],
    legacy_builds: &[ProjectBuildInput],
) -> Vec<ProjectBuildUnitInput> {
    if !explicit.is_empty() {
        return explicit.to_vec();
    }
    legacy_builds
        .iter()
        .map(|build| {
            let external_key = first_non_empty(&[build.plan_key.trim(), build.build_id.trim()]).to_string();
            ProjectBuildUnitInput {
                external_key,
                display_name: build.build_name.clone(),
                description: String::new(),
                unit_type: BUILD_TYPE.to_string(),
                repository_slug: build.repository_slug.clone(),
                language: inferred_language(&build.language, &build.compiler, &build.runtime_stack),
                compiler: build.compiler.clone(),
                runtime_stack: build.runtime_stack.clone(),
                lifecycle_status: STATUS_ACTIVE.to_string(),
                is_enabled: true,
                provider_details: Some(BuildUnitProviderDetailsInput {
                    plan_key: build.plan_key.clone(),
                    build_id: build.build_id.clone(),
                    ..BuildUnitProviderDetailsInput::default()
                }),
            }
        })
        .collect()
}

fn inferred_language(language: &str, compiler: &str, runtime_stack: &str) -> String {
    if !language.trim().is_empty() {
        return language.trim().to_string();
    }

    let normalized_compiler = compiler.trim().to_lowercase();
    let normalized_runtime = runtime_stack.trim().to_lowercase();

    if normalized_compiler == "gradle" || normalized_compiler == "maven" || normalized_runtime.contains("java") {
        return "java".to_string();
    }
    if matches!(normalized_compiler.as_str(), "node" | "node.js" | "javascript" | "typescript")
        || normalized_runtime.contains("node")
    {
        return "javascript".to_string();
    }
    if normalized_compiler == "python" || normalized_runtime.contains("python") {
        return "python".to_string();
    }
    if normalized_compiler == "dotnet" || normalized_runtime.contains(".net") {
        return "csharp".to_string();
    }

    runtime_stack.trim().to_string()
}

fn validate_repositories(repositories: &[ProjectRepositoryInput]) -> Result<(), String> {
    let mut seen = std::collections::HashSet::new();
    let mut representative_count = 0;
    for repository in repositories {
        let repo_slug = repository.repo_slug.trim();
        if repo_slug.is_empty() {
            return Err("Repository repoSlug is required.".to_string());
        }
        if !seen.insert(repo_slug.to_string()) {
            return Err(format!("Repository '{}' is duplicated in the request.", repo_slug));
        }
        if repository.is_representative {
            representative_count += 1;
        }
    }
    if representative_count > 1 {
        return Err("Only one representative repository can be provided per request.".to_string());
    }
    Ok(())
}

fn validate_build_units(
    build_units: &[ProjectBuildUnitInput],
    repositories: &[ProjectRepositoryInput],
) -> Result<(), String> {
    let repository_slugs = repositories
        .iter()
        .map(|repository| repository.repo_slug.trim().to_string())
        .collect::<std::collections::HashSet<_>>();
    let mut external_keys = std::collections::HashSet::new();
    let mut plan_keys = std::collections::HashSet::new();
    let mut build_ids = std::collections::HashSet::new();

    for build_unit in build_units {
        let external_key = build_unit.external_key.trim();
        let display_name = build_unit.display_name.trim();
        let repository_slug = build_unit.repository_slug.trim();
        let provider_details = build_unit.provider_details.clone().unwrap_or_default();
        let plan_key = first_non_empty(&[provider_details.plan_key.trim(), external_key]);
        let build_id = first_non_empty(&[provider_details.build_id.trim(), external_key]);

        if external_key.is_empty() {
            return Err("Build externalKey is required.".to_string());
        }
        if display_name.is_empty() {
            return Err("Build displayName is required.".to_string());
        }
        if !repository_slug.is_empty() && !repository_slugs.contains(repository_slug) {
            return Err(format!(
                "Build repositorySlug '{}' is not registered in repositories.",
                repository_slug
            ));
        }
        if !external_keys.insert(external_key.to_string()) {
            return Err(format!("Build externalKey '{}' is duplicated in the request.", external_key));
        }
        if !plan_key.is_empty() && !plan_keys.insert(plan_key.to_string()) {
            return Err(format!("Build planKey '{}' is duplicated in the request.", plan_key));
        }
        if !build_id.is_empty() && !build_ids.insert(build_id.to_string()) {
            return Err(format!("Build buildId '{}' is duplicated in the request.", build_id));
        }
    }
    Ok(())
}

async fn upsert_bamboo_build_unit(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    build_unit_id: Uuid,
    build_unit: &ProjectBuildUnitInput,
) -> Result<(), String> {
    let provider_details = build_unit.provider_details.clone().unwrap_or_default();
    let requested_plan_key = first_non_empty(&[
        provider_details.plan_key.trim(),
        build_unit.external_key.trim(),
    ])
    .to_string();
    let requested_build_id = first_non_empty(&[
        provider_details.build_id.trim(),
        build_unit.external_key.trim(),
    ])
    .to_string();

    let conflicting_plan = sqlx::query(
        "SELECT build_unit_id, build_id FROM buildmeta_bamboo_build_unit WHERE plan_key = $1 AND build_unit_id <> $2 LIMIT 1",
    )
    .bind(&requested_plan_key)
    .bind(build_unit_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(|error| error.to_string())?;
    if let Some(conflicting_plan) = conflicting_plan {
        let existing_build_id: String = conflicting_plan.get("build_id");
        if existing_build_id != requested_build_id {
            return Err(format!(
                "Build plan '{}' and buildId '{}' refer to different existing build plans.",
                requested_plan_key, requested_build_id
            ));
        }
        return Err(format!(
            "Build plan '{}' is already linked to another project.",
            requested_plan_key
        ));
    }

    let conflicting_build = sqlx::query(
        "SELECT build_unit_id, plan_key FROM buildmeta_bamboo_build_unit WHERE build_id = $1 AND build_unit_id <> $2 LIMIT 1",
    )
    .bind(&requested_build_id)
    .bind(build_unit_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(|error| error.to_string())?;
    if let Some(conflicting_build) = conflicting_build {
        let existing_plan_key: String = conflicting_build.get("plan_key");
        if existing_plan_key != requested_plan_key {
            return Err(format!(
                "Build buildId '{}' already exists with a different planKey.",
                requested_build_id
            ));
        }
        return Err(format!(
            "Build plan '{}' is already linked to another project.",
            requested_plan_key
        ));
    }

    sqlx::query(
        r#"
        INSERT INTO buildmeta_bamboo_build_unit (
            build_unit_id, created_at, updated_at, bamboo_project_key, plan_key, build_id,
            repository_linkage_mode, application_link, static_analysis_tool_version, coverity_project
        )
        VALUES ($1, NOW(), NOW(), $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (build_unit_id)
        DO UPDATE SET
            updated_at = NOW(),
            bamboo_project_key = EXCLUDED.bamboo_project_key,
            plan_key = EXCLUDED.plan_key,
            build_id = EXCLUDED.build_id,
            repository_linkage_mode = EXCLUDED.repository_linkage_mode,
            application_link = EXCLUDED.application_link,
            static_analysis_tool_version = EXCLUDED.static_analysis_tool_version,
            coverity_project = EXCLUDED.coverity_project
        "#,
    )
    .bind(build_unit_id)
    .bind(provider_details.bamboo_project_key.trim())
    .bind(&requested_plan_key)
    .bind(&requested_build_id)
    .bind(provider_details.repository_linkage_mode.trim())
    .bind(provider_details.application_link.trim())
    .bind(provider_details.static_analysis_tool_version.trim())
    .bind(provider_details.coverity_project.trim())
    .execute(&mut **tx)
    .await
    .map_err(|error| error.to_string())?;

    Ok(())
}

async fn upsert_jenkins_build_unit(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    build_unit_id: Uuid,
    build_unit: &ProjectBuildUnitInput,
) -> Result<(), String> {
    let provider_details = build_unit.provider_details.clone().unwrap_or_default();
    let job_path = first_non_empty(&[
        provider_details.job_path.trim(),
        build_unit.external_key.trim(),
    ])
    .to_string();
    sqlx::query(
        r#"
        INSERT INTO buildmeta_jenkins_build_unit (
            build_unit_id, created_at, updated_at, job_path, job_type, folder_path, pipeline_kind
        )
        VALUES ($1, NOW(), NOW(), $2, $3, $4, $5)
        ON CONFLICT (build_unit_id)
        DO UPDATE SET
            updated_at = NOW(),
            job_path = EXCLUDED.job_path,
            job_type = EXCLUDED.job_type,
            folder_path = EXCLUDED.folder_path,
            pipeline_kind = EXCLUDED.pipeline_kind
        "#,
    )
    .bind(build_unit_id)
    .bind(job_path)
    .bind(provider_details.job_type.trim())
    .bind(provider_details.folder_path.trim())
    .bind(provider_details.pipeline_kind.trim())
    .execute(&mut **tx)
    .await
    .map_err(|error| error.to_string())?;
    Ok(())
}

async fn prune_removed_build_units(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    project_id: Uuid,
    incoming_external_keys: &[String],
) -> Result<(), String> {
    if incoming_external_keys.is_empty() {
        sqlx::query("DELETE FROM buildmeta_build_unit WHERE project_id = $1")
            .bind(project_id)
            .execute(&mut **tx)
            .await
            .map_err(|error| error.to_string())?;
        return Ok(());
    }
    sqlx::query("DELETE FROM buildmeta_build_unit WHERE project_id = $1 AND NOT (external_key = ANY($2))")
        .bind(project_id)
        .bind(incoming_external_keys)
        .execute(&mut **tx)
        .await
        .map_err(|error| error.to_string())?;
    Ok(())
}

async fn prune_removed_repositories(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    project_id: Uuid,
    incoming_repo_slugs: Vec<String>,
) -> Result<(), String> {
    if incoming_repo_slugs.is_empty() {
        sqlx::query("UPDATE buildmeta_project SET representative_repository_id = NULL, updated_at = NOW() WHERE id = $1")
            .bind(project_id)
            .execute(&mut **tx)
            .await
            .map_err(|error| error.to_string())?;
        sqlx::query("DELETE FROM buildmeta_repository WHERE project_id = $1")
            .bind(project_id)
            .execute(&mut **tx)
            .await
            .map_err(|error| error.to_string())?;
        return Ok(());
    }
    let representative_row = sqlx::query(
        r#"
        SELECT p.representative_repository_id, r.repo_slug
        FROM buildmeta_project p
        LEFT JOIN buildmeta_repository r ON r.id = p.representative_repository_id
        WHERE p.id = $1
        "#,
    )
    .bind(project_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(|error| error.to_string())?;
    if let Some(representative_row) = representative_row {
        let repo_slug: String = representative_row.get::<Option<String>, _>("repo_slug").unwrap_or_default();
        if !repo_slug.is_empty() && !incoming_repo_slugs.contains(&repo_slug) {
            sqlx::query("UPDATE buildmeta_project SET representative_repository_id = NULL, updated_at = NOW() WHERE id = $1")
                .bind(project_id)
                .execute(&mut **tx)
                .await
                .map_err(|error| error.to_string())?;
        }
    }
    sqlx::query("DELETE FROM buildmeta_repository WHERE project_id = $1 AND NOT (repo_slug = ANY($2))")
        .bind(project_id)
        .bind(&incoming_repo_slugs)
        .execute(&mut **tx)
        .await
        .map_err(|error| error.to_string())?;
    Ok(())
}

fn first_non_empty<'a>(values: &[&'a str]) -> &'a str {
    for value in values {
        if !value.trim().is_empty() {
            return value.trim();
        }
    }
    ""
}
