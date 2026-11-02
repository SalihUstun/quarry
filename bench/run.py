import json
import os
import platform
import resource
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "bench"
CORPUS_DIR = BENCH / ".corpus"
SIZES_MB = [1, 10, 50]
RUNS = 5
MAX_CHARS = 1200
OVERLAP_CHARS = 200


def source_pages() -> list[str]:
    cases = json.loads((ROOT / "fixtures" / "chunking" / "cases.json").read_text(encoding="utf-8"))
    by_name = {case["name"]: case for case in cases}
    texts = [page["text"] for page in by_name["handbook_pdf"]["pages"]]
    texts += [page["text"] for name in ("table_rows", "abbreviations", "wrapping_and_hyphenation")
              for page in by_name[name]["pages"]]
    return texts


def build_corpus(size_mb: int) -> Path:
    path = CORPUS_DIR / f"corpus-{size_mb}mb.json"
    if path.exists():
        return path
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    texts = source_pages()
    target = size_mb * 1024 * 1024
    pages, total, index = [], 0, 0
    while total < target:
        text = "\n\n".join(texts[(index + offset) % len(texts)] for offset in range(3))
        pages.append({"page_number": index + 1, "text": text})
        total += len(text.encode("utf-8"))
        index += 1
    corpus = {"max_chars": MAX_CHARS, "overlap_chars": OVERLAP_CHARS, "pages": pages}
    path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    return path


def peak_rss_mb(rusage: resource.struct_rusage) -> float:
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return rusage.ru_maxrss / divisor


def measure(command: list[str], cwd: Path, env: dict[str, str]) -> tuple[dict[str, object], float]:
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, text=True)
    assert process.stdout is not None
    output = process.stdout.read()
    _, status, rusage = os.wait4(process.pid, 0)
    process.returncode = os.waitstatus_to_exitcode(status)
    if process.returncode != 0:
        raise RuntimeError(f"{command[0]} failed with exit code {process.returncode}")
    return json.loads(output), peak_rss_mb(rusage)


def commands() -> dict[str, tuple[list[str], Path, dict[str, str]]]:
    subprocess.run(
        ["cargo", "build", "--release", "--quiet", "-p", "quarry-bench"], cwd=ROOT / "rust", check=True
    )
    python = ROOT / "ai" / ".venv" / "bin" / "python"
    python_env = {**os.environ, "PYTHONPATH": str(ROOT / "ai")}
    return {
        "Python": ([str(python), str(BENCH / "python_chunk.py")], ROOT / "ai", python_env),
        "Rust": ([str(ROOT / "rust" / "target" / "release" / "quarry-bench")], ROOT, dict(os.environ)),
    }


def main() -> None:
    implementations = commands()
    rows = []
    for size_mb in SIZES_MB:
        corpus = build_corpus(size_mb)
        results = {}
        for name, (command, cwd, env) in implementations.items():
            timings, memory, report = [], [], {}
            for _ in range(RUNS):
                report, rss = measure([*command, str(corpus)], cwd, env)
                timings.append(float(report["seconds"]))
                memory.append(rss)
            results[name] = {
                "seconds": statistics.median(timings),
                "peak_rss_mb": statistics.median(memory),
                "chunks": report["chunks"],
                "checksum": report["checksum"],
            }
            print(f"{size_mb} MB {name}: {results[name]}", file=sys.stderr)
        identical = results["Python"]["checksum"] == results["Rust"]["checksum"]
        rows.append({"size_mb": size_mb, "identical_output": identical, **{
            f"{name.lower()}_{key}": value for name, result in results.items()
            for key, value in result.items() if key != "checksum"}})

    machine = f"{platform.system()} {platform.machine()}, {platform.python_version()} (CPython)"
    (BENCH / "results.json").write_text(
        json.dumps({"machine": machine, "runs": RUNS, "rows": rows}, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "| Girdi | Chunk | Python süre | Rust süre | Hızlanma | Python bellek | Rust bellek | Çıktı aynı |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['size_mb']} MB | {row['rust_chunks']:,} | {row['python_seconds']:.3f} s | "
            f"{row['rust_seconds']:.3f} s | **{row['python_seconds'] / row['rust_seconds']:.1f}x** | "
            f"{row['python_peak_rss_mb']:.0f} MB | {row['rust_peak_rss_mb']:.0f} MB | "
            f"{'✅' if row['identical_output'] else '❌'} |"
        )
    table = "\n".join(lines)
    (BENCH / "results.md").write_text(
        f"Makine: {machine}. Her ölçüm {RUNS} çalıştırmanın medyanı.\n\n{table}\n", encoding="utf-8"
    )
    print(table)


if __name__ == "__main__":
    main()
