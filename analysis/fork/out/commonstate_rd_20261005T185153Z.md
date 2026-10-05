# Common-state BF16 vs Q' rescue/damage decomposition (EXPLORATORY, POST HOC; 20261005T185153Z)

**TL;DR** EXPLORATORY, POST HOC. q8: net K = +0.9 pp (avg over c) = extra rescues +0.3 minus extra damages -0.6 pp; unresolved: neither component separated from zero (c = d1: unresolved: neither component separated from zero). Components: c = bf16: XR equivalent within ±3 pp (TOST), XD equivalent within ±3 pp (TOST); c = d1: XR equivalent within ±3 pp (TOST), XD equivalent within ±3 pp (TOST); c = avg: XR equivalent within ±3 pp (TOST), XD equivalent within ±3 pp (TOST). Note: the ±3 pp margin is large relative to the component rates themselves (2.9 to 5.3 pp); equivalence within it still allows BF16 up to 1.6x to 1.7x the rescues of Q' (r_Q' + margin over r_Q'), or no extra rescues. q4: net K = -1.8 pp (avg over c) = extra rescues -0.9 minus extra damages +0.9 pp; unresolved: neither component separated from zero (c = d1: unresolved: neither component separated from zero). Components: c = bf16: XR not resolved, XD not resolved; c = d1: XR not resolved, XD not resolved; c = avg: XR not resolved, XD not resolved. Note: the ±3 pp margin is large relative to the component rates themselves (2.4 to 7.1 pp); no component reached equivalence here.

Protocol `docs/insights/COMMONSTATE_RD_POSTHOC.md`. Script `analysis/fork/commonstate_rd.py` sha256 `5805d49d6445410eb2801285e192e6ebdb544b2d8be640ab3347efaea5f57764`, git `224c6cea37850f6aa673f49d9689a66bbc152bad`, B = 2000, seed 20261002. Q' = W4-d2; baseline = d1 action under the same continuation c. Intervals: t over block means (df = k-1) and task-cluster bootstrap (no crossed bootstrap in this machinery). Point estimates of K, Kbar and published r/d reproduced exactly (asserted).
Inference is to these 85 tasks (same-task; the bootstrap resamples tasks with blocks fixed); no new-task (crossed) interval is reported. These are hindsight outcome contrasts on fixed states, not a selection rule or router. Point splits of an unresolved K are descriptive only.

## q8: n = 510, k = 6, tasks = 85, per block {'f01': 85, 'f02': 85, 'f03': 85, 'f04': 85, 'f05': 85, 'f06': 85}

| c | r_B | r_Q' | d_B | d_Q' | net_B | net_Q' | XR = r_B-r_Q' (t95; boot95) | XD = d_B-d_Q' (t95; boot95) | XN = K (t95; boot95) | reading XR / XD / overall |
|---|---|---|---|---|---|---|---|---|---|---|
| bf16 | 5.3 | 4.7 | 3.7 | 3.9 | 1.6 | 0.8 | +0.6 ([-1.1, +2.3]; [-1.0, +2.4]) | -0.2 ([-1.6, +1.2]; [-1.8, +1.4]) | +0.8 ([-1.8, +3.3]; [-1.8, +3.3]) | equivalent within ±3 pp (TOST) / equivalent within ±3 pp (TOST) / unresolved: neither component separated from zero |
| d1 | 4.1 | 4.1 | 2.9 | 3.9 | 1.2 | 0.2 | +0.0 ([-3.1, +3.1]; [-1.6, +1.8]) | -1.0 ([-3.1, +1.1]; [-2.4, +0.2]) | +1.0 ([-3.5, +5.4]; [-1.2, +3.1]) | equivalent within ±3 pp (TOST) / equivalent within ±3 pp (TOST) / unresolved: neither component separated from zero |
| avg over c (Kbar-style) | 4.7 | 4.4 | 3.3 | 3.9 | 1.4 | 0.5 | +0.3 ([-2.0, +2.6]; [-1.2, +1.8]) | -0.6 ([-1.5, +0.4]; [-1.6, +0.4]) | +0.9 ([-2.0, +3.8]; [-1.0, +2.9]) | equivalent within ±3 pp (TOST) / equivalent within ±3 pp (TOST) / unresolved: neither component separated from zero |

Counts (unweighted) of flips relative to d1, per continuation: {"bf16": {"Y1=0": {"both": 16, "BF16 only": 11, "Q' only": 8, "neither": 327}, "Y1=1": {"both": 14, "BF16 only": 5, "Q' only": 6, "neither": 123}}, "d1": {"Y1=0": {"both": 10, "BF16 only": 11, "Q' only": 11, "neither": 331}, "Y1=1": {"both": 11, "BF16 only": 4, "Q' only": 9, "neither": 123}}}

Pocock 97% (reference only): XR[bf16] t97 [-1.4, +2.6] boot97 [-1.4, +2.5]; XD[bf16] t97 [-1.9, +1.5] boot97 [-2.0, +1.6]; XR[d1] t97 [-3.7, +3.7] boot97 [-1.8, +1.8]; XD[d1] t97 [-3.5, +1.5] boot97 [-2.5, +0.4]

## q4: n = 170, k = 2, tasks = 85, per block {'f02': 85, 'f03': 85}

| c | r_B | r_Q' | d_B | d_Q' | net_B | net_Q' | XR = r_B-r_Q' (t95; boot95) | XD = d_B-d_Q' (t95; boot95) | XN = K (t95; boot95) | reading XR / XD / overall |
|---|---|---|---|---|---|---|---|---|---|---|
| bf16 | 2.4 | 4.1 | 7.1 | 6.5 | -4.7 | -2.4 | -1.8 ([-9.2, +5.7]; [-5.3, +0.6]) | +0.6 ([-21.8, +23.0]; [-1.8, +2.9]) | -2.4 ([-17.3, +12.6]; [-6.5, +1.2]) | not resolved / not resolved / unresolved: neither component separated from zero |
| d1 | 2.9 | 2.9 | 4.7 | 3.5 | -1.8 | -0.6 | +0.0 ([-14.9, +14.9]; [-2.9, +2.9]) | +1.2 ([-13.8, +16.1]; [-1.8, +4.7]) | -1.2 ([-1.2, -1.2]; [-5.9, +3.5]) | not resolved / not resolved / unresolved: neither component separated from zero |
| avg over c (Kbar-style) | 2.6 | 3.5 | 5.9 | 5.0 | -3.2 | -1.5 | -0.9 ([-12.1, +10.3]; [-3.2, +1.2]) | +0.9 ([-17.8, +19.6]; [-1.5, +3.5]) | -1.8 ([-9.2, +5.7]; [-5.6, +1.8]) | not resolved / not resolved / unresolved: neither component separated from zero |

k = 2 (df = 1): t intervals are uninformative; readings rest on the bootstrap. t degenerate (zero spread across blocks): XN[d1].

Counts (unweighted) of flips relative to d1, per continuation: {"bf16": {"Y1=0": {"both": 3, "BF16 only": 1, "Q' only": 4, "neither": 96}, "Y1=1": {"both": 9, "BF16 only": 3, "Q' only": 2, "neither": 52}}, "d1": {"Y1=0": {"both": 2, "BF16 only": 3, "Q' only": 3, "neither": 99}, "Y1=1": {"both": 3, "BF16 only": 5, "Q' only": 3, "neither": 52}}}

## Inputs (sha256)

- `analysis/fork/commonstate/q8/gate/d2_bf16/cs_summary.json` 5fd4696cdcb34315dd4b8b05e8cc1b856a93ce802d6025f57c61f169f80cffca
- `analysis/fork/commonstate/q8/gate/d2_d1/cs_summary.json` 3f6bbfda36cc617e2d7026e44bca3592eb3f62082707e1bac144cc356c23a4a0
- `analysis/fork/bank_u/q8_gptq_w4_d1/f01/bank_rows.jsonl` a8433f8b800f9820f20cddddd9fd998a76c4a734c16aafa71133dd55af4a7b49
- `analysis/fork/commonstate/q8/panel/d2_bf16/f01/cs_rows.jsonl` 2df8c3670627ed343dc3c8931c08c1243aafdac586eb2d136c0d78cca460b646
- `analysis/fork/commonstate/q8/panel/d2_bf16/f01/cs_summary.json` f767931390ea1abeca325c1cdd4b0a3c938d532df7ce568a94c7f37f67a397b5
- `analysis/fork/commonstate/q8/panel/d2_d1/f01/cs_rows.jsonl` 4b8bba023b67c579689c8fef1d98b41ea57438d03b924f511f8cd79ec690603b
- `analysis/fork/commonstate/q8/panel/d2_d1/f01/cs_summary.json` 066d65cbc1446bce54ee6764845ca3222a433508dca6352b48437e48cf77a692
- `analysis/fork/bank_u/q8_gptq_w4_d1/f02/bank_rows.jsonl` 444d6ae5639c7439a637bb565d070f371bbf51f7f0164a5896d8892740d4b27a
- `analysis/fork/commonstate/q8/panel/d2_bf16/f02/cs_rows.jsonl` b49aed7f3ebb271798d6eea21540284c3c6823778b5c9eb4698609d509f76778
- `analysis/fork/commonstate/q8/panel/d2_bf16/f02/cs_summary.json` f33a14be53c34b8c4c20250ffa085efd0ff0907bfca60a60ad3d8d3015561525
- `analysis/fork/commonstate/q8/panel/d2_d1/f02/cs_rows.jsonl` f8c40b3d2730ed319fdedb3d891bef35b2d76bf5d8dbf6569867b2d4c3733614
- `analysis/fork/commonstate/q8/panel/d2_d1/f02/cs_summary.json` bb96d212bae03a6d5c0fe56424bed9c3fc009cc0e9008742c31d49f23a601017
- `analysis/fork/bank_u/q8_gptq_w4_d1/f03/bank_rows.jsonl` 4d2aa5dd06ee50e18fc53633619759010e33c3a3e221bf62a78eecf3758161b3
- `analysis/fork/commonstate/q8/panel/d2_bf16/f03/cs_rows.jsonl` a86e9011e5def973b4448d193c2777f58aba059bcfefb8626651b309c7aee3ff
- `analysis/fork/commonstate/q8/panel/d2_bf16/f03/cs_summary.json` a685aeba93fd5838af21d499500d11f988fdb7a2cc259b9a87523a5bfdc3e49b
- `analysis/fork/commonstate/q8/panel/d2_d1/f03/cs_rows.jsonl` 70fcea70950f32136bf5d049568e65fbb7e4b55594f35d19ac71fae9a5c0f3e3
- `analysis/fork/commonstate/q8/panel/d2_d1/f03/cs_summary.json` 654fff901494e2fc281279f4726d2befe8d771c91a7931c32ef70a1b3062a407
- `analysis/fork/commonstate/q8/ref_d1/f04/bank_rows.jsonl` 16e3e6bd446f8a7077e0df5fe845d99d86c54db72401ec4bf3b75067b668d817
- `analysis/fork/commonstate/q8/panel/d2_bf16/f04/cs_rows.jsonl` 8f7a16e11d70417429e9961eeefaa49c989f1fec37440b58a76c7febe744d029
- `analysis/fork/commonstate/q8/panel/d2_bf16/f04/cs_summary.json` d3d61740c909a09b0b3adaab9c7e6102ce7538a8b5318cf40ed3acf259d24a1f
- `analysis/fork/commonstate/q8/panel/d2_d1/f04/cs_rows.jsonl` ec0ef93a2cdcef321e9f15279dc479b2589be5e5a2f3f03264df7f92aa1ddebd
- `analysis/fork/commonstate/q8/panel/d2_d1/f04/cs_summary.json` a27fa196742d49eccb38857d020e1293d25b7d50bc43924559d21ee4126811d7
- `analysis/fork/commonstate/q8/ref_d1/f05/bank_rows.jsonl` baaa83d4812f0a3eafd1a63a5f7872381d97fc8f514070cf45d9d0908283082d
- `analysis/fork/commonstate/q8/panel/d2_bf16/f05/cs_rows.jsonl` 39932881b1e8edf36af7f77a0089041b1756b7e4ec2e46ef78394a29fc9869d4
- `analysis/fork/commonstate/q8/panel/d2_bf16/f05/cs_summary.json` e411233e3bf8c61c875e38dda0fb80224b56e6dbda1319fbd1bd9939ce00510e
- `analysis/fork/commonstate/q8/panel/d2_d1/f05/cs_rows.jsonl` 56cf0a56fdfd4d806bd78e8ed0bdcc1da44d5a0a24e941a454af5854533678a8
- `analysis/fork/commonstate/q8/panel/d2_d1/f05/cs_summary.json` 29861cc199652f15a463531b44380fce88f432d5e1b7812b616139f06cde580e
- `analysis/fork/commonstate/q8/ref_d1/f06/bank_rows.jsonl` 84f03d445816b1afb57774cf54241d9eb6e9d22f48a94eb194af3e5235b60500
- `analysis/fork/commonstate/q8/panel/d2_bf16/f06/cs_rows.jsonl` fabea53228b518a7f79c73f2ddf2b99e58f235be93f00336bd39908018b7826b
- `analysis/fork/commonstate/q8/panel/d2_bf16/f06/cs_summary.json` 3e475ec38f0c8818cf8047cda82adfebbe85d7c5a9a070e65073734eb5616330
- `analysis/fork/commonstate/q8/panel/d2_d1/f06/cs_rows.jsonl` 99b50f36b8523b606856ee5a4a8df9614918205148e23ec031036c3068f60d88
- `analysis/fork/commonstate/q8/panel/d2_d1/f06/cs_summary.json` c5630a53f2a1af2cf51d72449a71984617a64831060c08581e5d05f9e58c821a
- `analysis/fork/out/commonstate_q8ext_20261003T231159Z.json` 8395663e73b00cc33dd42b06d0518453fc90e334499cced29bf9e047bd56b165
- `analysis/fork/commonstate/q4/gate/d2_bf16/cs_summary.json` 0b0182f0bc384dd564f1ac11ab5beb57b813ba1fe7c9a6bd64ce36a54f6edbd0
- `analysis/fork/commonstate/q4/gate/d2_d1/cs_summary.json` a73eac33e1879685982d79a6f24f552819591ef077902a7ae81db167213a7df7
- `analysis/fork/bank_u/q4_gptq_w4_d1/f01/bank_rows.jsonl` 8ed671217536a7fb3227ce6f3292165b3ed6245aa9de370d577366032e9c8ca2
- `analysis/fork/commonstate/q4/panel/d2_bf16/f01/cs_rows.jsonl` a84eb183b6afea0c969c3785fe8b7db2d63880edaef596c9ca265abaeb47086c
- `analysis/fork/commonstate/q4/panel/d2_bf16/f01/cs_summary.json` 428dbc216185ffc78e4df03de9ef973c04d4719f75237a8c049290b48494fec2
- `analysis/fork/commonstate/q4/panel/d2_d1/f01/cs_rows.jsonl` a80346cc5021e599ba4f5ea4eb8499b8fd63f044c888a78a77add35a3a33dcce
- `analysis/fork/commonstate/q4/panel/d2_d1/f01/cs_summary.json` 1041e8756c52a6ad23043283b37392cc6d95485a85688d72591e2d1b62ef84e3
- `analysis/fork/bank_u/q4_gptq_w4_d1/f02/bank_rows.jsonl` 2eaeaf91db86cfd2736bca8b01cfbc18d09521f7f8136ccfb3aeba9d3bf0ebf2
- `analysis/fork/commonstate/q4/panel/d2_bf16/f02/cs_rows.jsonl` 28f55fe5f8889762f2697f70d2dc54c1087e4763d148b999e1cc8e808678ee3a
- `analysis/fork/commonstate/q4/panel/d2_bf16/f02/cs_summary.json` fda90b167a13eed2e56e82a46507ec72203d78f9cf512cdb0a214c6b2766fb60
- `analysis/fork/commonstate/q4/panel/d2_d1/f02/cs_rows.jsonl` a9bdae65ca16ed26f5fd729d6381ab5f45b5e6c8a60f7c462ce58e4470433f1c
- `analysis/fork/commonstate/q4/panel/d2_d1/f02/cs_summary.json` 7544d10bf4a1a1704310a1770cf60554f88c3d0ec49c7693818d6c74a8dead9d
- `analysis/fork/bank_u/q4_gptq_w4_d1/f03/bank_rows.jsonl` 4e7458ce577af63047147278d672d19504d85e23180337026addbd70b135cc68
- `analysis/fork/commonstate/q4/panel/d2_bf16/f03/cs_rows.jsonl` 75197da78b5db6b66631bc3b42a65d26112756f691accf7c0e2c8973e165b9ae
- `analysis/fork/commonstate/q4/panel/d2_bf16/f03/cs_summary.json` b4aa55d977f9e2dd74e7043ac38d0837578c7b11d0d18d412611828746575cd6
- `analysis/fork/commonstate/q4/panel/d2_d1/f03/cs_rows.jsonl` 26dc1acc907dd4d37c2dc3f2ccfdf03d4dcb90c0b4783eb030f2eb84a3a5181d
- `analysis/fork/commonstate/q4/panel/d2_d1/f03/cs_summary.json` 1c3d00b0a8283ad4e9b0d7f27b051f08eef30dd2438e6973521b24b4622dabcb
- `analysis/fork/out/commonstate_q4_20261004T001159Z.json` 7398bb23127a79c17d0b51578205c5282ff6a04919386158d60fd6f953809361
