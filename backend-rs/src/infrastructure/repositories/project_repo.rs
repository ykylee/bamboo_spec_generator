use sqlx::PgPool;
use crate::domain::projects::entities::Project;

pub struct SqlxProjectRepository {
    pool: PgPool,
}

impl SqlxProjectRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub async fn list(&self) -> Result<Vec<Project>, sqlx::Error> {
        let projects = sqlx::query_as!(
            Project,
            r#"SELECT id, jira_project_key, bitbucket_project_key, 
            ci_provider, display_name, description, representative_repo_slug,
            created_at, updated_at FROM project ORDER BY created_at DESC"#
        )
        .fetch_all(&self.pool)
        .await?;
        Ok(projects)
    }

    pub async fn get_by_key(&self, key: &str) -> Result<Option<Project>, sqlx::Error> {
        let project = sqlx::query_as!(
            Project,
            r#"SELECT id, jira_project_key, bitbucket_project_key,
            ci_provider, display_name, description, representative_repo_slug,
            created_at, updated_at FROM project WHERE jira_project_key = $1"#,
            key
        )
        .fetch_optional(&self.pool)
        .await?;
        Ok(project)
    }
}
