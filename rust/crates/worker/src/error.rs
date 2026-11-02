#[derive(Debug, thiserror::Error)]
pub enum ProcessError {
    #[error("unsupported content type: {0}")]
    UnsupportedContentType(String),
    #[error("document could not be read: {0}")]
    Extraction(String),
    #[error("document contains no extractable text")]
    NoText,
    #[error("storage path escapes the uploads directory")]
    InvalidStoragePath,
    #[error("embedding service is unavailable: {0}")]
    EmbeddingUnavailable(String),
    #[error("embedding service rejected the request: {0}")]
    EmbeddingRejected(String),
    #[error("database error: {0}")]
    Database(#[from] sqlx::Error),
    #[error("extraction task failed: {0}")]
    Task(#[from] tokio::task::JoinError),
}

impl ProcessError {
    #[must_use]
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            Self::EmbeddingUnavailable(_) | Self::Database(_) | Self::Task(_)
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_infrastructure_failures_are_retryable() {
        assert!(ProcessError::EmbeddingUnavailable("busy".into()).is_retryable());
        assert!(ProcessError::Database(sqlx::Error::PoolTimedOut).is_retryable());
        assert!(!ProcessError::EmbeddingRejected("401".into()).is_retryable());
        assert!(!ProcessError::Extraction("corrupt".into()).is_retryable());
        assert!(!ProcessError::NoText.is_retryable());
        assert!(!ProcessError::UnsupportedContentType("image/png".into()).is_retryable());
    }
}
