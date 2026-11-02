from uuid import uuid4

import pytest

from app.db.chunks import RetrievedChunk
from app.services.prompt import SYSTEM_PROMPT, build_messages, cited_source_numbers


def test_build_messages_numbers_sources_with_file_and_page() -> None:
    chunks = [
        RetrievedChunk(uuid4(), uuid4(), "el-kitabi.pdf", 2, "İzin 14 gündür.", 0.9),
        RetrievedChunk(uuid4(), uuid4(), "masraf.pdf", 5, "Harcırah 750 TL.", 0.7),
    ]

    system, user = build_messages("İzin kaç gün?", chunks)

    assert system.role == "system"
    assert system.content == SYSTEM_PROMPT
    assert user.role == "user"
    assert "[1] (el-kitabi.pdf, sayfa 2)\nİzin 14 gündür." in user.content
    assert "[2] (masraf.pdf, sayfa 5)\nHarcırah 750 TL." in user.content
    assert user.content.endswith("Soru: İzin kaç gün?")


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("İzin 14 gündür [1].", [1]),
        ("Bilgi [2][1] ve [2].", [1, 2]),
        ("Liste [1, 3].", [1, 3]),
        ("Geçersiz [9] ve [0].", []),
        ("Kaynak yok.", []),
    ],
)
def test_cited_source_numbers(answer: str, expected: list[int]) -> None:
    assert cited_source_numbers(answer, source_count=3) == expected
