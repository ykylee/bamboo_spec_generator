use actix_web::{dev::ServiceRequest, Error, HttpMessage};
use actix_web::error::ErrorUnauthorized;

pub async fn auth_middleware(
    req: ServiceRequest,
    _credentials: actix_web_httpauth::extractors::bearer::BearerAuth,
) -> Result<ServiceRequest, (Error, ServiceRequest)> {
    req.extensions_mut().insert("authenticated".to_string());
    Ok(req)
}
