use std::sync::LazyLock;

use regex::Regex;
use unicode_normalization::UnicodeNormalization;

const PARAGRAPH_MARKER: char = '\u{2029}';

static CONTROL_CHARACTERS: LazyLock<Regex> =
    LazyLock::new(|| compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"));
static HYPHENATED_LINE_BREAK: LazyLock<Regex> =
    LazyLock::new(|| compile(r"(\w)-\n[ \t]*([a-zçğıöşü])"));
static PARAGRAPH_BREAK: LazyLock<Regex> = LazyLock::new(|| compile(r"\n[ \t]*\n\s*"));
static CONTINUATION_LINE_BREAK: LazyLock<Regex> =
    LazyLock::new(|| compile(r"[ \t]*\n[ \t]*([a-zçğıöşü])"));
static LINE_BREAK: LazyLock<Regex> = LazyLock::new(|| compile(r"[ \t]*\n[ \t]*"));
static HORIZONTAL_WHITESPACE: LazyLock<Regex> = LazyLock::new(|| compile(r"[ \t\u{a0}]+"));

pub(crate) fn compile(pattern: &str) -> Regex {
    Regex::new(pattern).unwrap_or_else(|error| panic!("invalid built-in regex {pattern}: {error}"))
}

#[must_use]
pub fn turkish_lower(text: &str) -> String {
    text.replace('I', "ı").replace('İ', "i").to_lowercase()
}

#[must_use]
pub fn normalize_text(raw: &str) -> String {
    let text: String = raw.nfc().collect();
    let text = text.replace("\r\n", "\n").replace('\r', "\n");
    let text = CONTROL_CHARACTERS.replace_all(&text, "");
    let text = HYPHENATED_LINE_BREAK.replace_all(&text, "${1}${2}");
    let paragraph_marker = PARAGRAPH_MARKER.to_string();
    let text = PARAGRAPH_BREAK.replace_all(&text, paragraph_marker.as_str());
    let text = CONTINUATION_LINE_BREAK.replace_all(&text, " ${1}");
    let text = LINE_BREAK.replace_all(&text, "\n");
    let text = HORIZONTAL_WHITESPACE.replace_all(&text, " ");

    text.split(PARAGRAPH_MARKER)
        .map(str::trim)
        .filter(|paragraph| !paragraph.is_empty())
        .collect::<Vec<_>>()
        .join("\n\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn turkish_lower_applies_dotted_and_dotless_i_rules() {
        assert_eq!(turkish_lower("ISPARTA"), "ısparta");
        assert_eq!(turkish_lower("İSTANBUL"), "istanbul");
        assert_eq!(turkish_lower("Iğdır İli"), "ığdır ili");
        assert_eq!(turkish_lower("ÇĞÖŞÜ"), "çğöşü");
    }

    #[test]
    fn composes_decomposed_characters() {
        assert_eq!(normalize_text("s\u{327}irket"), "şirket");
    }

    #[test]
    fn joins_hyphenated_and_wrapped_lines_but_keeps_row_breaks() {
        let raw = "sözleş-\nmenin süresi\nbir yıl.\n2025801 AFAD\n2025802 MSB";

        assert_eq!(
            normalize_text(raw),
            "sözleşmenin süresi bir yıl.\n2025801 AFAD\n2025802 MSB"
        );
    }

    #[test]
    fn keeps_paragraphs_and_collapses_whitespace() {
        let raw = "Birinci  satır.\r\n\r\n  \nYeni\u{a0}paragraf\x0c burada.";

        assert_eq!(
            normalize_text(raw),
            "Birinci satır.\n\nYeni paragraf burada."
        );
    }
}
