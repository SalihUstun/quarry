from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.ingestion.text import normalize_text, split_sentences


@dataclass(frozen=True, slots=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class Chunk:
    index: int
    page_number: int
    content: str

    @property
    def char_count(self) -> int:
        return len(self.content)


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    max_chars: int = 1200
    overlap_chars: int = 200

    def __post_init__(self) -> None:
        if self.max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if not 0 <= self.overlap_chars < self.max_chars:
            raise ValueError("overlap_chars must be in [0, max_chars)")


def chunk_pages(pages: Iterable[PageText], config: ChunkingConfig | None = None) -> list[Chunk]:
    resolved = config or ChunkingConfig()
    chunks: list[Chunk] = []
    for page in pages:
        sentences = _fit_sentences(split_sentences(normalize_text(page.text)), resolved.max_chars)
        for content in _pack(sentences, resolved):
            chunks.append(Chunk(index=len(chunks), page_number=page.page_number, content=content))
    return chunks


def _fit_sentences(sentences: Iterable[str], max_chars: int) -> list[str]:
    fitted: list[str] = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            fitted.append(sentence)
        else:
            fitted.extend(_split_long_sentence(sentence, max_chars))
    return fitted


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for word in sentence.split():
        for part in _hard_wrap(word, max_chars):
            candidate = f"{current} {part}" if current else part
            if len(candidate) <= max_chars:
                current = candidate
            else:
                pieces.append(current)
                current = part
    if current:
        pieces.append(current)
    return pieces


def _hard_wrap(word: str, max_chars: int) -> list[str]:
    return [word[offset : offset + max_chars] for offset in range(0, len(word), max_chars)]


def _pack(sentences: Sequence[str], config: ChunkingConfig) -> list[str]:
    packed: list[str] = []
    current: list[str] = []
    length = 0
    for sentence in sentences:
        if current and length + 1 + len(sentence) > config.max_chars:
            packed.append("\n".join(current))
            current = _overlap_tail(current, config.overlap_chars)
            length = _joined_length(current)
            if current and length + 1 + len(sentence) > config.max_chars:
                current, length = [], 0
        length += len(sentence) + (1 if current else 0)
        current.append(sentence)
    if current:
        packed.append("\n".join(current))
    return packed


def _overlap_tail(sentences: Sequence[str], overlap_chars: int) -> list[str]:
    tail: list[str] = []
    length = 0
    for sentence in reversed(sentences):
        added = len(sentence) + (1 if tail else 0)
        if length + added > overlap_chars:
            break
        tail.insert(0, sentence)
        length += added
    return tail


def _joined_length(sentences: Sequence[str]) -> int:
    return sum(len(sentence) for sentence in sentences) + max(len(sentences) - 1, 0)
