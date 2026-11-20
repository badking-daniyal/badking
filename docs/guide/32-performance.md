# Performance

```bash
python benchmarks/bench_core.py
```

Measured on a local machine (Python 3.9, Windows):

| Operation | RPS | avg ms | P95 | P99 |
|---|---:|---:|---:|---:|
| filter.text_eq | 752,842 | 0.0011 | 0.0011 | 0.0012 |
| digits.fa_to_en | 202,988 | 0.0047 | 0.0048 | 0.0064 |
| text.smart_split | 73,824 | 0.0133 | 0.0139 | 0.0319 |
| proto.roundtrip | 134,890 | 0.0072 | 0.0073 | 0.0087 |

**No comparison with aiobale has been measured.** No performance claim is made.
