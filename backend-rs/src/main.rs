use actix_web::{web, App, HttpServer, middleware};
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

    HttpServer::new(|| {
        App::new()
            .wrap(middleware::Logger::default())
            .service(
                web::scope("/api/v1")
                    .configure(bamboo_backend::api::routes::projects::configure)
                    .configure(bamboo_backend::api::routes::build_plans::configure)
                    .configure(bamboo_backend::api::routes::modules::configure)
                    .configure(bamboo_backend::api::routes::settings::configure)
            )
            .route("/", web::get().to(|| async { "bamboo-spec-generator API v1" }))
    })
    .bind((host, port))?
    .run()
    .await
}
