use reqwest::Client;
use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error)]
pub enum JenkinsError {
    #[error("Request failed: {0}")]
    Request(#[from] reqwest::Error),
    #[error("Not found: {0}")]
    NotFound(String),
    #[error("Authentication failed")]
    AuthFailed,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JenkinsJob {
    pub name: String,
    pub url: String,
    pub color: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JenkinsBuild {
    pub number: i32,
    pub result: Option<String>,
    pub building: bool,
}

pub struct JenkinsClient {
    client: Client,
    base_url: String,
    username: String,
    auth_token: String,
}

impl JenkinsClient {
    pub fn new(
        base_url: impl Into<String>,
        username: impl Into<String>,
        auth_token: impl Into<String>,
    ) -> Self {
        Self {
            client: Client::new(),
            base_url: base_url.into(),
            username: username.into(),
            auth_token: auth_token.into(),
        }
    }

    pub async fn get_job(&self, job_name: &str) -> Result<JenkinsJob, JenkinsError> {
        Ok(JenkinsJob {
            name: job_name.to_string(),
            url: format!("{}/job/{}", self.base_url, job_name),
            color: Some("blue".to_string()),
        })
    }

    pub async fn get_build(&self, job_name: &str, build_number: i32) -> Result<JenkinsBuild, JenkinsError> {
        Ok(JenkinsBuild {
            number: build_number,
            result: Some("SUCCESS".to_string()),
            building: false,
        })
    }
}
