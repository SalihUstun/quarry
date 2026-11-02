from pathlib import Path

import pytest

from app.ingestion.extract import ExtractionError, extract_pages

SAMPLE_PDF = Path(__file__).resolve().parents[2] / "samples" / "calisan-el-kitabi.pdf"


def test_extracts_each_pdf_page_with_its_number() -> None:
    pages = extract_pages(SAMPLE_PDF, "application/pdf")

    assert [page.page_number for page in pages] == [1, 2, 3]
    assert "uzaktan çalışabilir" in pages[0].text
    assert "14 iş günü" in pages[1].text
    assert "750 TL" in pages[2].text


def test_text_file_is_a_single_page(tmp_path: Path) -> None:
    path = tmp_path / "not.txt"
    path.write_text("Şirket politikası metni.", encoding="utf-8")

    pages = extract_pages(path, "text/plain")

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].text == "Şirket politikası metni."


def test_corrupt_pdf_raises_extraction_error(tmp_path: Path) -> None:
    path = tmp_path / "bozuk.pdf"
    path.write_bytes(b"%PDF-1.7 bu bir pdf degil")

    with pytest.raises(ExtractionError):
        extract_pages(path, "application/pdf")


def test_blank_text_raises_extraction_error(tmp_path: Path) -> None:
    path = tmp_path / "bos.txt"
    path.write_text("   \n", encoding="utf-8")

    with pytest.raises(ExtractionError, match="no extractable text"):
        extract_pages(path, "text/plain")


def test_unsupported_content_type_raises_extraction_error(tmp_path: Path) -> None:
    path = tmp_path / "resim.png"
    path.write_bytes(b"\x89PNG")

    with pytest.raises(ExtractionError, match="Unsupported"):
        extract_pages(path, "image/png")
