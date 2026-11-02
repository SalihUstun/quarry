use std::path::{Path, PathBuf};
use std::sync::Arc;

use pdfium_render::prelude::Pdfium;
use quarry_text::{Chunk, ChunkingConfig, chunk_pages};
use uuid::Uuid;

use crate::embeddings::EmbeddingClient;
use crate::error::ProcessError;
use crate::extract::extract_pages;
use crate::store::{ClaimedDocument, DocumentStore};

#[derive(Debug, PartialEq, Eq)]
pub enum Outcome {
    Completed { pages: usize, chunks: usize },
    Skipped,
}

pub struct Pipeline {
    store: DocumentStore,
    embeddings: EmbeddingClient,
    pdfium: Arc<Pdfium>,
    uploads_dir: PathBuf,
    chunking: ChunkingConfig,
}

impl Pipeline {
    #[must_use]
    pub fn new(
        store: DocumentStore,
        embeddings: EmbeddingClient,
        pdfium: Arc<Pdfium>,
        uploads_dir: PathBuf,
        chunking: ChunkingConfig,
    ) -> Self {
        Self {
            store,
            embeddings,
            pdfium,
            uploads_dir,
            chunking,
        }
    }

    #[must_use]
    pub fn store(&self) -> &DocumentStore {
        &self.store
    }

    pub async fn process(
        &self,
        document_id: Uuid,
        redelivered: bool,
    ) -> Result<Outcome, ProcessError> {
        let Some(document) = self.store.claim(document_id, redelivered).await? else {
            return Ok(Outcome::Skipped);
        };

        let (page_count, chunks) = self.extract_and_chunk(&document).await?;
        if chunks.is_empty() {
            return Err(ProcessError::NoText);
        }

        let texts: Vec<String> = chunks.iter().map(|chunk| chunk.content.clone()).collect();
        let embeddings = self
            .embeddings
            .embed(document.tenant_id, &document.uploaded_by, &texts)
            .await?;
        self.store
            .complete(&document, page_count, &chunks, embeddings)
            .await?;

        Ok(Outcome::Completed {
            pages: page_count,
            chunks: chunks.len(),
        })
    }

    async fn extract_and_chunk(
        &self,
        document: &ClaimedDocument,
    ) -> Result<(usize, Vec<Chunk>), ProcessError> {
        let path = resolve_upload(&self.uploads_dir, &document.storage_path)?;
        let pdfium = Arc::clone(&self.pdfium);
        let content_type = document.content_type.clone();
        let chunking = self.chunking;

        tokio::task::spawn_blocking(move || {
            let pages = extract_pages(&pdfium, &path, &content_type)?;
            Ok((pages.len(), chunk_pages(&pages, chunking)))
        })
        .await?
    }
}

pub fn resolve_upload(uploads_dir: &Path, storage_path: &str) -> Result<PathBuf, ProcessError> {
    let relative = Path::new(storage_path);
    let escapes = relative.is_absolute()
        || relative
            .components()
            .any(|component| !matches!(component, std::path::Component::Normal(_)));
    if escapes {
        return Err(ProcessError::InvalidStoragePath);
    }
    Ok(uploads_dir.join(relative))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_tenant_relative_upload_paths() {
        let path = resolve_upload(Path::new("/data/uploads"), "tenant-a/doc.pdf")
            .expect("valid relative path");

        assert_eq!(path, PathBuf::from("/data/uploads/tenant-a/doc.pdf"));
    }

    #[test]
    fn rejects_paths_that_escape_the_uploads_directory() {
        for storage_path in ["../etc/passwd", "/etc/passwd", "tenant/../../secret", "./x"] {
            assert!(
                matches!(
                    resolve_upload(Path::new("/data/uploads"), storage_path),
                    Err(ProcessError::InvalidStoragePath)
                ),
                "{storage_path} should be rejected"
            );
        }
    }
}
