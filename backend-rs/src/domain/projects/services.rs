use crate::domain::projects::entities::Project;

pub trait ProjectRepositoryTrait: Send + Sync {
    fn list(&self) -> impl Future<Output = Result<Vec<Project>, Box<dyn std::error::Error>>> + Send;
    fn get_by_key(&self, key: &str) -> impl Future<Output = Result<Option<Project>, Box<dyn std::error::Error>>> + Send;
    fn create(&self, project: Project) -> impl Future<Output = Result<Project, Box<dyn std::error::Error>>> + Send;
    fn update(&self, key: &str, project: Project) -> impl Future<Output = Result<Project, Box<dyn std::error::Error>>> + Send;
}

use std::future::Future;

pub struct ProjectService<R: ProjectRepositoryTrait> {
    repository: R,
}

impl<R: ProjectRepositoryTrait> ProjectService<R> {
    pub fn new(repository: R) -> Self {
        Self { repository }
    }

    pub async fn list_projects(&self, _ci_provider: Option<String>) -> Result<Vec<Project>, String> {
        self.repository.list()
            .await
            .map_err(|e| e.to_string())
    }

    pub async fn get_project(&self, key: &str) -> Result<Option<Project>, String> {
        self.repository.get_by_key(key)
            .await
            .map_err(|e| e.to_string())
    }
}
