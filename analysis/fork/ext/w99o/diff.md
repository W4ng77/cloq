# W99o: old → new numbers (ext and ext_r2)

- old: `analysis/fork/out/ext_20261001T135106Z.json`, `analysis/fork/out/ext_r2_20261002T024433Z.json`
- new: `analysis/fork/out/ext_20261002T103443Z.json`, `analysis/fork/out/ext_r2_20261002T103454Z.json`

## 1. tab:extr2 columns per cell (only changed entries; `=` rows omitted)

**ALFWorld q8 AWQ-W4**: unchanged

**ALFWorld q8 GPTQ-W4**: unchanged

**BFCL q4 AWQ-W4**: unchanged

**BFCL q4 GPTQ-W4**: unchanged

**BFCL q8 AWQ-W4**: unchanged

**BFCL q8 GPTQ-W4**: unchanged

**ALFWorld q8 GPTQ-W3**: unchanged

**ALFWorld q8 KV4**: unchanged

**BFCL q4 GPTQ-W3**: unchanged

**BFCL q4 KV4**: unchanged

**BFCL q8 GPTQ-W3**: unchanged

**BFCL q8 KV4**: unchanged

## 2. Pools (equal weight per cell)

**W4:alfworld:pooled_equal_weight**: unchanged
**W4:all_envs:pooled_equal_weight**: unchanged
**W4:bfcl:pooled_equal_weight**: unchanged
**stress:alfworld:pooled_equal_weight**: unchanged
**stress:all_envs:pooled_equal_weight**: unchanged
**stress:bfcl:pooled_equal_weight**: unchanged

## 3. Ranges and statements quoted in the paper text

- BFCL W4 off-diagonal range %: 4.7–17.1 (unchanged)
- BFCL W4 off-diagonal pool %: 10.3 (unchanged)
- ALFWorld W4 off-diagonal range %: 32.8–40.0 (unchanged)
- BFCL W4 expected off-diagonal range %: 16.2–32.4 (unchanged)
- BFCL W4 kappa range: 0.47–0.71 (unchanged)
- W4 turnover M range % (BFCL + ALFWorld cells): 5.2–24.6 (unchanged)
- W4 cells whose G_all 95% CI excludes 0: bfcl:q4:awq_w4_d1 -3.8 [-6.5, -1.3] (unchanged)
- BFCL W4 pool G_all: +0.1 [-1.0, +1.2] (unchanged)
- W4 all-env pool G_all: -1.2 [-3.3, +0.8] (unchanged)
- stress BFCL pool G_all: +1.0 [+0.2, +1.9] (unchanged)
- tau2 comparison line: τ² W4 pooled G_all +0.7 [-0.3, +1.6] pp, divergence 82%; ALFWorld -3.7 [-9.7, +1.9] pp, divergence 87%; BFCL +0.1 [-1.0, +1.2] pp, divergence 73% (τ² source analysis/fork/out/dev_all_20261001T093944Z.json). (unchanged)

## 4. Exhaustive: every changed numeric leaf (rounded) under cells/pooled

### ext: 0 changed leaves


### ext_r2: 0 changed leaves


