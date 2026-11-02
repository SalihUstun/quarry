use std::sync::LazyLock;

use regex::Regex;

use crate::normalize::{compile, turkish_lower};

const ABBREVIATIONS: &[&str] = &[
    "a", "apt", "av", "bkz", "bşk", "cad", "çev", "dr", "doç", "ed", "gn", "hz", "ins", "kr",
    "ltd", "mad", "mah", "md", "müh", "no", "nr", "öğr", "örn", "prof", "s", "sn", "sok", "şti",
    "tel", "uzm", "vb", "vd", "vs", "yy", "yrd",
];

static SENTENCE_BOUNDARY: LazyLock<Regex> =
    LazyLock::new(|| compile(r#"[.!?…]+["'”’)\]]*\s+|\n+"#));
static DOTTED_ABBREVIATION: LazyLock<Regex> = LazyLock::new(|| compile(r"^(?:\w\.)+\w?$"));

#[must_use]
pub fn split_sentences(text: &str) -> Vec<&str> {
    let mut sentences = Vec::new();
    let mut start = 0;
    for boundary in SENTENCE_BOUNDARY.find_iter(text) {
        if is_sentence_end(text, boundary.start(), boundary.end()) {
            push_trimmed(&mut sentences, &text[start..boundary.end()]);
            start = boundary.end();
        }
    }
    push_trimmed(&mut sentences, &text[start..]);
    sentences
}

fn is_sentence_end(text: &str, punctuation_start: usize, boundary_end: usize) -> bool {
    let punctuation = text[punctuation_start..].chars().next();
    if punctuation == Some('\n') {
        return true;
    }
    if text[boundary_end..]
        .chars()
        .next()
        .is_some_and(char::is_lowercase)
    {
        return false;
    }
    if punctuation != Some('.') {
        return true;
    }
    !is_abbreviation(last_token(text, punctuation_start))
}

fn last_token(text: &str, end: usize) -> &str {
    let start = text[..end]
        .char_indices()
        .rev()
        .find(|(_, character)| character.is_whitespace())
        .map_or(0, |(index, character)| index + character.len_utf8());
    &text[start..end]
}

fn is_abbreviation(token: &str) -> bool {
    let stripped = token.trim_start_matches(['(', '"', '\'', '“', '‘']);
    let mut characters = stripped.chars();
    match (characters.next(), characters.next()) {
        (None, _) => false,
        (Some(only), None) if only.is_alphabetic() => true,
        _ => {
            DOTTED_ABBREVIATION.is_match(stripped)
                || ABBREVIATIONS.contains(&turkish_lower(stripped).as_str())
        }
    }
}

fn push_trimmed<'a>(sentences: &mut Vec<&'a str>, candidate: &'a str) {
    let sentence = candidate.trim();
    if !sentence.is_empty() {
        sentences.push(sentence);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splits_on_terminal_punctuation() {
        let text = "İzin talebi yazılı yapılır. Onay süresi beş gündür! Sorular var mı? Evet.";

        assert_eq!(
            split_sentences(text),
            [
                "İzin talebi yazılı yapılır.",
                "Onay süresi beş gündür!",
                "Sorular var mı?",
                "Evet."
            ]
        );
    }

    #[test]
    fn keeps_abbreviations_inside_sentence() {
        for text in [
            "Toplantıya Prof. Dr. Ayşe Yılmaz katılacak.",
            "Belgeyi T.C. Kimlik numarası ile doldurun.",
            "Şirket unvanı Örnek A.Ş. olarak yazılmalıdır.",
            "Kırtasiye, temizlik malzemesi vb. giderler karşılanır.",
            "Başvuru adresi Atatürk Cad. No. 5 Kadıköy olarak belirtilmiştir.",
            "Formu M. Kaya imzalamalıdır.",
        ] {
            assert_eq!(split_sentences(text), [text]);
        }
    }

    #[test]
    fn does_not_split_before_lowercase_ordinal_context() {
        assert_eq!(
            split_sentences("Bu kural 3. maddede tanımlanmıştır. Diğer kurallar ektedir."),
            [
                "Bu kural 3. maddede tanımlanmıştır.",
                "Diğer kurallar ektedir."
            ]
        );
    }

    #[test]
    fn treats_line_breaks_as_boundaries() {
        assert_eq!(
            split_sentences("2025801 AFAD Japonya\n2025802 MSB Almanya"),
            ["2025801 AFAD Japonya", "2025802 MSB Almanya"]
        );
    }

    #[test]
    fn blank_text_has_no_sentences() {
        assert_eq!(split_sentences("   "), Vec::<&str>::new());
    }
}
