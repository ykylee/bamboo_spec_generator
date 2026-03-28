use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct ProjectListQuery {
    #[serde(default)]
    pub ci_provider: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ProjectCreateIn {
    pub jira_project_key: String,
    pub bitbucket_project_key: String,
    #[serde(default = "default_ci_provider")]
    pub ci_provider: String,
    pub display_name: String,
    pub description: Option<String>,
}

fn default_ci_provider() -> String {
    "bamboo".to_string()
}

#[derive(Debug, Deserialize)]
pub struct ProjectUpdateIn {
    pub display_name: Option<String>,
    pub description: Option<String>,
    pub representative_repo_slug: Option<String>,
}
