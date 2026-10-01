**TL;DR** Common-population panel: G/r/d/M per cell on its own population vs the common 85-task retail/airline pool on the 20 retail / 20 airline blocks complete in all compared cells.

# Population panel (20261001T0224Z)

| cell | population | units | tasks | blocks | G | r | d | M |
|---|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | cell_specific | 1700 | 85 | 20 | -1.9 [-3.8, +0.1] | 6.8 | 8.7 | 15.5 |
| q4:gptq_w4_d1 | common_85_task_pool | 1700 | 85 | 20 | -1.9 [-3.8, +0.1] | 6.8 | 8.7 | 15.5 |
| q4:awq_w4 | cell_specific | 1699 | 85 | 20 | -0.3 [-2.2, +1.6] | 9.8 | 10.1 | 20.0 |
| q4:awq_w4 | common_85_task_pool | 1699 | 85 | 20 | -0.3 [-2.2, +1.6] | 9.8 | 10.1 | 20.0 |
| q4:kvq_int8 | cell_specific | 1870 | 85 | 22 | -0.3 [-1.7, +1.0] | 3.1 | 3.4 | 6.5 |
| q4:kvq_int8 | common_85_task_pool | 1700 | 85 | 20 | -0.1 [-1.3, +1.3] | 3.2 | 3.3 | 6.5 |
| q8:gptq_w4_d1 | cell_specific | 1860 | 165 | 20 | +2.8 [+1.4, +4.4] | 10.1 | 7.3 | 17.5 |
| q8:gptq_w4_d1 | common_85_task_pool | 1700 | 85 | 20 | +2.9 [+1.5, +4.5] | 10.4 | 7.5 | 17.9 |
| q8:awq_w4 | cell_specific | 1860 | 165 | 20 | +2.0 [-0.5, +4.3] | 11.1 | 9.1 | 20.3 |
| q8:awq_w4 | common_85_task_pool | 1700 | 85 | 20 | +1.9 [-0.6, +4.4] | 11.4 | 9.5 | 20.9 |
| q8:kvq_int8 | cell_specific | 1870 | 85 | 22 | +0.6 [-0.4, +1.6] | 4.3 | 3.7 | 8.1 |
| q8:kvq_int8 | common_85_task_pool | 1700 | 85 | 20 | +0.9 [+0.1, +1.8] | 4.5 | 3.6 | 8.1 |

Common complete blocks: retail ['f01', 'f02', 'f03', 'f04', 'f05', 'f06', 'f07', 'f08', 'f09', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'q3', 'q4', 'q5']; airline ['f01', 'f02', 'f03', 'f04', 'f05', 'f06', 'f07', 'f08', 'f09', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'q3', 'q4', 'q5'].
