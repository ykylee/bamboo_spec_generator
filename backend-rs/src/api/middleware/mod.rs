use actix_web::{
    dev::ServiceRequest,
    error::{ErrorInternalServerError, ErrorUnauthorized},
    Error, HttpMessage,
};
use actix_web_httpauth::extractors::bearer::BearerAuth;

pub async fn auth_middleware(
    req: ServiceRequest,
    credentials: BearerAuth,
) -> Result<ServiceRequest, (Error, ServiceRequest)> {
    let expected = std::env::var("BAMBOO_API_TOKEN").unwrap_or_default();
    if expected.trim().is_empty() {
        return Err((ErrorInternalServerError("BAMBOO_API_TOKEN is not configured."), req));
    }
    if credentials.token() != expected {
        return Err((ErrorUnauthorized("Invalid API token."), req));
    }
    req.extensions_mut().insert(credentials.token().to_string());
    Ok(req)
}
