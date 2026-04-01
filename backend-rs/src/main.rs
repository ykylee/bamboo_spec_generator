use actix_cors::Cors;
use actix_web::{middleware, web, App, HttpServer};
use actix_web::http::header;
use actix_web_httpauth::middleware::HttpAuthentication;
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Starting bamboo-spec-generator backend");

    let host = std::env::var("SERVER_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("SERVER_PORT")
        .unwrap_or_else(|_| "8080".to_string())
        .parse()
        .expect("Invalid SERVER_PORT");

    info!("Server starting at {}:{}", host, port);

    let pool = match bamboo_backend::infrastructure::database::create_pool_from_env().await {
        Ok(pool) => {
            info!("Connected to PostgreSQL");
            Some(pool)
        }
        Err(error) => {
            info!("PostgreSQL pool not initialized: {}", error);
            None
        }
    };
    let state = bamboo_backend::AppState { pool };

    HttpServer::new(move || {
        let cors = Cors::default()
            .allow_any_origin()
            .allowed_methods(vec!["GET", "POST", "PUT", "OPTIONS"])
            .allowed_headers(vec![
                header::AUTHORIZATION,
                header::ACCEPT,
                header::CONTENT_TYPE,
            ])
            .max_age(3600);

        App::new()
            .app_data(web::Data::new(state.clone()))
            .wrap(cors)
            .wrap(middleware::Logger::default())
            .service(
                web::scope("/api/v1")
                    .wrap(HttpAuthentication::bearer(
                        bamboo_backend::api::middleware::auth_middleware,
                    ))
                    .configure(bamboo_backend::api::routes::projects::configure)
                    .configure(bamboo_backend::api::routes::build_plans::configure)
                    .configure(bamboo_backend::api::routes::executions::configure)
                    .configure(bamboo_backend::api::routes::modules::configure)
                    .configure(bamboo_backend::api::routes::settings::configure)
                    .configure(bamboo_backend::api::routes::jenkins_jobs::configure)
            )
            .route("/", web::get().to(|| async { "bamboo-spec-generator API v1" }))
    })
    .bind((host, port))?
    .run()
    .await
}
