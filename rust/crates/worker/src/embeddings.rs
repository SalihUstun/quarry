use std::time::Duration;

use reqwest::StatusCode;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::error::ProcessError;

#[derive(Serialize)]
struct EmbeddingRequest<'a> {
    texts: &'a [String],
}

#[derive(Deserialize)]
struct EmbeddingResponse {
    vectors: Vec<Vec<f32>>,
}

#[derive(Clone)]
pub struct EmbeddingClient {
    http: reqwest::Client,
    url: String,
    internal_token: String,
    batch_size: usize,
}

impl EmbeddingClient {
    pub fn new(
        base_url: &str,
        internal_token: String,
        batch_size: usize,
    ) -> Result<Self, reqwest::Error> {
        Ok(Self {
            http: reqwest::Client::builder()
                .timeout(Duration::from_secs(180))
                .build()?,
            url: format!("{}/internal/embeddings", base_url.trim_end_matches('/')),
            internal_token,
            batch_size: batch_size.max(1),
        })
    }

    pub async fn embed(
        &self,
        tenant_id: Uuid,
        user_id: &str,
        texts: &[String],
    ) -> Result<Vec<Vec<f32>>, ProcessError> {
        let mut vectors = Vec::with_capacity(texts.len());
        for batch in texts.chunks(self.batch_size) {
            vectors.extend(self.embed_batch(tenant_id, user_id, batch).await?);
        }
        if vectors.len() != texts.len() {
            return Err(ProcessError::EmbeddingRejected(format!(
                "expected {} vectors, received {}",
                texts.len(),
                vectors.len()
            )));
        }
        Ok(vectors)
    }

    async fn embed_batch(
        &self,
        tenant_id: Uuid,
        user_id: &str,
        texts: &[String],
    ) -> Result<Vec<Vec<f32>>, ProcessError> {
        let response = self
            .http
            .post(&self.url)
            .header("X-Internal-Token", &self.internal_token)
            .header("X-Tenant-Id", tenant_id.to_string())
            .header("X-User-Id", user_id)
            .json(&EmbeddingRequest { texts })
            .send()
            .await
            .map_err(|error| ProcessError::EmbeddingUnavailable(error.to_string()))?;

        let status = response.status();
        if status.is_success() {
            let body: EmbeddingResponse = response
                .json()
                .await
                .map_err(|error| ProcessError::EmbeddingUnavailable(error.to_string()))?;
            return Ok(body.vectors);
        }

        let detail = response.text().await.unwrap_or_default();
        let message = format!("{status}: {}", truncate(&detail, 200));
        if is_permanent_failure(status) {
            Err(ProcessError::EmbeddingRejected(message))
        } else {
            Err(ProcessError::EmbeddingUnavailable(message))
        }
    }
}

fn is_permanent_failure(status: StatusCode) -> bool {
    status.is_client_error()
        && status != StatusCode::REQUEST_TIMEOUT
        && status != StatusCode::TOO_MANY_REQUESTS
}

fn truncate(text: &str, max_chars: usize) -> &str {
    text.char_indices()
        .nth(max_chars)
        .map_or(text, |(index, _)| &text[..index])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn client_errors_are_permanent_except_timeouts_and_rate_limits() {
        assert!(is_permanent_failure(StatusCode::UNAUTHORIZED));
        assert!(is_permanent_failure(StatusCode::UNPROCESSABLE_ENTITY));
        assert!(!is_permanent_failure(StatusCode::TOO_MANY_REQUESTS));
        assert!(!is_permanent_failure(StatusCode::REQUEST_TIMEOUT));
        assert!(!is_permanent_failure(StatusCode::BAD_GATEWAY));
    }

    #[test]
    fn truncate_respects_character_boundaries() {
        assert_eq!(truncate("şişli", 3), "şiş");
        assert_eq!(truncate("kısa", 10), "kısa");
    }
}
