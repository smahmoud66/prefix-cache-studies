# What the focused-LRU comparison establishes

**Current manuscript: [Exact Evaluation of Adaptive Prefix-Cache Continuations, v3.1](https://github.com/smahmoud66/prefix-cache-studies/blob/main/papers/evaluator/paper.pdf).** Giving both implementations the survival test and cross-exit score sharing left the original RANK-11 kernel with zero additional replays saved. Its mean complete native CPU was higher in six of eight comparisons. The contribution that survives is the exact specialization for atomic prefix paths and the accounting of where each shortcut helps. FOCUSED is our adaptation of [Touzeau et al.](https://valentintouzeau.fr/papers/POPL2019.pdf#page=11); the published analyzer was not timed.

## Where the 267,672 replays went

One pass through the 2,745 measured tool/agent cohorts at 128 blocks, **decision output**. Each row counts a historical pair evaluated from one distinct eligible exit. FULL replays every such evaluation when more than one exit is eligible.

| Treatment of that evaluation in RANK-11 and FOCUSED | Count |
|---|---:|
| Omitted: the pair contributes the same amount to every eligible exit, so it cannot change the decision | 26,391 |
| Scored directly by the survival test | 139,871 |
| Reused an already computed score for the same projected state | 54,800 |
| Replayed | 46,610 |
| **Total evaluations accounted for** | **267,672** |

The raw counter records **2,648 common pair terms**, once per pair within a cohort. Multiplying each cohort’s `common_elided` by its `candidate_states` before summing gives **26,391 pair-by-exit evaluations**. That leaves **241,281 certificate checks**. Of those, 139,871 succeeded and 101,410 reached the memo: 54,800 hits and 46,610 residual replays. Both identities hold for every cohort, for both strong implementations, in each recorded repetition. Absolute output must retain the value of a common term; that interface evaluates it once and credits each exit. [Scoring code](evaluator.cpp) · [Archived per-cohort records](timings) · [All eight cells](measurement_tables.md)

## What the clocks say

At 128 blocks on tool/agent decisions, turning on certification alone left 114,705 replays; sharing alone left 118,093. Both together removed **82.6% of FULL’s replays in this cell**. FULL to FOCUSED reduced complete native CPU from 281.63 to 66.59 µs (76.4%). At 32 blocks on tool/agent traffic the same CPU comparison gave 38.5% savings for decisions and 36.3% for absolute scores.

| Mean per 128-block tool/agent decision | RANK-11 | FOCUSED |
|---|---:|---:|
| Historical scoring and ranking CPU | 60.10 µs | 38.42 µs |
| Remaining native CPU (difference of means) | 28.90 µs | 28.17 µs |
| Complete native CPU | 89.00 µs | 66.59 µs |
| Local caller wall, including IPC and decoding | 133.35 µs | 110.80 µs |

Changing residual state representation reduced local caller wall by **16.9%** here. On conversation decisions, adding certification to sharing left replays unchanged at 32 blocks (151) and removed just 67 at 128 (223 to 156). But on conversation **absolute scores** at 128 blocks it cut replays from 12,182 to 6,975. The eight cells separate traffic, capacity and required output; the three repetitions on one M2 reuse the same exposed bins and describe machine variation only. [Timing definitions and full tables](measurement_tables.md) · [Matched contrasts](summary.json)

This readout uses the completed run. The [archived checkpoint](checkpoint.json) describes the earlier manuscript. The [public reproduction guide](../../docs/reproduce.md) describes how to verify the published measurements and obtain the code.
