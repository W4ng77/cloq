# A7 re-runs: per-arm report (effect-blind; NEWMETHOD A7.4, A7.E2)

**TL;DR** ok = False; problems: ['a7_rr1_q8_kivi_k2v2_f03: running', 'a7_rr1_q8_kivi_k4v4_f01: running']

| cell | block | state | arm | A7.2 class | status | longest request (s) | state id. | shadow id. | no-op (BB) |
|---|---|---|---|---|---|---|---|---|---|
| kivi_k2v2 | f01 | 1bdc433905484e8d | QQ | timeout_cause_not_established | recovered | 307.6 | True | True | – |
| kivi_k2v2 | f02 | 02dde73dfe90f6f6 | QQ | timeout_cause_not_established | recovered | 313.6 | True | True | – |
| kivi_k2v2 | f02 | 0f51e0c84a65cf7f | BQ | timeout_cause_not_established | recovered | 524.7 | True | True | – |
| kivi_k2v2 | f02 | 21f3a2013895739f | BQ | timeout_cause_not_established | recovered | 197.2 | True | True | – |
| kivi_k2v2 | f02 | e553e7972e96416c | BQ | timeout_cause_not_established | recovered | 158.8 | True | True | – |
| spinquant_w4a4 | f01 | 197f61e9d1573be3 | QB | other | recovered | 14.4 | True | True | – |
| spinquant_w4a4 | f01 | 1bdc433905484e8d | QQ | other | recovered | 34.3 | True | True | – |
| spinquant_w4a4 | f01 | 27b52ac1d2cc9ec6 | QQ | other | recovered | 3.0 | True | True | – |
| spinquant_w4a4 | f01 | 2b7e8183406b2144 | QB | other | recovered | 19.4 | True | True | – |
| spinquant_w4a4 | f01 | 33b049d3a313a14f | QQ | other | recovered | 10.8 | True | True | – |
| spinquant_w4a4 | f01 | 9749f30f7ffd3c41 | BQ | other | recovered | 12.3 | True | True | – |
| spinquant_w4a4 | f01 | 9749f30f7ffd3c41 | QQ | other | recovered | 4.8 | True | True | – |
| spinquant_w4a4 | f01 | a42e6f98f2baa960 | QQ | other | recovered | 26.4 | True | True | – |
| spinquant_w4a4 | f01 | f01a1f21e0c452e7 | QQ | other | recovered | 13.7 | True | True | – |

| task | queue | arms | servers = a7_expect | arms = spec | one rr dir |
|---|---|---|---|---|---|
| a7_rr1_q8_kivi_k2v2_f01 | done | 1 | True | True | True |
| a7_rr1_q8_kivi_k2v2_f02 | done | 4 | True | True | True |
| a7_rr1_q8_spinquant_w4a4_f01 | done | 9 | True | True | True |
| a7_rr1_q8_kivi_k2v2_f03 | running | 5 | – | – | – |
| a7_rr1_q8_kivi_k4v4_f01 | running | 12 | – | – | – |
