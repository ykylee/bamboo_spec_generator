pub mod api;
pub mod domain;
pub mod infrastructure;
pub mod workers;

#[derive(Clone)]
pub struct AppState {
    pub pool: Option<sqlx::PgPool>,
}
