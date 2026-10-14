## main

Provider: `sim` · seeds: [1] · 30 tasks × 1 epochs per arm · values are mean ± sd across seeds

| Arm | Success % | Precision % | Injected % | Misled % | Poisoned inj. % | Redundancy idx | Tokens/task | Ctx tokens | $/success |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 66.7 | 0.0 | 0.0 | 0.0 | 0.0 | 1.000 | 930 | 0 | 0.0192 |
| flat_memory | 66.7 | 81.8 | 73.3 | 33.3 | 22.2 | 0.125 | 1026 | 96 | 0.0197 |
| actioncloud | 66.7 | 80.0 | 66.7 | 31.2 | 12.5 | 0.125 | 1018 | 88 | 0.0196 |

| vs baseline | Token savings % | Cost savings % | Latency reduction % | Success Δ (pp) |
|---|---:|---:|---:|---:|
| flat_memory | -10.4 | -2.3 | -0.1 | 0.0 |
| actioncloud | -9.6 | -2.1 | -0.1 | 0.0 |
