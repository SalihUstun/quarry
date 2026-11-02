mod config;
mod embeddings;
mod error;
mod extract;
mod pipeline;
mod queue;
mod store;

use std::sync::Arc;

use anyhow::{Context, Result};
use pdfium_render::prelude::Pdfium;
use sqlx::postgres::PgPoolOptions;
use tracing_subscriber::EnvFilter;

use crate::config::Config;
use crate::embeddings::EmbeddingClient;
use crate::pipeline::Pipeline;
use crate::store::DocumentStore;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .json()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    let config = Config::from_env()?;

    let bindings = Pdfium::bind_to_library(Pdfium::pdfium_platform_library_name_at_path(
        &config.pdfium_library_dir,
    ))
    .context("could not load the PDFium library")?;
    let pdfium = Arc::new(Pdfium::new(bindings));

    let pool = PgPoolOptions::new()
        .max_connections(u32::from(config.concurrency) + 2)
        .connect(&config.database_url)
        .await
        .context("could not connect to PostgreSQL")?;

    let embeddings = EmbeddingClient::new(
        &config.ai_base_url,
        config.internal_token.clone(),
        config.embedding_batch_size,
    )?;

    let pipeline = Arc::new(Pipeline::new(
        DocumentStore::new(pool),
        embeddings,
        pdfium,
        config.uploads_dir.clone(),
        config.chunking,
    ));

    queue::run(&config, pipeline).await
}
