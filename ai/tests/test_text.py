import pytest

from app.ingestion.text import normalize_text, split_sentences, turkish_lower


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ISPARTA", "ısparta"),
        ("İSTANBUL", "istanbul"),
        ("Iğdır İli", "ığdır ili"),
        ("ÇĞÖŞÜ", "çğöşü"),
    ],
)
def test_turkish_lower_applies_dotted_and_dotless_i_rules(raw: str, expected: str) -> None:
    assert turkish_lower(raw) == expected


def test_normalize_composes_decomposed_characters() -> None:
    decomposed = "şirket"

    assert normalize_text(decomposed) == "şirket"


def test_normalize_joins_hyphenated_line_breaks() -> None:
    assert normalize_text("sözleş-\nmenin süresi") == "sözleşmenin süresi"


def test_normalize_joins_wrapped_lines_and_keeps_paragraphs() -> None:
    raw = "Birinci satır\nikinci satır.\n\n  \nYeni   paragraf\x0c burada."

    assert normalize_text(raw) == "Birinci satır ikinci satır.\n\nYeni paragraf burada."


def test_split_sentences_on_terminal_punctuation() -> None:
    text = "İzin talebi yazılı yapılır. Onay süresi beş gündür! Sorular var mı? Evet."

    assert split_sentences(text) == [
        "İzin talebi yazılı yapılır.",
        "Onay süresi beş gündür!",
        "Sorular var mı?",
        "Evet.",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Toplantıya Prof. Dr. Ayşe Yılmaz katılacak.",
        "Belgeyi T.C. Kimlik numarası ile doldurun.",
        "Şirket unvanı Örnek A.Ş. olarak yazılmalıdır.",
        "Kırtasiye, temizlik malzemesi vb. giderler karşılanır.",
        "Başvuru adresi Atatürk Cad. No. 5 Kadıköy olarak belirtilmiştir.",
        "Formu M. Kaya imzalamalıdır.",
    ],
)
def test_split_sentences_keeps_abbreviations_inside_sentence(text: str) -> None:
    assert split_sentences(text) == [text]


def test_split_sentences_does_not_split_before_lowercase_ordinal_context() -> None:
    text = "Bu kural 3. maddede tanımlanmıştır. Diğer kurallar ektedir."

    assert split_sentences(text) == [
        "Bu kural 3. maddede tanımlanmıştır.",
        "Diğer kurallar ektedir.",
    ]


def test_split_sentences_splits_on_paragraph_break_without_punctuation() -> None:
    assert split_sentences("Başlık\n\nİçerik cümlesi.") == ["Başlık", "İçerik cümlesi."]


def test_split_sentences_returns_empty_list_for_blank_text() -> None:
    assert split_sentences("   ") == []
