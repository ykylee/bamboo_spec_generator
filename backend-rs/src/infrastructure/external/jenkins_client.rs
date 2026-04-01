use reqwest::{header, Client, Method, StatusCode};
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};

#[derive(Debug, thiserror::Error)]
pub enum JenkinsError {
    #[error("Jenkins request failed: {0}")]
    Request(#[from] reqwest::Error),
    #[error("Jenkins authentication failed: {0}")]
    AuthFailed(String),
    #[error("Jenkins resource not found: {0}")]
    NotFound(String),
    #[error("Jenkins API request failed: {0}")]
    Api(String),
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JenkinsQueueItem {
    pub number: i64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JenkinsApplyResult {
    pub created: bool,
    pub updated: bool,
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
            base_url: base_url.into().trim_end_matches('/').to_string(),
            username: username.into(),
            auth_token: auth_token.into(),
        }
    }

    pub async fn get_job(&self, job_path: &str, depth: usize) -> Result<Option<Value>, JenkinsError> {
        self.request_json(
            Method::GET,
            &format!("/{}/api/json?depth={}", job_path_url(job_path), depth),
            None,
            None,
            false,
            true,
        )
        .await
    }

    pub async fn get_build(&self, job_path: &str, build_number: &str) -> Result<Option<Value>, JenkinsError> {
        self.request_json(
            Method::GET,
            &format!("/{}/{}/api/json", job_path_url(job_path), build_number),
            None,
            None,
            false,
            true,
        )
        .await
    }

    pub async fn build_job(
        &self,
        job_path: &str,
        parameters: &Map<String, Value>,
    ) -> Result<JenkinsQueueItem, JenkinsError> {
        let endpoint = if parameters.is_empty() {
            format!("/{}/build", job_path_url(job_path))
        } else {
            format!("/{}/buildWithParameters", job_path_url(job_path))
        };
        let form_pairs = parameters
            .iter()
            .map(|(key, value)| {
                let value = if let Some(text) = value.as_str() {
                    text.to_string()
                } else {
                    value.to_string()
                };
                (key.clone(), value)
            })
            .collect::<Vec<_>>();
        let response = self
            .request_raw(
                Method::POST,
                &endpoint,
                if form_pairs.is_empty() {
                    None
                } else {
                    Some(reqwest::Body::from(
                        serde_urlencoded::to_string(&form_pairs)
                            .map_err(|e| JenkinsError::Api(e.to_string()))?,
                    ))
                },
                if form_pairs.is_empty() {
                    None
                } else {
                    Some("application/x-www-form-urlencoded")
                },
                true,
                false,
            )
            .await?;
        let response = response.ok_or_else(|| JenkinsError::Api("Missing Jenkins response".to_string()))?;

        let queue_number = response
            .headers()
            .get(header::LOCATION)
            .and_then(|value| value.to_str().ok())
            .and_then(extract_queue_number)
            .unwrap_or_default();
        Ok(JenkinsQueueItem { number: queue_number })
    }

    pub async fn create_or_update_pipeline_job(
        &self,
        job_path: &str,
        pipeline_script: &str,
        description: &str,
    ) -> Result<JenkinsApplyResult, JenkinsError> {
        let config_xml = pipeline_job_config_xml(pipeline_script, description);
        if self.get_job(job_path, 0).await?.is_none() {
            self.ensure_folders(job_path).await?;
            self.create_job(job_path, &config_xml).await?;
            return Ok(JenkinsApplyResult {
                created: true,
                updated: false,
            });
        }

        self.update_job_config(job_path, &config_xml).await?;
        Ok(JenkinsApplyResult {
            created: false,
            updated: true,
        })
    }

    pub async fn get_computer_list(&self) -> Result<Vec<Value>, JenkinsError> {
        let payload = self
            .request_json(Method::GET, "/computer/api/json?depth=1", None, None, false, false)
            .await?
            .unwrap_or_else(|| json!({}));
        Ok(payload
            .get("computer")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default())
    }

    pub async fn get_queue(&self) -> Result<Vec<Value>, JenkinsError> {
        let payload = self
            .request_json(Method::GET, "/queue/api/json?depth=0", None, None, false, false)
            .await?
            .unwrap_or_else(|| json!({}));
        Ok(payload
            .get("items")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default())
    }

    async fn ensure_folders(&self, job_path: &str) -> Result<(), JenkinsError> {
        let parts = job_path
            .split('/')
            .filter(|part| !part.trim().is_empty())
            .collect::<Vec<_>>();
        let mut current = Vec::new();
        for folder in parts.iter().take(parts.len().saturating_sub(1)) {
            current.push(*folder);
            let folder_path = current.join("/");
            if self.get_job(&folder_path, 0).await?.is_none() {
                self.create_folder(&folder_path).await?;
            }
        }
        Ok(())
    }

    async fn create_folder(&self, folder_path: &str) -> Result<(), JenkinsError> {
        let parts = folder_path
            .split('/')
            .filter(|part| !part.trim().is_empty())
            .collect::<Vec<_>>();
        let folder_name = parts.last().copied().unwrap_or_default();
        let parent = parts[..parts.len().saturating_sub(1)].join("/");
        let endpoint = if parent.is_empty() {
            "/createItem".to_string()
        } else {
            format!("/{}/createItem", job_path_url(&parent))
        };
        let payload = [
            ("name".to_string(), folder_name.to_string()),
            (
                "mode".to_string(),
                "com.cloudbees.hudson.plugins.folder.Folder".to_string(),
            ),
            ("from".to_string(), String::new()),
            (
                "json".to_string(),
                json!({
                    "name": folder_name,
                    "mode": "com.cloudbees.hudson.plugins.folder.Folder",
                    "from": "",
                    "Submit": "OK"
                })
                .to_string(),
            ),
            ("Submit".to_string(), "OK".to_string()),
        ];
        self.request_raw(
            Method::POST,
            &endpoint,
            Some(reqwest::Body::from(
                serde_urlencoded::to_string(payload).map_err(|e| JenkinsError::Api(e.to_string()))?,
            )),
            Some("application/x-www-form-urlencoded"),
            true,
            false,
        )
        .await?;
        Ok(())
    }

    async fn create_job(&self, job_path: &str, config_xml: &str) -> Result<(), JenkinsError> {
        let parts = job_path
            .split('/')
            .filter(|part| !part.trim().is_empty())
            .collect::<Vec<_>>();
        let job_name = parts.last().copied().unwrap_or_default();
        let parent = parts[..parts.len().saturating_sub(1)].join("/");
        let endpoint = if parent.is_empty() {
            format!("/createItem?name={}", urlencoding::encode(job_name))
        } else {
            format!(
                "/{}/createItem?name={}",
                job_path_url(&parent),
                urlencoding::encode(job_name)
            )
        };
        self.request_raw(
            Method::POST,
            &endpoint,
            Some(reqwest::Body::from(config_xml.to_string())),
            Some("application/xml"),
            true,
            false,
        )
        .await?;
        Ok(())
    }

    async fn update_job_config(&self, job_path: &str, config_xml: &str) -> Result<(), JenkinsError> {
        self.request_raw(
            Method::POST,
            &format!("/{}/config.xml", job_path_url(job_path)),
            Some(reqwest::Body::from(config_xml.to_string())),
            Some("application/xml"),
            true,
            false,
        )
        .await?;
        Ok(())
    }

    async fn request_json(
        &self,
        method: Method,
        path: &str,
        body: Option<reqwest::Body>,
        content_type: Option<&str>,
        include_crumb: bool,
        allow_not_found: bool,
    ) -> Result<Option<Value>, JenkinsError> {
        let response = self
            .request_raw(method, path, body, content_type, include_crumb, allow_not_found)
            .await?;
        let Some(response) = response else {
            return Ok(None);
        };
        let text = response.text().await?;
        if text.trim().is_empty() {
            return Ok(Some(json!({})));
        }
        serde_json::from_str(&text)
            .map(Some)
            .map_err(|e| JenkinsError::Api(e.to_string()))
    }

    async fn request_raw(
        &self,
        method: Method,
        path: &str,
        body: Option<reqwest::Body>,
        content_type: Option<&str>,
        include_crumb: bool,
        allow_not_found: bool,
    ) -> Result<Option<reqwest::Response>, JenkinsError> {
        let url = format!("{}{}", self.base_url, path);
        let mut request = self
            .client
            .request(method, url)
            .basic_auth(&self.username, Some(&self.auth_token))
            .header(header::ACCEPT, "application/json");
        if let Some(content_type) = content_type {
            request = request.header(header::CONTENT_TYPE, content_type);
        }
        if include_crumb {
            if let Some((field, crumb)) = self.fetch_crumb().await? {
                request = request.header(field, crumb);
            }
        }
        if let Some(body) = body {
            request = request.body(body);
        }

        let response = request.send().await?;
        let status = response.status();
        if allow_not_found && status == StatusCode::NOT_FOUND {
            return Ok(None);
        }
        if status == StatusCode::UNAUTHORIZED || status == StatusCode::FORBIDDEN {
            let body = response.text().await.unwrap_or_default();
            return Err(JenkinsError::AuthFailed(body));
        }
        if status == StatusCode::NOT_FOUND {
            let body = response.text().await.unwrap_or_default();
            return Err(JenkinsError::NotFound(body));
        }
        if !status.is_success() {
            let body = response.text().await.unwrap_or_default();
            return Err(JenkinsError::Api(format!("{} {}", status.as_u16(), body)));
        }
        Ok(Some(response))
    }

    async fn fetch_crumb(&self) -> Result<Option<(String, String)>, JenkinsError> {
        let response = self
            .client
            .get(format!("{}/crumbIssuer/api/json", self.base_url))
            .basic_auth(&self.username, Some(&self.auth_token))
            .header(header::ACCEPT, "application/json")
            .send()
            .await?;
        if response.status() == StatusCode::NOT_FOUND {
            return Ok(None);
        }
        if response.status() == StatusCode::UNAUTHORIZED || response.status() == StatusCode::FORBIDDEN {
            let body = response.text().await.unwrap_or_default();
            return Err(JenkinsError::AuthFailed(body));
        }
        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(JenkinsError::Api(format!("{} {}", status.as_u16(), body)));
        }
        let payload: Value = response.json().await?;
        let field = payload
            .get("crumbRequestField")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim()
            .to_string();
        let crumb = payload
            .get("crumb")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim()
            .to_string();
        if field.is_empty() || crumb.is_empty() {
            Ok(None)
        } else {
            Ok(Some((field, crumb)))
        }
    }
}

fn extract_queue_number(location: &str) -> Option<i64> {
    location
        .trim_end_matches('/')
        .split('/')
        .next_back()
        .and_then(|value| value.parse::<i64>().ok())
}

fn job_path_url(job_path: &str) -> String {
    job_path
        .split('/')
        .filter(|part| !part.trim().is_empty())
        .map(|part| format!("job/{}", urlencoding::encode(part)))
        .collect::<Vec<_>>()
        .join("/")
}

fn pipeline_job_config_xml(pipeline_script: &str, description: &str) -> String {
    format!(
        "<?xml version=\"1.1\" encoding=\"UTF-8\"?>\n<flow-definition plugin=\"workflow-job\">\n  <description>{}</description>\n  <keepDependencies>false</keepDependencies>\n  <properties/>\n  <definition class=\"org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition\" plugin=\"workflow-cps\">\n    <script>{}</script>\n    <sandbox>true</sandbox>\n  </definition>\n  <triggers/>\n  <disabled>false</disabled>\n</flow-definition>\n",
        xml_escape(description),
        xml_escape(pipeline_script)
    )
}

fn xml_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}
