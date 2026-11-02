use std::env;
use std::path::PathBuf;
use std::str::FromStr;
use std::time::Duration;

use anyhow::{Context, Result};
use quarry_text::ChunkingConfig;

#[derive(Debug, Clone)]
pub struct Config {
    pub amqp_url: String,
    pub database_url: String,
    pub ai_base_url: String,
    pub internal_token: String,
    pub uploads_dir: PathBuf,
    pub pdfium_library_dir: PathBuf,
    pub concurrency: u16,
    pub max_attempts: u32,
    pub retry_delay: Duration,
    pub embedding_batch_size: usize,
    pub chunking: ChunkingConfig,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        let chunking = ChunkingConfig::new(
            parsed("CHUNK_MAX_CHARS", 1200)?,
            parsed("CHUNK_OVERLAP_CHARS", 200)?,
        )?;
        Ok(Self {
            amqp_url: required("AMQP_URL")?,
            database_url: required("DATABASE_URL")?,
            ai_base_url: required("AI_BASE_URL")?,
            internal_token: required("INTERNAL_TOKEN")?,
            uploads_dir: PathBuf::from(optional("UPLOADS_DIR", "/data/uploads")),
            pdfium_library_dir: PathBuf::from(optional("PDFIUM_LIBRARY_DIR", "/opt/pdfium/lib")),
            concurrency: parsed("WORKER_CONCURRENCY", 4)?,
            max_attempts: parsed("WORKER_MAX_ATTEMPTS", 5)?,
            retry_delay: Duration::from_millis(parsed("WORKER_RETRY_DELAY_MS", 30_000)?),
            embedding_batch_size: parsed("EMBEDDING_BATCH_SIZE", 32)?,
            chunking,
        })
    }
}

fn required(name: &str) -> Result<String> {
    env::var(name).with_context(|| format!("environment variable {name} is required"))
}

fn optional(name: &str, default: &str) -> String {
    env::var(name).unwrap_or_else(|_| default.to_owned())
}

fn parsed<T>(name: &str, default: T) -> Result<T>
where
    T: FromStr,
    T::Err: std::error::Error + Send + Sync + 'static,
{
    match env::var(name) {
        Ok(value) => value
            .parse()
            .with_context(|| format!("environment variable {name} has an invalid value")),
        Err(_) => Ok(default),
    }
}
