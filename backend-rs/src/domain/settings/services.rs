use crate::domain::settings::entities::SystemSetting;

pub async fn list_settings() -> Result<Vec<SystemSetting>, String> {
    Ok(vec![
        SystemSetting {
            id: uuid::Uuid::new_v4(),
            key: "bamboo.server.url".to_string(),
            value: Some("http://localhost:8085".to_string()),
            description: Some("Bamboo server URL".to_string()),
            created_at: chrono::Utc::now(),
            updated_at: chrono::Utc::now(),
        },
    ])
}

pub async fn get_setting(_key: &str) -> Result<Option<SystemSetting>, String> {
    Ok(None)
}

pub async fn update_setting(_key: &str, _value: &str) -> Result<SystemSetting, String> {
    Err("Not implemented".to_string())
}
