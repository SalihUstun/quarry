Makine: Darwin arm64, 3.12.15 (CPython). Her ölçüm 5 çalıştırmanın medyanı.

| Girdi | Chunk | Python süre | Rust süre | Hızlanma | Python bellek | Rust bellek | Çıktı aynı |
|---|---|---|---|---|---|---|---|
| 1 MB | 1,178 | 0.103 s | 0.026 s | **3.9x** | 29 MB | 8 MB | ✅ |
| 10 MB | 11,770 | 1.064 s | 0.255 s | **4.2x** | 100 MB | 40 MB | ✅ |
| 50 MB | 58,844 | 5.381 s | 1.264 s | **4.3x** | 322 MB | 182 MB | ✅ |
