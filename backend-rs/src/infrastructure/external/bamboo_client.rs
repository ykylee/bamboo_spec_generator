use reqwest::Client;
use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error)]
pub enum BambooError {
    #[error("Request failed: {0}")]
    Request(#[from] reqwest::Error),
    #[error("Not found: {0}")]
    NotFound(String),
    #[error("Authentication failed")]
    AuthFailed,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct BambooPlan {
    pub key: String,
    pub name: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct BambooBuild {
    pub number: i32,
    pub state: String,
    pub build_state: String,
}

pub struct BambooClient {
    client: Client,
    base_url: String,
    auth_token: String,
}

impl BambooClient {
    pub fn new(base_url: impl Into<String>, auth_token: impl Into<String>) -> Self {
        Self {
            client: Client::new(),
            base_url: base_url.into(),
            auth_token: auth_token.into(),
        }
    }

    pub async fn get_plan(&self, plan_key: &str) -> Result<BambooPlan, BambooError> {
        Ok(BambooPlan {
            key: plan_key.to_string(),
            name: plan_key.to_string(),
        })
    }

    pub async fn get_build(&self, plan_key: &str, build_number: i32) -> Result<BambooBuild, BambooError> {
        Ok(BambooBuild {
            number: build_number,
            state: "success".to_string(),
            build_state: "Built".to_string(),
        })
    }
}
