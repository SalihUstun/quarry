use std::fmt;

use crate::normalize::normalize_text;
use crate::sentences::split_sentences;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PageText {
    pub page_number: u32,
    pub text: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Chunk {
    pub index: usize,
    pub page_number: u32,
    pub content: String,
}

impl Chunk {
    #[must_use]
    pub fn char_count(&self) -> usize {
        self.content.chars().count()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ChunkingConfig {
    max_chars: usize,
    overlap_chars: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChunkingConfigError {
    ZeroMaxChars,
    OverlapNotSmallerThanMax,
}

impl fmt::Display for ChunkingConfigError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::ZeroMaxChars => formatter.write_str("max_chars must be positive"),
            Self::OverlapNotSmallerThanMax => {
                formatter.write_str("overlap_chars must be smaller than max_chars")
            }
        }
    }
}

impl std::error::Error for ChunkingConfigError {}

impl ChunkingConfig {
    pub fn new(max_chars: usize, overlap_chars: usize) -> Result<Self, ChunkingConfigError> {
        if max_chars == 0 {
            return Err(ChunkingConfigError::ZeroMaxChars);
        }
        if overlap_chars >= max_chars {
            return Err(ChunkingConfigError::OverlapNotSmallerThanMax);
        }
        Ok(Self {
            max_chars,
            overlap_chars,
        })
    }

    #[must_use]
    pub fn max_chars(&self) -> usize {
        self.max_chars
    }

    #[must_use]
    pub fn overlap_chars(&self) -> usize {
        self.overlap_chars
    }
}

impl Default for ChunkingConfig {
    fn default() -> Self {
        Self {
            max_chars: 1200,
            overlap_chars: 200,
        }
    }
}

#[must_use]
pub fn chunk_pages(pages: &[PageText], config: ChunkingConfig) -> Vec<Chunk> {
    let mut chunks = Vec::new();
    for page in pages {
        let normalized = normalize_text(&page.text);
        let sentences = fit_sentences(split_sentences(&normalized), config.max_chars);
        for content in pack(&sentences, config) {
            chunks.push(Chunk {
                index: chunks.len(),
                page_number: page.page_number,
                content,
            });
        }
    }
    chunks
}

fn char_len(text: &str) -> usize {
    text.chars().count()
}

fn fit_sentences(sentences: Vec<&str>, max_chars: usize) -> Vec<String> {
    let mut fitted = Vec::with_capacity(sentences.len());
    for sentence in sentences {
        if char_len(sentence) <= max_chars {
            fitted.push(sentence.to_owned());
        } else {
            fitted.extend(split_long_sentence(sentence, max_chars));
        }
    }
    fitted
}

fn split_long_sentence(sentence: &str, max_chars: usize) -> Vec<String> {
    let mut pieces = Vec::new();
    let mut current = String::new();
    let mut current_len = 0;
    for word in sentence.split_whitespace() {
        for part in hard_wrap(word, max_chars) {
            let part_len = char_len(part);
            let candidate_len = if current.is_empty() {
                part_len
            } else {
                current_len + 1 + part_len
            };
            if candidate_len <= max_chars {
                if !current.is_empty() {
                    current.push(' ');
                }
                current.push_str(part);
                current_len = candidate_len;
            } else {
                pieces.push(std::mem::take(&mut current));
                current.push_str(part);
                current_len = part_len;
            }
        }
    }
    if !current.is_empty() {
        pieces.push(current);
    }
    pieces
}

fn hard_wrap(word: &str, max_chars: usize) -> Vec<&str> {
    let boundaries: Vec<usize> = word
        .char_indices()
        .map(|(index, _)| index)
        .step_by(max_chars)
        .chain(std::iter::once(word.len()))
        .collect();
    boundaries
        .windows(2)
        .map(|window| &word[window[0]..window[1]])
        .collect()
}

fn pack(sentences: &[String], config: ChunkingConfig) -> Vec<String> {
    let mut packed = Vec::new();
    let mut current: Vec<&str> = Vec::new();
    let mut length = 0;
    for sentence in sentences {
        let sentence_len = char_len(sentence);
        if !current.is_empty() && length + 1 + sentence_len > config.max_chars {
            packed.push(current.join("\n"));
            current = overlap_tail(&current, config.overlap_chars);
            length = joined_length(&current);
            if !current.is_empty() && length + 1 + sentence_len > config.max_chars {
                current.clear();
                length = 0;
            }
        }
        length += sentence_len + usize::from(!current.is_empty());
        current.push(sentence);
    }
    if !current.is_empty() {
        packed.push(current.join("\n"));
    }
    packed
}

fn overlap_tail<'a>(sentences: &[&'a str], overlap_chars: usize) -> Vec<&'a str> {
    let mut tail = Vec::new();
    let mut length = 0;
    for sentence in sentences.iter().rev() {
        let added = char_len(sentence) + usize::from(!tail.is_empty());
        if length + added > overlap_chars {
            break;
        }
        tail.push(*sentence);
        length += added;
    }
    tail.reverse();
    tail
}

fn joined_length(sentences: &[&str]) -> usize {
    sentences
        .iter()
        .map(|sentence| char_len(sentence))
        .sum::<usize>()
        + sentences.len().saturating_sub(1)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn page(number: u32, text: &str) -> PageText {
        PageText {
            page_number: number,
            text: text.to_owned(),
        }
    }

    #[test]
    fn short_page_becomes_single_chunk() {
        let chunks = chunk_pages(
            &[page(1, "Kısa bir metin. İkinci cümle.")],
            ChunkingConfig::default(),
        );

        assert_eq!(
            chunks,
            [Chunk {
                index: 0,
                page_number: 1,
                content: "Kısa bir metin.\nİkinci cümle.".to_owned()
            }]
        );
    }

    #[test]
    fn chunks_never_exceed_max_chars_counted_in_characters() {
        let config = ChunkingConfig::new(60, 20).expect("valid config");
        let text = "Çalışan ğüşıöç İzin süresi şöyle belirlenir. ".repeat(20);

        let chunks = chunk_pages(&[page(1, &text)], config);

        assert!(chunks.len() > 1);
        assert!(chunks.iter().all(|chunk| chunk.char_count() <= 60));
    }

    #[test]
    fn hard_wraps_multibyte_words_on_character_boundaries() {
        assert_eq!(hard_wrap("ğğğğğ", 2), ["ğğ", "ğğ", "ğ"]);
    }

    #[test]
    fn rejects_invalid_config() {
        assert_eq!(
            ChunkingConfig::new(0, 0),
            Err(ChunkingConfigError::ZeroMaxChars)
        );
        assert_eq!(
            ChunkingConfig::new(100, 100),
            Err(ChunkingConfigError::OverlapNotSmallerThanMax)
        );
    }
}
