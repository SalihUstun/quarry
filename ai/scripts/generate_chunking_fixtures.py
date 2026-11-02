import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from app.ingestion.chunker import ChunkingConfig, PageText, chunk_pages
from app.ingestion.extract import extract_pages

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PDF = REPO_ROOT / "samples" / "calisan-el-kitabi.pdf"
OUTPUT = REPO_ROOT / "fixtures" / "chunking" / "cases.json"


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    pages: list[PageText]
    max_chars: int = 1200
    overlap_chars: int = 200

    def to_json(self) -> dict[str, object]:
        chunks = chunk_pages(self.pages, ChunkingConfig(self.max_chars, self.overlap_chars))
        return {
            "name": self.name,
            "max_chars": self.max_chars,
            "overlap_chars": self.overlap_chars,
            "pages": [asdict(page) for page in self.pages],
            "expected": [
                {"index": chunk.index, "page_number": chunk.page_number, "content": chunk.content}
                for chunk in chunks
            ],
        }


def sentence(number: int) -> str:
    return f"Bu {number:02d} numaralı cümle yeterince uzun bir örnek metindir."


TABLE = "\n".join(
    [
        "Kurum Alan Kontenjan Ülkeler Kadro",
        "2025848 20258059 MSB- 6G VE ÖTESİ 2 EA/SAY ABD, İsviçre, Almanya, Fransa Mühendis",
        "2025849 20258060 MSB- OTONOM SİSTEMLER 1 EA/SAY ABD, Japonya, Almanya Mühendis",
        "2025850 20258063 MSB- KİMYASAL SAVUNMA 1 EA/SAY ABD, Kanada, İsviçre Mühendis",
    ]
)

ABBREVIATIONS = (
    "Toplantıya Prof. Dr. Ayşe Yılmaz katılacak. Belgeyi T.C. Kimlik no. ile doldurun. "
    "Örnek A.Ş. adına M. Kaya imzalar. Kural 3. maddede yazılıdır. "
    "Kırtasiye vb. giderler ödenir! Soru var mı? Evet."
)

WRAPPING = (
    "Sözleş-\nmenin süresi bir\nyıldır.\r\n\r\n  \nYeni   paragraf\x0c burada.\n"
    "şirket ISPARTA ofisi\nİstanbul şubesi"
)


def build_cases() -> list[Case]:
    handbook = extract_pages(SAMPLE_PDF, "application/pdf")
    return [
        Case("handbook_pdf", handbook),
        Case("handbook_pdf_small", handbook, max_chars=160, overlap_chars=60),
        Case("table_rows", [PageText(4, TABLE)], max_chars=180, overlap_chars=90),
        Case("abbreviations", [PageText(1, ABBREVIATIONS)], max_chars=80, overlap_chars=30),
        Case("wrapping_and_hyphenation", [PageText(2, WRAPPING)]),
        Case(
            "long_sentence_and_word",
            [PageText(1, " ".join(["kelime"] * 60) + ". " + "a" * 95)],
            max_chars=40,
            overlap_chars=10,
        ),
        Case(
            "many_sentences_overlap",
            [PageText(3, " ".join(sentence(number) for number in range(30)))],
            max_chars=200,
            overlap_chars=60,
        ),
        Case("empty_pages", [PageText(1, "  \n "), PageText(2, "")]),
    ]


def render() -> str:
    cases = [case.to_json() for case in build_cases()]
    return json.dumps(cases, ensure_ascii=False, indent=2) + "\n"


def main(arguments: list[str]) -> int:
    if "--check" in arguments:
        return 0 if OUTPUT.read_text(encoding="utf-8") == render() else 1
    OUTPUT.write_text(render(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
