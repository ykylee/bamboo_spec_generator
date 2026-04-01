use std::collections::BTreeMap;

use reqwest::{header, Client, Method, StatusCode};
use serde_json::Value;

#[derive(Debug, thiserror::Error)]
pub enum BambooError {
    #[error("Bamboo request failed: {0}")]
    Request(#[from] reqwest::Error),
    #[error("Bamboo authentication failed: {0}")]
    AuthFailed(String),
    #[error("Bamboo resource not found: {0}")]
    NotFound(String),
    #[error("Bamboo API request failed: {0}")]
    Api(String),
}

pub struct BambooClient {
    client: Client,
    base_url: String,
    auth_token: String,
}

impl BambooClient {
    pub fn new(base_url: impl Into<String>, auth_token: impl Into<String>) -> Self {
        Self {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(15))
                .build()
                .unwrap_or_else(|_| Client::new()),
            base_url: base_url.into().trim_end_matches('/').to_string(),
            auth_token: auth_token.into(),
        }
    }

    pub async fn get_plan(
        &self,
        project_key: &str,
        plan_key: &str,
        expand: Option<&str>,
    ) -> Result<Option<Value>, BambooError> {
        let mut endpoint = format!(
            "/rest/api/latest/plan/{}/{}",
            urlencoding::encode(project_key),
            urlencoding::encode(plan_key)
        );
        if let Some(expand) = expand.filter(|value| !value.trim().is_empty()) {
            endpoint.push_str("?expand=");
            endpoint.push_str(&urlencoding::encode(expand));
        }
        self.request_json(Method::GET, &endpoint, true).await
    }

    pub async fn get_latest_result(&self, full_plan_key: &str) -> Result<Value, BambooError> {
        Ok(self
            .request_json(
                Method::GET,
                &format!(
                    "/rest/api/latest/result/{}?max-result=1",
                    urlencoding::encode(full_plan_key)
                ),
                false,
            )
            .await?
            .unwrap_or(Value::Object(Default::default())))
    }

    pub async fn queue_plan(
        &self,
        full_plan_key: &str,
        stage: &str,
        execute_all_stages: bool,
        custom_revision: &str,
        variables: &BTreeMap<String, String>,
    ) -> Result<Value, BambooError> {
        let mut pairs = Vec::new();
        if !stage.trim().is_empty() {
            pairs.push(("stage".to_string(), stage.trim().to_string()));
        }
        if execute_all_stages {
            pairs.push(("executeAllStages".to_string(), "true".to_string()));
        }
        if !custom_revision.trim().is_empty() {
            pairs.push(("customRevision".to_string(), custom_revision.trim().to_string()));
        }
        for (key, value) in variables {
            if key.trim().is_empty() {
                continue;
            }
            pairs.push((key.trim().to_string(), value.clone()));
        }
        let query = if pairs.is_empty() {
            String::new()
        } else {
            format!(
                "?{}",
                serde_urlencoded::to_string(&pairs).map_err(|error| BambooError::Api(error.to_string()))?
            )
        };
        Ok(self
            .request_json(
                Method::POST,
                &format!(
                    "/rest/api/latest/queue/{}{}",
                    urlencoding::encode(full_plan_key),
                    query
                ),
                false,
            )
            .await?
            .unwrap_or(Value::Object(Default::default())))
    }

    async fn request_json(
        &self,
        method: Method,
        path: &str,
        allow_not_found: bool,
    ) -> Result<Option<Value>, BambooError> {
        let url = format!("{}{}", self.base_url, path);
        let mut request = self
            .client
            .request(method, url)
            .header(header::ACCEPT, "application/json");
        if !self.auth_token.trim().is_empty() {
            request = request.bearer_auth(self.auth_token.trim());
        }
        let response = request.send().await?;
        let status = response.status();
        if status == StatusCode::NOT_FOUND && allow_not_found {
            return Ok(None);
        }
        if status == StatusCode::UNAUTHORIZED || status == StatusCode::FORBIDDEN {
            let payload = response.text().await.unwrap_or_default();
            return Err(BambooError::AuthFailed(payload));
        }
        if !status.is_success() {
            let payload = response.text().await.unwrap_or_default();
            return Err(BambooError::Api(format!("{} {}", status, payload).trim().to_string()));
        }
        let body = response.text().await?;
        if body.trim().is_empty() {
            return Ok(Some(Value::Object(Default::default())));
        }
        let payload =
            serde_json::from_str::<Value>(&body).map_err(|error| BambooError::Api(error.to_string()))?;
        Ok(Some(payload))
    }
}
