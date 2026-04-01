use actix_web::{http::StatusCode, HttpResponse};

pub const DATABASE_URL_MISSING: &str = "DATABASE_URL is not configured";

pub fn json_error(status: StatusCode, message: impl Into<String>) -> HttpResponse {
    HttpResponse::build(status).json(serde_json::json!({
        "error": message.into()
    }))
}

pub fn service_unavailable_database() -> HttpResponse {
    json_error(StatusCode::SERVICE_UNAVAILABLE, DATABASE_URL_MISSING)
}

pub fn internal_error(message: impl Into<String>) -> HttpResponse {
    json_error(StatusCode::INTERNAL_SERVER_ERROR, message)
}

pub fn not_found(message: impl Into<String>) -> HttpResponse {
    json_error(StatusCode::NOT_FOUND, message)
}

pub fn bad_request(message: impl Into<String>) -> HttpResponse {
    json_error(StatusCode::BAD_REQUEST, message)
}

pub fn not_implemented(message: impl Into<String>) -> HttpResponse {
    json_error(StatusCode::NOT_IMPLEMENTED, message)
}

pub fn map_domain_error(message: &str) -> HttpResponse {
    if is_not_found_message(message) {
        return not_found(message);
    }
    bad_request(message)
}

fn is_not_found_message(message: &str) -> bool {
    let normalized = message.trim().to_lowercase();
    normalized.contains("was not found") || normalized.contains("not found")
}

#[cfg(test)]
mod tests {
    use super::is_not_found_message;

    #[test]
    fn maps_not_found_messages() {
        assert!(is_not_found_message("Build execution 'x' was not found."));
        assert!(is_not_found_message("Jenkins job not found."));
        assert!(!is_not_found_message("Build number is already associated with a different commit."));
    }
}
