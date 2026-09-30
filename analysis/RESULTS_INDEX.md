**TL;DR** The committed result files behind the numbers in `docs/STATUS_*.md` and the paper tables. Each file records its script sha, git head and snapshot sha. Newer files are produced automatically by `scripts/a6000/analysis_daemon.py`, and the latest version of each is committed when the status docs are updated.

| result | file (latest committed) | producing script |
|---|---|---|
| τ² same-state forks (W4, KV8, stress) | `analysis/fork/out/dev_all_*.{md,json}` | `analysis/fork/analyze_dev.py` |
| KV8 / stress subsets | `analysis/fork/out/dev_kvq_int8_*`, `dev_gptq_w3_kvq_int4_rot_*` | same |
| forks on ALFWorld / BFCL | `analysis/fork/out/ext_*` | `analysis/fork/analyze_ext.py` |
| restoration / residual dose | `analysis/fork/out/restore_eval_*` | `analysis/fork/analyze_restore_eval.py` |
| pivot detection (exploratory) | `analysis/fork/out/pivot_*` | `analysis/fork/analyze_pivot.py` |
| pivot-arm screening | `analysis/fork/out/pivot_arms_*` | `analysis/fork/analyze_pivot_arms.py` |
| difficulty moderators (exploratory) | `analysis/fork/out/difficulty_*` | `analysis/fork/analyze_difficulty.py` |
| W×A×KV matrix | `analysis/ahook/out/wakv_*` | `analysis/ahook/analyze_wakv.py` |
| success NI/TOST | `analysis/insights/iter_4/out/success_ni_REAL_*.json` | `analysis/insights/iter_4/success_ni.py` |

The integrity snapshots (`analysis/insights/iter_3/out/snapshot_auto_*.json`) are the admitted-run manifests the analyses read. Each output file cites its snapshot by path and sha.
