use sqlx::postgres::{PgPool, PgPoolOptions};
use std::time::Duration;

pub async fn create_pool(database_url: &str) -> Result<PgPool, sqlx::Error> {
    PgPoolOptions::new()
        .max_connections(5)
        .acquire_timeout(Duration::from_secs(3))
        .connect(database_url)
        .await
}

pub async fn create_pool_from_env() -> anyhow::Result<PgPool> {
    let database_url = std::env::var("DATABASE_URL")?;
    Ok(create_pool(&database_url).await?)
}
