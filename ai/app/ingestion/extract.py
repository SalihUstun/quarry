from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.chunker import PageText

PDF_CONTENT_TYPE = "application/pdf"
TEXT_CONTENT_TYPE = "text/plain"
SUPPORTED_CONTENT_TYPES = frozenset({PDF_CONTENT_TYPE, TEXT_CONTENT_TYPE})


class ExtractionError(Exception):
    pass


def extract_pages(path: Path, content_type: str) -> list[PageText]:
    if content_type == PDF_CONTENT_TYPE:
        pages = _extract_pdf(path)
    elif content_type == TEXT_CONTENT_TYPE:
        pages = [PageText(page_number=1, text=path.read_text(encoding="utf-8", errors="replace"))]
    else:
        raise ExtractionError(f"Unsupported content type: {content_type}")

    if not any(page.text.strip() for page in pages):
        raise ExtractionError("Document contains no extractable text")
    return pages


def _extract_pdf(path: Path) -> list[PageText]:
    try:
        reader = PdfReader(path)
        return [
            PageText(page_number=number, text=page.extract_text() or "")
            for number, page in enumerate(reader.pages, start=1)
        ]
    except (PdfReadError, OSError, ValueError) as error:
        raise ExtractionError(f"PDF could not be read: {error}") from error
