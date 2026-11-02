use pgvector::Vector;
use quarry_text::Chunk;
use sqlx::{FromRow, PgPool};
use uuid::Uuid;

use crate::error::ProcessError;

#[derive(Debug, Clone, FromRow)]
pub struct ClaimedDocument {
    pub id: Uuid,
    pub tenant_id: Uuid,
    pub content_type: String,
    pub storage_path: String,
    pub uploaded_by: String,
}

#[derive(Clone)]
pub struct DocumentStore {
    pool: PgPool,
}

impl DocumentStore {
    #[must_use]
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub async fn claim(
        &self,
        document_id: Uuid,
        redelivered: bool,
    ) -> Result<Option<ClaimedDocument>, ProcessError> {
        let document = sqlx::query_as::<_, ClaimedDocument>(
            "UPDATE documents
             SET status = 'processing', error = NULL, updated_at = now()
             WHERE id = $1
               AND (status IN ('pending', 'failed') OR ($2 AND status = 'processing'))
             RETURNING id, tenant_id, content_type, storage_path, uploaded_by",
        )
        .bind(document_id)
        .bind(redelivered)
        .fetch_optional(&self.pool)
        .await?;
        Ok(document)
    }

    pub async fn complete(
        &self,
        document: &ClaimedDocument,
        page_count: usize,
        chunks: &[Chunk],
        embeddings: Vec<Vec<f32>>,
    ) -> Result<(), ProcessError> {
        let mut transaction = self.pool.begin().await?;
        sqlx::query("DELETE FROM chunks WHERE document_id = $1")
            .bind(document.id)
            .execute(&mut *transaction)
            .await?;

        for (chunk, embedding) in chunks.iter().zip(embeddings) {
            sqlx::query(
                "INSERT INTO chunks
                    (tenant_id, document_id, chunk_index, page_number, content, char_count, embedding)
                 VALUES ($1, $2, $3, $4, $5, $6, $7)",
            )
            .bind(document.tenant_id)
            .bind(document.id)
            .bind(to_i32(chunk.index))
            .bind(i32::try_from(chunk.page_number).unwrap_or(i32::MAX))
            .bind(&chunk.content)
            .bind(to_i32(chunk.char_count()))
            .bind(Vector::from(embedding))
            .execute(&mut *transaction)
            .await?;
        }

        sqlx::query(
            "UPDATE documents
             SET status = 'ready', page_count = $2, error = NULL, updated_at = now()
             WHERE id = $1",
        )
        .bind(document.id)
        .bind(to_i32(page_count))
        .execute(&mut *transaction)
        .await?;

        transaction.commit().await?;
        Ok(())
    }

    pub async fn schedule_retry(&self, document_id: Uuid, error: &str) -> Result<(), ProcessError> {
        self.set_status(document_id, "pending", error).await
    }

    pub async fn mark_failed(&self, document_id: Uuid, error: &str) -> Result<(), ProcessError> {
        self.set_status(document_id, "failed", error).await
    }

    async fn set_status(
        &self,
        document_id: Uuid,
        status: &str,
        error: &str,
    ) -> Result<(), ProcessError> {
        sqlx::query(
            "UPDATE documents SET status = $2, error = $3, updated_at = now() WHERE id = $1",
        )
        .bind(document_id)
        .bind(status)
        .bind(error.chars().take(1000).collect::<String>())
        .execute(&self.pool)
        .await?;
        Ok(())
    }
}

fn to_i32(value: usize) -> i32 {
    i32::try_from(value).unwrap_or(i32::MAX)
}
