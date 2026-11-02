import re
import unicodedata

ABBREVIATIONS = frozenset(
    {
        "a",
        "apt",
        "av",
        "bkz",
        "bşk",
        "cad",
        "çev",
        "dr",
        "doç",
        "ed",
        "gn",
        "hz",
        "ins",
        "kr",
        "ltd",
        "mad",
        "mah",
        "md",
        "müh",
        "no",
        "nr",
        "öğr",
        "örn",
        "prof",
        "s",
        "sn",
        "sok",
        "şti",
        "tel",
        "uzm",
        "vb",
        "vd",
        "vs",
        "yy",
        "yrd",
    }
)

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HYPHENATED_LINE_BREAK = re.compile(r"(\w)-\n[ \t]*([a-zçğıöşü])")
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n\s*")
_LINE_BREAK = re.compile(r"[ \t]*\n[ \t]*")
_HORIZONTAL_WHITESPACE = re.compile(r"[ \t ]+")
_SENTENCE_BOUNDARY = re.compile(r"[.!?…]+[\"'”’)\]]*\s+|\n\n")
_DOTTED_ABBREVIATION = re.compile(r"^(?:\w\.)+\w?$")
_PARAGRAPH_MARKER = " "


def turkish_lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def normalize_text(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARACTERS.sub("", text)
    text = _HYPHENATED_LINE_BREAK.sub(r"\1\2", text)
    text = _PARAGRAPH_BREAK.sub(_PARAGRAPH_MARKER, text)
    text = _LINE_BREAK.sub(" ", text)
    text = _HORIZONTAL_WHITESPACE.sub(" ", text)
    paragraphs = (paragraph.strip() for paragraph in text.split(_PARAGRAPH_MARKER))
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        end = match.end()
        if _is_sentence_end(text, match.start(), end):
            _append_stripped(sentences, text[start:end])
            start = end
    _append_stripped(sentences, text[start:])
    return sentences


def _is_sentence_end(text: str, punctuation_start: int, boundary_end: int) -> bool:
    if text.startswith("\n\n", punctuation_start):
        return True
    if boundary_end < len(text) and text[boundary_end].islower():
        return False
    if text[punctuation_start] != ".":
        return True
    return not _is_abbreviation(_last_token(text, punctuation_start))


def _last_token(text: str, end: int) -> str:
    start = end
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    return text[start:end]


def _is_abbreviation(token: str) -> bool:
    stripped = token.lstrip("(\"'“‘")
    if not stripped:
        return False
    if len(stripped) == 1 and stripped.isalpha():
        return True
    if _DOTTED_ABBREVIATION.match(stripped):
        return True
    return turkish_lower(stripped) in ABBREVIATIONS


def _append_stripped(sentences: list[str], candidate: str) -> None:
    sentence = candidate.strip()
    if sentence:
        sentences.append(sentence)
