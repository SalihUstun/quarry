use std::path::PathBuf;

use quarry_text::{ChunkingConfig, PageText, chunk_pages};
use serde::Deserialize;

#[derive(Deserialize)]
struct FixturePage {
    page_number: u32,
    text: String,
}

#[derive(Deserialize)]
struct FixtureChunk {
    index: usize,
    page_number: u32,
    content: String,
}

#[derive(Deserialize)]
struct FixtureCase {
    name: String,
    max_chars: usize,
    overlap_chars: usize,
    pages: Vec<FixturePage>,
    expected: Vec<FixtureChunk>,
}

fn load_cases() -> Vec<FixtureCase> {
    let path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../fixtures/chunking/cases.json");
    let json = std::fs::read_to_string(&path).expect("fixture file is readable");
    serde_json::from_str(&json).expect("fixture file is valid JSON")
}

#[test]
fn rust_chunker_matches_python_reference_for_every_fixture() {
    let cases = load_cases();
    assert!(!cases.is_empty());

    for case in cases {
        let pages: Vec<PageText> = case
            .pages
            .into_iter()
            .map(|page| PageText {
                page_number: page.page_number,
                text: page.text,
            })
            .collect();
        let config = ChunkingConfig::new(case.max_chars, case.overlap_chars).expect("valid config");

        let actual = chunk_pages(&pages, config);

        assert_eq!(
            actual.len(),
            case.expected.len(),
            "chunk count differs in {}",
            case.name
        );
        for (actual, expected) in actual.iter().zip(&case.expected) {
            assert_eq!(
                actual.index, expected.index,
                "index differs in {}",
                case.name
            );
            assert_eq!(
                actual.page_number, expected.page_number,
                "page differs in {}",
                case.name
            );
            assert_eq!(
                actual.content, expected.content,
                "content differs in {}",
                case.name
            );
        }
    }
}
