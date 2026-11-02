use std::fmt::Write as _;
use std::time::Instant;

use quarry_text::{Chunk, ChunkingConfig, PageText, chunk_pages};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Deserialize)]
struct CorpusPage {
    page_number: u32,
    text: String,
}

#[derive(Deserialize)]
struct Corpus {
    max_chars: usize,
    overlap_chars: usize,
    pages: Vec<CorpusPage>,
}

#[derive(Serialize)]
struct Report {
    implementation: &'static str,
    seconds: f64,
    chunks: usize,
    checksum: String,
}

fn checksum(chunks: &[Chunk]) -> String {
    let mut hasher = Sha256::new();
    for chunk in chunks {
        hasher.update(chunk.page_number.to_string().as_bytes());
        hasher.update(b"\x1f");
        hasher.update(chunk.content.as_bytes());
        hasher.update(b"\x1e");
    }
    hasher
        .finalize()
        .iter()
        .fold(String::with_capacity(64), |mut hex, byte| {
            let _ = write!(hex, "{byte:02x}");
            hex
        })
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args()
        .nth(1)
        .ok_or("usage: quarry-bench <corpus.json>")?;
    let corpus: Corpus = serde_json::from_str(&std::fs::read_to_string(path)?)?;
    let config = ChunkingConfig::new(corpus.max_chars, corpus.overlap_chars)?;
    let pages: Vec<PageText> = corpus
        .pages
        .into_iter()
        .map(|page| PageText {
            page_number: page.page_number,
            text: page.text,
        })
        .collect();

    let started = Instant::now();
    let chunks = chunk_pages(&pages, config);
    let seconds = started.elapsed().as_secs_f64();

    let report = Report {
        implementation: "rust",
        seconds,
        chunks: chunks.len(),
        checksum: checksum(&chunks),
    };
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
