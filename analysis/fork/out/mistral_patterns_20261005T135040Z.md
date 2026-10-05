**TL;DR** EXPLORATORY, POST HOC. Mistral-Small-3.2-24B, ordinary BF16-trajectory states (U2B), A6 primary view, pool of GPTQ-W4 and RTN-W4 (equal-weight cells, 464 non-exact states, K = 5 common blocks): act_any 28.4 [24.1, 32.8] (t), 28.4 [19.5, 36.3] (crossed)%, cont_any 24.2 [21.0, 27.7] (t), 24.2 [17.0, 31.3] (crossed)%, gap +4.1 [+0.2, +8.1] (t), +4.1 [-0.6, +8.9] (crossed) pp. Classes: unchanged 69.3, action only 6.5, continuation only 2.3, one arm differs 20.2, strict reversal 1.7%. Joint rescue (1000) 3.4 [0.9, 6.1] (t), 3.4 [0.9, 6.8] (crossed)% vs label reference 2.9 (obs - ref +0.5 [-2.4, +3.5] (t), +0.5 [-2.0, +3.6] (crossed) pp); rescue undone (0100, 0110) 4.0 [2.2, 5.9] (t), 4.0 [1.5, 7.1] (crossed)% vs 4.7 (obs - ref -0.7 [-2.0, +0.7] (t), -0.7 [-3.0, +1.9] (crossed) pp). Check vs `analysis/fork/out/newmethod_m24_20261004T024453Z.json`: True. These are BF16-trajectory states (BB = recorded BF16 original), not Bank P upgrade states: the named patterns are defined by arm label and do not carry the Bank P rescue reading.

# Outcome classes on the m24 panel (EXPLORATORY, POST HOC; 20261005T135040Z)

Script `analysis/fork/mistral_patterns.py` (sha256 1f23d1cc92a40611), git a431b7ff6e, B = 2000, seed 20261001. Full numbers: `analysis/fork/out/mistral_patterns_20261005T135040Z.json` (block bootstrap and task-cluster intervals kept there). Shares in % of the stated denominator. Fixed pool: t over per-block ratios (K < 10), not clipped at 0; zero-count shares print [0.0, 0.0]: not valid intervals for a proportion. Rows `<view>:<denominator>:<cell>`; pool = GPTQ-W4 + RTN-W4 on common blocks.

## 1. Action vs continuation (fixed task pool, t)

| group | states | K | act_any | cont_any | act - cont | P(k=2) |
|---|---|---|---|---|---|---|
| A6:nonexact:gptq_w4_d1 | 264 | 6 | 29.6 [26.6, 32.8] | 25.4 [21.1, 29.7] | +4.2 [+0.8, +7.8] | 11.4 [7.4, 14.8] |
| A6:nonexact:rtn_w4 | 251 | 5 | 26.7 [19.1, 34.5] | 23.1 [17.7, 28.8] | +3.6 [-0.5, +7.6] | 10.8 [9.1, 12.6] |
| A6:nonexact:pool | 464 | 5 | 28.4 [24.1, 32.8] | 24.2 [21.0, 27.7] | +4.1 [+0.2, +8.1] | 10.5 [9.3, 11.7] |
| A6:all:gptq_w4_d1 | 498 | 6 | 15.7 [14.3, 17.1] | 21.3 [19.2, 23.4] | -5.6 [-8.0, -3.3] | 13.9 [10.6, 17.1] |
| A6:all:rtn_w4 | 415 | 5 | 16.1 [11.6, 20.7] | 21.2 [17.9, 24.5] | -5.1 [-7.0, -3.1] | 13.7 [12.4, 15.1] |
| A6:all:pool | 830 | 5 | 15.8 [13.8, 17.7] | 21.0 [19.0, 23.0] | -5.2 [-6.7, -3.6] | 13.4 [11.7, 15.1] |
| strict:nonexact:gptq_w4_d1 | 215 | 5 | 30.2 [26.9, 33.8] | 25.6 [20.0, 31.2] | +4.7 [+0.4, +9.1] | 11.2 [6.1, 15.8] |
| strict:nonexact:rtn_w4 | 144 | 3 | 28.5 [11.8, 44.9] | 25.7 [15.9, 35.4] | +2.8 [-4.9, +10.3] | 11.8 [10.3, 13.3] |
| strict:nonexact:pool | 266 | 3 | 29.4 [24.0, 34.6] | 25.6 [18.8, 32.3] | +3.9 [-4.8, +12.3] | 10.0 [8.8, 11.2] |
| strict:all:gptq_w4_d1 | 415 | 5 | 15.7 [13.8, 17.5] | 21.2 [18.5, 23.9] | -5.5 [-8.6, -2.4] | 13.7 [9.4, 18.0] |
| strict:all:rtn_w4 | 249 | 3 | 16.5 [5.1, 27.8] | 22.1 [15.2, 29.0] | -5.6 [-10.2, -1.1] | 14.1 [12.3, 15.8] |
| strict:all:pool | 498 | 3 | 15.7 [11.7, 19.6] | 21.3 [16.0, 26.5] | -5.6 [-8.7, -2.5] | 13.1 [8.7, 17.4] |

## 2. Same, new tasks (crossed task x block)

| group | states | K | act_any | cont_any | act - cont | P(k=2) |
|---|---|---|---|---|---|---|
| A6:nonexact:gptq_w4_d1 | 264 | 6 | 29.6 [20.4, 38.4] | 25.4 [17.3, 33.8] | +4.2 [-1.8, +10.0] | 11.4 [5.7, 17.9] |
| A6:nonexact:rtn_w4 | 251 | 5 | 26.7 [17.4, 36.6] | 23.1 [14.8, 31.9] | +3.6 [-1.7, +8.7] | 10.8 [5.4, 16.5] |
| A6:nonexact:pool | 464 | 5 | 28.4 [19.5, 36.3] | 24.2 [17.0, 31.3] | +4.1 [-0.6, +8.9] | 10.5 [6.3, 15.1] |
| A6:all:gptq_w4_d1 | 498 | 6 | 15.7 [10.6, 20.9] | 21.3 [15.9, 27.5] | -5.6 [-11.0, -1.2] | 13.9 [8.8, 19.3] |
| A6:all:rtn_w4 | 415 | 5 | 16.1 [10.1, 22.2] | 21.2 [14.9, 27.9] | -5.1 [-9.9, -0.7] | 13.7 [8.9, 19.0] |
| A6:all:pool | 830 | 5 | 15.8 [10.7, 20.6] | 21.0 [15.3, 26.4] | -5.2 [-9.2, -1.7] | 13.4 [9.6, 17.6] |
| strict:nonexact:gptq_w4_d1 | 215 | 5 | 30.2 [20.6, 40.0] | 25.6 [16.8, 34.9] | +4.7 [-2.0, +10.9] | 11.2 [5.1, 18.6] |
| strict:nonexact:rtn_w4 | 144 | 3 | 28.5 [16.8, 40.4] | 25.7 [15.9, 36.7] | +2.8 [-4.2, +9.7] | 11.8 [5.3, 19.2] |
| strict:nonexact:pool | 266 | 3 | 29.4 [20.3, 38.2] | 25.6 [17.2, 34.7] | +3.9 [-2.0, +9.5] | 10.0 [5.3, 15.5] |
| strict:all:gptq_w4_d1 | 415 | 5 | 15.7 [10.1, 21.2] | 21.2 [15.2, 27.5] | -5.5 [-11.1, -0.5] | 13.7 [8.4, 19.5] |
| strict:all:rtn_w4 | 249 | 3 | 16.5 [9.2, 24.5] | 22.1 [15.3, 29.7] | -5.6 [-12.4, +0.0] | 14.1 [8.4, 20.5] |
| strict:all:pool | 498 | 3 | 15.7 [10.2, 21.5] | 21.3 [15.5, 27.5] | -5.6 [-10.6, -1.2] | 13.1 [8.6, 18.1] |

## 3. Five classes (partition; fixed task pool, t)

| group | states | K | unchanged | action only | continuation only | one arm differs | strict reversal |
|---|---|---|---|---|---|---|---|
| A6:nonexact:gptq_w4_d1 | 264 | 6 | 67.8 [63.6, 71.9] | 6.8 [4.8, 8.9] | 2.6 [-0.0, 5.1] | 20.8 [16.8, 25.4] | 1.9 [-0.8, 4.3] |
| A6:nonexact:rtn_w4 | 251 | 5 | 70.5 [63.8, 77.0] | 6.4 [4.4, 8.3] | 2.8 [0.6, 5.1] | 18.7 [13.2, 24.4] | 1.6 [0.5, 2.8] |
| A6:nonexact:pool | 464 | 5 | 69.3 [65.3, 73.0] | 6.5 [4.3, 8.7] | 2.3 [0.5, 4.2] | 20.2 [16.5, 24.1] | 1.7 [0.5, 2.8] |
| A6:all:gptq_w4_d1 | 498 | 6 | 75.1 [72.6, 77.6] | 3.6 [2.5, 4.8] | 9.2 [6.8, 11.7] | 11.0 [9.6, 12.5] | 1.0 [-0.5, 2.5] |
| A6:all:rtn_w4 | 415 | 5 | 74.9 [70.8, 79.1] | 3.9 [2.6, 5.1] | 8.9 [8.1, 9.7] | 11.3 [8.1, 14.6] | 1.0 [0.3, 1.6] |
| A6:all:pool | 830 | 5 | 75.4 [72.8, 78.1] | 3.6 [2.4, 4.8] | 8.8 [7.7, 9.9] | 11.2 [9.8, 12.6] | 1.0 [0.3, 1.6] |
| strict:nonexact:gptq_w4_d1 | 215 | 5 | 67.0 [62.1, 71.9] | 7.4 [5.4, 9.4] | 2.8 [-0.8, 6.1] | 21.9 [17.4, 26.8] | 0.9 [-0.6, 2.4] |
| strict:nonexact:rtn_w4 | 144 | 3 | 68.1 [54.9, 81.5] | 6.2 [1.8, 10.6] | 3.5 [0.2, 6.8] | 20.1 [7.1, 33.0] | 2.1 [1.8, 2.4] |
| strict:nonexact:pool | 266 | 3 | 68.0 [63.5, 72.7] | 6.4 [2.6, 10.2] | 2.6 [-2.2, 7.4] | 21.9 [17.9, 25.9] | 1.0 [0.9, 1.2] |
| strict:all:gptq_w4_d1 | 415 | 5 | 74.9 [71.7, 78.2] | 3.9 [2.6, 5.1] | 9.4 [6.2, 12.6] | 11.3 [9.6, 13.0] | 0.5 [-0.3, 1.3] |
| strict:all:rtn_w4 | 249 | 3 | 74.3 [64.7, 83.9] | 3.6 [0.6, 6.6] | 9.2 [7.5, 11.0] | 11.7 [3.0, 20.3] | 1.2 [1.2, 1.2] |
| strict:all:pool | 498 | 3 | 75.3 [68.8, 81.8] | 3.4 [1.1, 5.7] | 9.0 [6.0, 12.0] | 11.7 [9.4, 13.9] | 0.6 [0.6, 0.6] |

## 4. Named patterns and label reference (fixed task pool, t)

| group | states | K | joint rescue | E[J] (label ref) | jr - E[J] | rescue undone | E[U] (label ref) | ru - E[U] |
|---|---|---|---|---|---|---|---|---|
| A6:nonexact:gptq_w4_d1 | 264 | 6 | 3.4 [0.1, 6.7] | 2.8 [2.4, 3.4] | +0.6 [-3.2, +4.3] | 2.6 [0.2, 5.0] | 4.7 [4.2, 5.2] | -2.1 [-4.3, +0.0] |
| A6:nonexact:rtn_w4 | 251 | 5 | 4.0 [0.1, 8.1] | 2.9 [1.9, 4.0] | +1.1 [-2.5, +4.8] | 5.2 [1.2, 9.5] | 4.7 [3.4, 6.0] | +0.5 [-2.3, +3.5] |
| A6:nonexact:pool | 464 | 5 | 3.4 [0.9, 6.1] | 2.9 [2.2, 3.6] | +0.5 [-2.4, +3.5] | 4.0 [2.2, 5.9] | 4.7 [4.1, 5.3] | -0.7 [-2.0, +0.7] |
| A6:all:gptq_w4_d1 | 498 | 6 | 1.8 [0.1, 3.5] | n/a | n/a | 1.4 [0.2, 2.6] | n/a | n/a |
| A6:all:rtn_w4 | 415 | 5 | 2.4 [0.0, 4.8] | n/a | n/a | 3.1 [0.9, 5.4] | n/a | n/a |
| A6:all:pool | 830 | 5 | 1.9 [0.5, 3.4] | n/a | n/a | 2.3 [1.3, 3.3] | n/a | n/a |
| strict:nonexact:gptq_w4_d1 | 215 | 5 | 3.7 [-0.7, 7.9] | 2.8 [2.2, 3.5] | +0.9 [-4.0, +5.7] | 2.3 [-0.7, 5.3] | 4.7 [4.0, 5.2] | -2.3 [-5.1, +0.4] |
| strict:nonexact:rtn_w4 | 144 | 3 | 4.2 [-1.6, 10.1] | 3.5 [2.4, 4.6] | +0.7 [-4.0, +5.5] | 7.6 [4.0, 11.4] | 5.4 [4.5, 6.4] | +2.2 [-0.5, +5.0] |
| strict:nonexact:pool | 266 | 3 | 3.3 [0.0, 6.7] | 3.3 [2.1, 4.4] | +0.0 [-4.3, +4.5] | 4.6 [0.3, 9.0] | 4.9 [3.7, 6.2] | -0.3 [-3.8, +3.2] |
| strict:all:gptq_w4_d1 | 415 | 5 | 1.9 [-0.3, 4.2] | n/a | n/a | 1.2 [-0.3, 2.7] | n/a | n/a |
| strict:all:rtn_w4 | 249 | 3 | 2.4 [-0.6, 5.4] | n/a | n/a | 4.4 [2.7, 6.2] | n/a | n/a |
| strict:all:pool | 498 | 3 | 1.8 [0.3, 3.3] | n/a | n/a | 2.6 [0.3, 4.9] | n/a | n/a |

## 5. Named patterns, new tasks (crossed)

| group | states | K | joint rescue | E[J] (label ref) | jr - E[J] | rescue undone | E[U] (label ref) | ru - E[U] |
|---|---|---|---|---|---|---|---|---|
| A6:nonexact:gptq_w4_d1 | 264 | 6 | 3.4 [0.4, 7.7] | 2.8 [1.5, 4.3] | +0.6 [-2.9, +4.5] | 2.6 [0.0, 6.3] | 4.7 [3.1, 6.4] | -2.1 [-4.7, +1.4] |
| A6:nonexact:rtn_w4 | 251 | 5 | 4.0 [0.7, 8.7] | 2.9 [1.4, 4.6] | +1.1 [-2.1, +5.0] | 5.2 [1.2, 10.4] | 4.7 [2.9, 6.7] | +0.5 [-2.8, +4.6] |
| A6:nonexact:pool | 464 | 5 | 3.4 [0.9, 6.8] | 2.9 [1.7, 4.3] | +0.5 [-2.0, +3.6] | 4.0 [1.5, 7.1] | 4.7 [3.2, 6.3] | -0.7 [-3.0, +1.9] |
| A6:all:gptq_w4_d1 | 498 | 6 | 1.8 [0.2, 4.0] | n/a | n/a | 1.4 [0.0, 3.4] | n/a | n/a |
| A6:all:rtn_w4 | 415 | 5 | 2.4 [0.5, 5.1] | n/a | n/a | 3.1 [0.7, 6.3] | n/a | n/a |
| A6:all:pool | 830 | 5 | 1.9 [0.5, 3.9] | n/a | n/a | 2.3 [0.8, 4.0] | n/a | n/a |
| strict:nonexact:gptq_w4_d1 | 215 | 5 | 3.7 [0.0, 8.6] | 2.8 [1.4, 4.4] | +0.9 [-2.9, +5.4] | 2.3 [0.0, 6.2] | 4.7 [2.9, 6.5] | -2.3 [-5.2, +1.5] |
| strict:nonexact:rtn_w4 | 144 | 3 | 4.2 [0.0, 9.7] | 3.5 [1.6, 5.6] | +0.7 [-2.9, +5.4] | 7.6 [2.2, 14.2] | 5.4 [3.3, 7.7] | +2.2 [-2.2, +7.5] |
| strict:nonexact:pool | 266 | 3 | 3.3 [0.7, 7.1] | 3.3 [1.7, 5.0] | +0.0 [-2.9, +3.5] | 4.6 [1.2, 9.5] | 4.9 [3.1, 6.9] | -0.3 [-3.1, +3.5] |
| strict:all:gptq_w4_d1 | 415 | 5 | 1.9 [0.0, 4.8] | n/a | n/a | 1.2 [0.0, 3.4] | n/a | n/a |
| strict:all:rtn_w4 | 249 | 3 | 2.4 [0.0, 5.6] | n/a | n/a | 4.4 [1.2, 8.4] | n/a | n/a |
| strict:all:pool | 498 | 3 | 1.8 [0.4, 3.8] | n/a | n/a | 2.6 [0.6, 5.2] | n/a | n/a |

## 6. Admission and checks

```
{
 "admitted_blocks": {
  "A6": {
   "gptq_w4_d1": [
    "f01",
    "f02",
    "f03",
    "f04",
    "f05",
    "f06"
   ],
   "rtn_w4": [
    "f01",
    "f02",
    "f03",
    "f05",
    "f06"
   ]
  },
  "strict": {
   "gptq_w4_d1": [
    "f02",
    "f03",
    "f04",
    "f05",
    "f06"
   ],
   "rtn_w4": [
    "f03",
    "f05",
    "f06"
   ]
  }
 },
 "check_vs_cited": {
  "gptq_w4_d1": {
   "A6 n_states [ours, cited]": [
    498,
    498
   ],
   "A6 n_nonexact": [
    264,
    264
   ],
   "A6 blocks": [
    [
     "f01",
     "f02",
     "f03",
     "f04",
     "f05",
     "f06"
    ],
    [
     "f01",
     "f02",
     "f03",
     "f04",
     "f05",
     "f06"
    ]
   ],
   "A6 offdiag all-states %": [
    12.05,
    12.05
   ],
   "strict n_states": [
    415,
    415
   ],
   "strict K": [
    5,
    5
   ]
  },
  "rtn_w4": {
   "A6 n_states [ours, cited]": [
    415,
    415
   ],
   "A6 n_nonexact": [
    251,
    251
   ],
   "A6 blocks": [
    [
     "f01",
     "f02",
     "f03",
     "f05",
     "f06"
    ],
    [
     "f01",
     "f02",
     "f03",
     "f05",
     "f06"
    ]
   ],
   "A6 offdiag all-states %": [
    12.29,
    12.29
   ],
   "strict n_states": [
    249,
    249
   ],
   "strict K": [
    3,
    3
   ]
  },
  "ok": true
 },
 "population": {
  "n_tasks": 83,
  "excluded_by_mask": [
   "airline|13",
   "airline|44"
  ]
 },
 "a6_zeroed_nonexact": {
  "A6:gptq_w4_d1": {
   "0010 zeroed BQ": 1
  },
  "A6:rtn_w4": {
   "0000 zeroed QB,QQ": 1,
   "0000 zeroed QQ": 1
  },
  "strict:gptq_w4_d1": {},
  "strict:rtn_w4": {}
 }
}
```

## Method

```
EXPLORATORY, POST HOC (review 2026-10-05, W3-W5 'Mistral evidence thin'): outcome classes on the second-family panel.
Panel: Mistral-Small-3.2-24B (m24), new-method panel A (analyze_newmethod loaders, 83-task frozen mask, strict blocks), cells GPTQ-W4 d1 and
RTN-W4. Views as in the paper: 'A6' = the primary (arm errors on the agent's own message scored Y = 0, then strict blocks; GPTQ 6 blocks, RTN 5)
and 'strict' = strict as preregistered (no A6; GPTQ 5, RTN 3). States are U2B ordinary states sampled on the BF16 trajectory, not Bank P first
divergences on the Q trajectory: BB is the recorded BF16 original (shared by both cells), a_B is the recorded BF16 action, a_Q is Q's proposal.
Arm naming: the panel already uses XY = (source of the action at the state, continuation controller), the same as outcome_classes.py and
analyze_dev.effects (A = Y_BB - Y_QB, G = Y_BQ - Y_QQ); its headline D_cc = Y_QB - Y_BB = -Delta_B. Bit order BB,BQ,QB,QQ is identical, so the
16 patterns and the named patterns carry over by arm label (checked per unit against the panel's own E: D_cc = -(y_BB - y_QB), offdiag).
Named patterns by arm label: joint rescue = 1000 (only BB succeeds); rescue undone = 0100, 0110. On this panel the reference is BB (BF16 all the
way), so 1000 reads 'only the all-BF16 arm succeeds' and the rescue reading of Bank P (Q baseline QQ) is not the natural one; shares are reported
by arm label only. Label reference (labels permuted uniformly given k): E[J] = P(k=1)/4, E[U] = P(k=1)/4 + P(k=2)/6; obs - ref per state.
Denominators: 'nonexact' (a_Q not token-identical to a_B; the analogue of divergent states; primary) and 'all' (exact states included: there
QB = BB and BQ = QQ are reused arms, so act_any = 0 by construction and only the continuation can change the outcome). The label reference
assumes the four arm labels are exchangeable, which fails on exact states (1000, 0100, 0110 are impossible there but get reference mass), so
E[J], E[U] and obs - ref are defined on 'nonexact' only; on 'all' rows they are biased downward by construction and printed n/a (JSON keeps them).
BB is the recorded original (no-op re-run on a 10% hash sample, protocol §2.3) and the other three arms are re-executions; under A6 only the
re-executed arms can be scored Y = 0 (counted per pattern in JSON a6_zeroed_nonexact). Patterns that single out BB (1000, 0111) carry this asymmetry.
Estimation exactly as outcome_classes.group: ratios of sums per cell, pool = equal-weight mean of the two cells on common blocks; fixed task pool:
t over per-block ratios (K < 10; block bootstrap kept in JSON); new tasks: crossed task x block bootstrap; B = 2000, seed 20261001.
Never opens analysis/fork/holdout/ (analyze_newmethod.no_holdout guards every path).
usage: python analysis/fork/mistral_patterns.py [--B 2000] [--selftest] -> analysis/fork/out/mistral_patterns_<UTC>.{md,json}
```

## Data sources (sha256)

- `manifests/fork/newmethod_panel_v1_m24.json` 53295b64fbcc7c4501ea8883aa34ce922a5ca0e23c5636c8bb1c4efe38e3ff4c
- `manifests/fork/newmethod_panel_v1_m24_mask_v1.json` b03a8a918959e3568315b1ae134f2902580e6af822d80beccb692729c2f82c81
- `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` 3b144592254a6bf91d70c5b9dbd919ee5cf0470ceecdd135d49d6685b921d06a
- `analysis/fork/out/newmethod_m24_20261004T024453Z.json` 2202da94750a3eecb95f7a74ad8a04363527ce557a6ef3f50c401e9db36c53e6
- `analysis/fork/analyze_newmethod.py` 2f8372ceb83b6bd7146a48b787de07b900fd224f14d93d476c18036c2cd1615e
- `analysis/fork/analyze_dev.py` 5851a57b1a7b6199a2e9ddb113b85df33faeefe49980ff03a158857e80fda372
- `analysis/fork/offdiag_null.py` 897d3b61c4e918c5c16bc633265b3e0ce82958d0817e9e88017d85e0159b3112
- `analysis/fork/outcome_classes.py` 689923fa4f488123490bfbf4643346666889219cb347e48a02a4c95eaba2da17
- `analysis/fork/mistral_patterns.py` 1f23d1cc92a40611d3dd075ebbb16ed3704e872ef3f3afdb140cd3b5a8fcdb9a
- `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f01/bank_rows.jsonl` f11996097e30622d22cbb8bb22c5b5b748f77dbcbbfbbaafad4297272b4566d1
- `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f02/bank_rows.jsonl` 2130aa2d388c6e25f99e476911799dae67564a434b76e925bb8170b7bd0dce1b
- `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f03/bank_rows.jsonl` dd33e52e007685613bc176f73d69ebfdd14b89dc7293d4a9187677cbce4a5e71
- `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f04/bank_rows.jsonl` b113341a0a88c1786563fa8e8e8ac592e359b0425e8f872836664428c120a4e6
- `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f05/bank_rows.jsonl` 5f109823b243cfb04b84d8b0d93fc67cf261083d97adc1c6996b483d85585daf
- `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f06/bank_rows.jsonl` 9db4dd8755f428ab6b1aed428ebadfa722cfc4dd743a04f4c28dd546c2d999d6
- `analysis/fork/newmethod/tau2/m24_rtn_w4/f01/bank_rows.jsonl` 9409d7f4000f33249f126efcbeb60cf2abf290ecebf3197ef87e02417f3aa00a
- `analysis/fork/newmethod/tau2/m24_rtn_w4/f02/bank_rows.jsonl` 4a9ce725ccc6eea37296e9f3b00f4b82e1012f0e6d1aa351b07358ad951d253a
- `analysis/fork/newmethod/tau2/m24_rtn_w4/f03/bank_rows.jsonl` f7a8c307d7545a489c5bb4aa3ccd340f60fe695c0c12e72656c74c22728ce755
- `analysis/fork/newmethod/tau2/m24_rtn_w4/f04/bank_rows.jsonl` 673205baddfcdffe0d863cbd3f626cc9744b3adf489990fd36ff3aaf302e276d
- `analysis/fork/newmethod/tau2/m24_rtn_w4/f05/bank_rows.jsonl` 44d2d0fb312e9c9c76cff41093257aa7069b3642ed4225b204941af45d30c457
- `analysis/fork/newmethod/tau2/m24_rtn_w4/f06/bank_rows.jsonl` c89bb35d15c0fe569ea3d71f32a7d42f59aa51bd4daeedb443ae67614dfb2e00
- units digest (cell, state_key, view, pattern) 8b647e66c784aea36471979ec799a7baebae653a21765f5fbbd42d24ee0b34b0
