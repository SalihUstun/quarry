import hashlib
import json
import sys
import time

from app.ingestion.chunker import ChunkingConfig, PageText, chunk_pages


def checksum(chunks: list) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(str(chunk.page_number).encode())
        digest.update(b"\x1f")
        digest.update(chunk.content.encode())
        digest.update(b"\x1e")
    return digest.hexdigest()


def main(path: str) -> None:
    with open(path, encoding="utf-8") as corpus_file:
        corpus = json.load(corpus_file)
    config = ChunkingConfig(corpus["max_chars"], corpus["overlap_chars"])
    pages = [PageText(page["page_number"], page["text"]) for page in corpus["pages"]]

    started = time.perf_counter()
    chunks = chunk_pages(pages, config)
    seconds = time.perf_counter() - started

    report = {
        "implementation": "python",
        "seconds": seconds,
        "chunks": len(chunks),
        "checksum": checksum(chunks),
    }
    print(json.dumps(report))


if __name__ == "__main__":
    main(sys.argv[1])
