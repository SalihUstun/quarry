from itertools import pairwise

import pytest

from app.ingestion.chunker import ChunkingConfig, PageText, chunk_pages


def sentence(number: int) -> str:
    return f"Bu {number:02d} numaralı cümle yeterince uzun bir örnek metindir."


def test_short_page_becomes_single_chunk() -> None:
    chunks = chunk_pages([PageText(page_number=1, text="Kısa bir metin. İkinci cümle.")])

    assert len(chunks) == 1
    assert chunks[0].content == "Kısa bir metin.\nİkinci cümle."
    assert chunks[0].page_number == 1
    assert chunks[0].index == 0


def test_chunks_never_exceed_max_chars() -> None:
    config = ChunkingConfig(max_chars=200, overlap_chars=60)
    text = " ".join(sentence(number) for number in range(40))

    chunks = chunk_pages([PageText(1, text)], config)

    assert len(chunks) > 1
    assert all(chunk.char_count <= config.max_chars for chunk in chunks)


def test_consecutive_chunks_share_overlapping_sentences() -> None:
    config = ChunkingConfig(max_chars=200, overlap_chars=60)
    text = " ".join(sentence(number) for number in range(10))

    chunks = chunk_pages([PageText(1, text)], config)

    for previous, current in pairwise(chunks):
        last_sentence_of_previous = previous.content.splitlines()[-1]
        assert current.content.startswith(last_sentence_of_previous)


def test_every_sentence_appears_in_some_chunk() -> None:
    config = ChunkingConfig(max_chars=150, overlap_chars=40)
    sentences = [sentence(number) for number in range(25)]

    chunks = chunk_pages([PageText(1, " ".join(sentences))], config)

    combined = "\n".join(chunk.content for chunk in chunks)
    assert all(item in combined for item in sentences)


def test_chunks_do_not_cross_pages_and_keep_global_index() -> None:
    pages = [PageText(1, "Birinci sayfa metni."), PageText(2, "İkinci sayfa metni.")]

    chunks = chunk_pages(pages)

    assert [(chunk.index, chunk.page_number) for chunk in chunks] == [(0, 1), (1, 2)]


def test_sentence_longer_than_limit_is_split_by_words() -> None:
    config = ChunkingConfig(max_chars=50, overlap_chars=10)
    long_sentence = " ".join(["kelime"] * 40) + "."

    chunks = chunk_pages([PageText(1, long_sentence)], config)

    assert len(chunks) > 1
    assert all(chunk.char_count <= 50 for chunk in chunks)


def test_word_longer_than_limit_is_hard_wrapped() -> None:
    config = ChunkingConfig(max_chars=10, overlap_chars=0)

    chunks = chunk_pages([PageText(1, "a" * 25)], config)

    assert [chunk.content for chunk in chunks] == ["a" * 10, "a" * 10, "a" * 5]


def test_empty_pages_produce_no_chunks() -> None:
    assert chunk_pages([PageText(1, "  \n "), PageText(2, "")]) == []


@pytest.mark.parametrize(("max_chars", "overlap_chars"), [(0, 0), (100, 100), (100, -1)])
def test_invalid_config_is_rejected(max_chars: int, overlap_chars: int) -> None:
    with pytest.raises(ValueError, match="must"):
        ChunkingConfig(max_chars=max_chars, overlap_chars=overlap_chars)


def test_table_rows_stay_on_separate_lines_within_a_chunk() -> None:
    rows = [
        "2025848 20258059 MSB- 6G VE ÖTESİ 2 EA/SAY ABD, İsviçre, Almanya, Fransa Mühendis",
        "2025849 20258060 MSB- OTONOM SİSTEMLER 1 EA/SAY ABD, Japonya, Almanya Mühendis",
    ]

    chunks = chunk_pages([PageText(4, "\n".join(rows))])

    assert chunks[0].content.splitlines() == rows
