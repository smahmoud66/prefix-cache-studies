# External validation of history-informed prefix-cache tie-breaking

**Decision — algorithmic acceleration is established. Scheduling transfer remains unsupported.** On previously unexamined Qwen/Bailian chat traffic, 4,643 of 5,200 cohorts offered multiple immediately optimal cache exits at the primary capacity. Historical scoring never changed the deterministic immediate choice. The API episode also tied, for a reason identifiable before replay: its released records provide no linked requests within which the frozen namespace would allow reuse. Neither episode provides an economic case for deploying the additional scorer over exact immediate ordering.

### Primary result by workload

Both policies received the same first 1,000 requests for FCFS warm-up. Each then served the next 20,000 requests continuously from its own cache. The primary comparison used 512-token blocks and 65,536 retained token positions.

| External episode | Exact immediate prefill | History-informed prefill | Positions saved | Saved/request | Relative saving | Mean local decision wall, immediate → history |
|---|---:|---:|---:|---:|---:|---:|
| A · chat | 43,320,479 | 43,320,479 | 0 | 0.000 | 0.000% | 3.43 → 23.98 µs |
| B · API automation | 17,516,341 | 17,516,341 | 0 | 0.000 | 0.000% | 3.14 → 24.20 µs |

**Chat.** The optimized policy reused 12,800 of the 43,333,279 input positions. Exact immediate ordering already saved the same 512 additional positions against FCFS. k-LPM and the simple history-frequency control matched the optimized policy on total prefill. The three registered randomized controls, in seed order, used 43,320,479, 43,317,407 and 43,316,895 positions. Two history-blind draws therefore did better by 3,072 and 3,584 positions. That shows exit choice could matter on this episode. Three draws do not establish an expected advantage for random scheduling. At native 16-token resolution and the same retained capacity, all three draws again beat OPT, while OPT tied IMM and RANK. At the smaller capacity, OPT changed three chat decisions at coarse resolution and thirteen at native resolution. The complete-episode effects and each of the four chronological window effects against IMM were zero.

**API automation.** All 21,000 selected records were distinct chat roots. With sharing limited to documented chat lineage, each request contributes its entire input length under every order. The measured total equaled the 17,516,341 input positions at both resolutions and capacities. This is a measured overhead comparison and a structural work tie. Whether independent API calls share reusable system prefixes within a real tenant remains unknown.

### Scope, provenance and causal design

The authors describe two sampled, production-derived streams from a Qwen serving cluster, with seconds since trace start, input/output lengths, chat and parent identifiers, turns, types, and salted hashes of individual 16-token blocks. Both complete files matched the authors’ Git LFS SHA-256 identities at revision `5f7439c51ec248a0c585f7d90a41a6f57773b912`. The project exposure check found an earlier search mentioning Bailian and found Mooncake as the previously replayed source. No previous evaluation of these Bailian files was found in the available records. [Authors’ pinned release](https://github.com/alibaba-edu/qwen-bailian-usagetraces-anon/tree/5f7439c51ec248a0c585f7d90a41a6f57773b912) · [Inspected documentation, license, checksums and exposure record](source/provenance.md)

The release has no tenant map. Before examining effects, we chose one capacity pool per file with separate prefix identities for each causally established chat lineage. Of the 21,000 chat records, 8,589 linked to an earlier parent. The adapter interns the complete preceding prefix and the exact incoming edge, using 32 consecutive source identifiers per coarse edge. Only complete blocks before the mandatory last token can hit. Input length supplies compulsory tail work. Output lengths, later lineage links, future requests and imagined service completions have no role in ordering. The anonymized hashes cannot certify original-token equality beyond the source hashing scheme. [Adapter](adapter.py) · [Source metadata](source/source_metadata.json)

The measured periods were 310.078–4,077.589 trace seconds for chat and 40.170–945.968 for API. Cohorts collected at most four requests over at most one second. State and history continued across reporting windows. Mean intentional collection waits were **272.4 ms** on chat and **68.2 ms** on API, with p95 waits of 872 and 224 ms and maxima of 1,000 and 706 ms. The primary optimized scheduler displaced a request at most two slots on chat and zero slots on API. All policies respected the three-slot bound. Two repetitions of each cell quantify local timing variability. The two traffic episodes are the external samples. The large request count does not supply a distribution over serving systems. [Prospective protocol](protocol.md) · [Frozen panel, policy and source digests](freeze.json)

### What the mechanism establishes

The method first minimizes the current cohort’s immediate missing blocks. Among eligible complete exits, it evaluates up to eight pairs drawn from the last sixteen completed cohorts using causal k-LPM replay. Incumbent preference and then lexicographic order settle equal scores. For a pair with relevant prefix identities U, retaining the identities **and absolute MRU ranks** of its residents preserves each possible historical hit and subsequent k-LPM choice. The direct score |U|−h applies when |U|+z≤C, with h resident relevant identities and z outsiders ahead of the deepest such resident. Other cases use the original exact continuation, with memoization confined to that pair and decision. This argument concerns exact historical scoring. An immediate minimum is guaranteed only from the current entry state.

The prior study verified 8,766 cohort–capacity cases and reduced mean native CPU at 128 blocks from 283.03 to 68.72 µs. Its largest acceleration occurred on conversation traffic, which saved zero prefill. On the tool/agent traffic that yielded savings it ran 3.19× faster than the reference, while costing 9.45× the native CPU of exact immediate ordering. We retained that result and used its digest-locked implementation. A new streaming harness uses the same compiled transition and matched in-process interface across all controls. Only the physical state-array extent increases in the 4,096-slot build. The external reference subset checked the first 16 measured cohorts after warm-up for all eight workload–representation–capacity cases. All 128 checks passed on action, incumbent, immediate work, complete exit and absolute historical score for reference versus optimized; decision-only optimization produced the same action and exit. Both full timing repetitions reproduced every recorded non-timing field. [Prior derivation and performance](../exact_tie_20261108/final_report.md) · [Native harness and controls](external_replay.cpp) · [Fixtures](engine_preflight.json) · [Independent review](result_audit.md)

### Practical tradeoff

Against exact immediate ordering, the primary optimized scorer cost an additional **106.85 ms** of measured local decision wall time over the chat episode and **105.27 ms** over API. With zero saved positions, no positive marginal prefill time can offset that extra serialized time. Against the weaker FCFS control on chat, 109.81 extra ms divided by 512 saved positions gives **214.48 µs per saved position**. Exact immediate ordering achieved the same saving. Attributing it to history would be incorrect. The appendix includes every baseline and the native-resolution thresholds.

These calculations compare ready-cohort input through committed cache/history and usable order within the native caller. They include current identity ingestion and history-index maintenance. Common tape decoding, warm-up, output formatting and post-decision diagnostics appear in process totals. The local CPU and wall clocks measure scheduling. A production accelerator can batch requests, overlap CPU work, and have context-dependent marginal prefill costs. Gate waiting cancels only between policies with this identical gate. Retained token positions likewise exclude active requests, decode state and other GPU memory. No live latency was measured.

At primary capacity, peak optimized process RSS was **5.66 MiB** on chat and **4.53 MiB** on API. At native resolution and the same token capacity it reached **120.94 and 97.52 MiB**. At the end of native-resolution chat, the index had **1,620,275 slots** including its sentinel, for **5,696 currently active identities**. Bounded demand history therefore does not bound all index storage in a continuous episode. The two observed zeroes against exact immediate leave the earlier workload-specific gain intact. They give no evidence of incremental scheduling value on these external episodes.

### Cost and reproduction

The eight integration processes and 128 timed processes consumed **148.05 child CPU-seconds**. The replay driver used 0.36 CPU-seconds and frozen numerical aggregation used 6.31. The two development builds used 8.20 CPU-seconds and their synthetic suites used 0.214. The full trace objects totaled **152,564,475 bytes**. The complete charge and separately identified estimates appear in the ledger receipt. GPU time, paid inference calls and PACE jobs were zero. [Resource reconciliation](costs.json) · [Per-run receipts](run_receipts.jsonl) · [Reproduction commands](reproduction.md) · [Machine-readable estimates and timing repetitions](summary.json)

### All policy trajectories

Complete measured-episode prefill, in positions. Warm-up work is shared across policies within each row. Each episode contains 20,000 measured requests.

| Traffic | Tokens/block × cache blocks | Warm-up | FCFS | K | IMM | OPT | RANK | RAND1729 | RAND314159 | RAND271828 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 512 × 128 | 1,680,425 | 43,320,991 | 43,320,479 | 43,320,479 | 43,320,479 | 43,320,479 | 43,320,479 | 43,317,407 | 43,316,895 |
| A | 512 × 32 | 1,693,225 | 43,332,767 | 43,332,767 | 43,332,767 | 43,332,767 | 43,332,767 | 43,332,767 | 43,332,767 | 43,332,767 |
| A | 16 × 4096 | 1,681,177 | 43,320,047 | 43,319,967 | 43,318,207 | 43,318,207 | 43,318,207 | 43,317,471 | 43,317,487 | 43,316,911 |
| A | 16 × 1024 | 1,693,081 | 43,331,951 | 43,331,951 | 43,331,951 | 43,331,951 | 43,331,951 | 43,331,951 | 43,331,951 | 43,331,951 |
| B | 512 × 128 | 832,444 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 |
| B | 512 × 32 | 832,444 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 |
| B | 16 × 4096 | 832,444 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 |
| B | 16 × 1024 | 832,444 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 | 17,516,341 |

### Costs and conditional break-even against each control

ΔP is control work minus optimized work. ΔT is optimized minus control wall time in the local caller, averaged over the two full measured repetitions. A positive ΔP implies the serialized break-even β = ΔT/ΔP in microseconds per saved position. A negative ratio would indicate a local time advantage even at zero marginal prefill cost. A dash means no positive prefill saving. Each timing cell gives mean / p95 / p99 / maximum per cohort in µs, pooled over the two repetitions. RSS is the larger per-process high-water mark. Process CPU/wall include input parsing, warm-up and diagnostic output. The underlying summary preserves separate repetitions.

<details><summary>A · 512 · 128 — timing, work contrasts and memory</summary>

| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |
|---|---:|---:|---:|---|---|---:|---:|
| FCFS | +512 | +109.81 | 214.4780 | 2.6 / 4.0 / 5.0 / 136.0 | 2.9 / 3.7 / 4.9 / 136.8 | 0.054 / 0.061 | 5.28 |
| K | +0 | +108.02 | — | 2.9 / 4.0 / 6.0 / 87.0 | 3.2 / 4.1 / 7.0 / 87.5 | 0.057 / 0.066 | 5.36 |
| IMM | +0 | +106.85 | — | 3.1 / 4.0 / 6.0 / 78.0 | 3.4 / 4.4 / 7.5 / 78.7 | 0.060 / 0.065 | 5.31 |
| OPT | +0 | +0.00 | — | 23.3 / 32.0 / 38.0 / 104.0 | 24.0 / 32.8 / 44.0 / 123.9 | 0.164 / 0.181 | 5.66 |
| RANK | +0 | +4.09 | — | 22.8 / 31.0 / 34.0 / 102.0 | 23.2 / 31.1 / 36.4 / 107.4 | 0.161 / 0.174 | 5.58 |
| RAND1729 | +0 | +4.78 | — | 22.5 / 29.0 / 33.0 / 105.0 | 23.1 / 30.0 / 36.6 / 107.4 | 0.178 / 0.192 | 5.47 |
| RAND314159 | -3,072 | +7.97 | — | 22.0 / 29.0 / 33.0 / 103.0 | 22.4 / 29.6 / 36.2 / 103.0 | 0.174 / 0.186 | 5.44 |
| RAND271828 | -3,584 | +11.14 | — | 21.4 / 29.0 / 32.0 / 109.0 | 21.8 / 29.2 / 35.8 / 108.7 | 0.169 / 0.197 | 5.38 |

</details>

<details><summary>A · 512 · 32 — timing, work contrasts and memory</summary>

| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |
|---|---:|---:|---:|---|---|---:|---:|
| FCFS | +0 | +38.97 | — | 1.8 / 3.0 / 4.0 / 77.0 | 2.1 / 2.7 / 4.1 / 77.9 | 0.051 / 0.055 | 5.28 |
| K | +0 | +37.67 | — | 1.9 / 3.0 / 6.0 / 82.0 | 2.4 / 3.4 / 11.2 / 104.8 | 0.051 / 0.062 | 5.31 |
| IMM | +0 | +37.22 | — | 2.1 / 3.0 / 5.0 / 98.0 | 2.4 / 3.2 / 7.2 / 170.5 | 0.054 / 0.061 | 5.33 |
| OPT | +0 | +0.00 | — | 7.8 / 12.0 / 22.0 / 81.0 | 9.6 / 14.7 / 33.2 / 4497.6 | 0.082 / 0.118 | 5.48 |
| RANK | +0 | -31.44 | — | 7.9 / 13.0 / 23.0 / 84.0 | 15.6 / 17.0 / 44.9 / 25008.9 | 0.085 / 0.168 | 5.67 |
| RAND1729 | +0 | +11.15 | — | 6.9 / 10.0 / 16.0 / 78.0 | 7.5 / 11.3 / 21.7 / 104.0 | 0.080 / 0.112 | 5.44 |
| RAND314159 | +0 | +12.77 | — | 6.7 / 9.0 / 13.0 / 76.0 | 7.1 / 8.9 / 19.2 / 124.4 | 0.078 / 0.097 | 5.42 |
| RAND271828 | +0 | +12.87 | — | 6.8 / 9.0 / 12.0 / 83.0 | 7.1 / 9.7 / 14.7 / 85.0 | 0.078 / 0.100 | 5.36 |

</details>

<details><summary>A · 16 · 4096 — timing, work contrasts and memory</summary>

| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |
|---|---:|---:|---:|---|---|---:|---:|
| FCFS | +1,840 | +3337.41 | 1813.8114 | 57.7 / 75.0 / 90.0 / 2763.0 | 58.4 / 76.9 / 92.1 / 2787.1 | 1.095 / 1.107 | 118.30 |
| K | +1,760 | +3329.75 | 1891.9014 | 59.0 / 77.0 / 94.0 / 3025.0 | 59.9 / 79.2 / 99.2 / 3050.2 | 1.097 / 1.115 | 118.30 |
| IMM | +0 | +3314.27 | — | 61.9 / 79.0 / 93.0 / 3819.0 | 62.8 / 80.8 / 97.5 / 3829.8 | 1.110 / 1.136 | 118.55 |
| OPT | +0 | +0.00 | — | 695.8 / 819.0 / 852.0 / 4243.0 | 700.2 / 829.5 / 872.4 / 4260.5 | 4.417 / 4.448 | 120.94 |
| RANK | +0 | +142.83 | — | 668.3 / 785.0 / 812.0 / 4149.0 | 672.7 / 795.3 / 831.8 / 4175.0 | 4.296 / 4.326 | 133.80 |
| RAND1729 | -736 | +357.14 | — | 627.5 / 737.0 / 766.0 / 4225.0 | 631.5 / 748.2 / 789.3 / 4226.1 | 4.859 / 4.912 | 120.72 |
| RAND314159 | -720 | +358.52 | — | 626.8 / 737.0 / 765.0 / 4061.0 | 631.2 / 748.8 / 789.5 / 4061.7 | 4.855 / 4.894 | 120.72 |
| RAND271828 | -1,296 | +340.24 | — | 630.9 / 738.0 / 766.0 / 4089.0 | 634.8 / 748.1 / 788.7 / 4128.8 | 4.882 / 4.918 | 120.69 |

</details>

<details><summary>A · 16 · 1024 — timing, work contrasts and memory</summary>

| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |
|---|---:|---:|---:|---|---|---:|---:|
| FCFS | +0 | +912.35 | — | 27.9 / 43.0 / 57.0 / 4027.0 | 28.5 / 44.7 / 61.0 / 4056.4 | 0.903 / 0.919 | 118.27 |
| K | +0 | +906.41 | — | 28.9 / 44.0 / 61.0 / 3382.0 | 29.7 / 45.7 / 68.4 / 3406.1 | 0.921 / 0.942 | 118.30 |
| IMM | +0 | +907.93 | — | 28.9 / 44.0 / 59.0 / 2915.0 | 29.4 / 44.9 / 60.0 / 2932.7 | 0.936 / 0.950 | 118.45 |
| OPT | +0 | +0.00 | — | 202.5 / 244.0 / 411.0 / 3219.0 | 204.0 / 249.2 / 425.0 / 3233.9 | 1.840 / 1.859 | 119.59 |
| RANK | +0 | +58.45 | — | 190.3 / 230.0 / 254.0 / 4808.0 | 192.8 / 235.3 / 280.0 / 4882.3 | 1.783 / 1.812 | 133.17 |
| RAND1729 | +0 | +140.10 | — | 174.5 / 215.0 / 240.0 / 3785.0 | 177.1 / 220.8 / 280.7 / 3963.3 | 1.864 / 1.894 | 119.66 |
| RAND314159 | +0 | +112.96 | — | 180.7 / 217.0 / 236.0 / 2866.0 | 182.3 / 221.2 / 248.7 / 2874.7 | 1.929 / 1.950 | 119.62 |
| RAND271828 | +0 | +131.27 | — | 177.1 / 215.0 / 233.0 / 3120.0 | 178.8 / 219.5 / 245.5 / 3122.8 | 1.888 / 1.910 | 119.62 |

</details>

<details><summary>B · 512 · 128 — timing, work contrasts and memory</summary>

| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |
|---|---:|---:|---:|---|---|---:|---:|
| FCFS | +0 | +106.75 | — | 2.4 / 3.0 / 6.0 / 103.0 | 2.8 / 3.5 / 11.0 / 112.2 | 0.041 / 0.056 | 4.28 |
| K | +0 | +106.20 | — | 2.6 / 4.0 / 5.0 / 95.0 | 3.0 / 3.6 / 7.3 / 94.8 | 0.043 / 0.048 | 4.25 |
| IMM | +0 | +105.27 | — | 2.8 / 4.0 / 6.0 / 78.0 | 3.1 / 3.8 / 7.9 / 83.9 | 0.045 / 0.054 | 4.27 |
| OPT | +0 | +0.00 | — | 23.5 / 29.0 / 34.0 / 108.0 | 24.2 / 31.0 / 41.0 / 229.5 | 0.148 / 0.161 | 4.53 |
| RANK | +0 | +0.51 | — | 23.7 / 29.0 / 33.0 / 102.0 | 24.1 / 29.6 / 36.0 / 102.2 | 0.149 / 0.159 | 4.47 |
| RAND1729 | +0 | +5.89 | — | 22.4 / 28.0 / 31.0 / 148.0 | 23.0 / 28.4 / 37.7 / 154.8 | 0.150 / 0.164 | 4.36 |
| RAND314159 | +0 | +4.19 | — | 22.9 / 28.0 / 32.0 / 170.0 | 23.4 / 28.6 / 35.5 / 170.9 | 0.153 / 0.169 | 4.38 |
| RAND271828 | +0 | +2.60 | — | 23.1 / 28.0 / 32.0 / 98.0 | 23.7 / 29.1 / 38.6 / 97.8 | 0.156 / 0.169 | 4.41 |

</details>

<details><summary>B · 512 · 32 — timing, work contrasts and memory</summary>

| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |
|---|---:|---:|---:|---|---|---:|---:|
| FCFS | +0 | +31.20 | — | 1.6 / 2.0 / 4.0 / 67.0 | 1.9 / 2.3 / 3.8 / 67.5 | 0.036 / 0.047 | 4.27 |
| K | +0 | +31.02 | — | 1.6 / 2.0 / 4.0 / 68.0 | 1.9 / 2.4 / 3.8 / 68.2 | 0.036 / 0.047 | 4.27 |
| IMM | +0 | +30.59 | — | 1.7 / 3.0 / 5.0 / 126.0 | 2.0 / 2.5 / 7.2 / 126.6 | 0.037 / 0.048 | 4.28 |
| OPT | +0 | +0.00 | — | 7.6 / 10.0 / 14.0 / 149.0 | 8.1 / 11.0 / 20.5 / 149.7 | 0.067 / 0.079 | 4.53 |
| RANK | +0 | +0.90 | — | 7.5 / 10.0 / 12.0 / 86.0 | 7.9 / 10.2 / 16.0 / 115.7 | 0.068 / 0.075 | 4.56 |
| RAND1729 | +0 | +0.23 | — | 7.6 / 10.0 / 14.0 / 85.0 | 8.1 / 10.3 / 18.5 / 86.8 | 0.071 / 0.079 | 4.36 |
| RAND314159 | +0 | +3.62 | — | 7.0 / 9.0 / 12.0 / 102.0 | 7.4 / 9.5 / 16.6 / 102.5 | 0.066 / 0.080 | 4.36 |
| RAND271828 | +0 | +3.33 | — | 7.1 / 9.0 / 12.0 / 88.0 | 7.5 / 9.5 / 14.7 / 88.0 | 0.068 / 0.083 | 4.30 |

</details>

<details><summary>B · 16 · 4096 — timing, work contrasts and memory</summary>

| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |
|---|---:|---:|---:|---|---|---:|---:|
| FCFS | +0 | +3517.98 | — | 54.8 / 66.0 / 81.0 / 3767.0 | 55.6 / 68.4 / 85.7 / 3773.2 | 0.615 / 0.626 | 94.95 |
| K | +0 | +3508.93 | — | 56.7 / 69.0 / 82.0 / 3410.0 | 57.4 / 70.8 / 85.6 / 3420.4 | 0.628 / 0.637 | 94.94 |
| IMM | +0 | +3491.55 | — | 60.0 / 69.0 / 82.0 / 3064.0 | 60.9 / 71.2 / 86.1 / 3078.8 | 0.647 / 0.657 | 95.14 |
| OPT | +0 | +0.00 | — | 754.6 / 805.0 / 835.0 / 6021.0 | 759.2 / 816.0 / 858.1 / 6034.0 | 4.119 / 4.148 | 97.52 |
| RANK | +0 | +72.67 | — | 739.8 / 784.0 / 812.0 / 6137.0 | 744.6 / 795.4 / 833.2 / 6162.9 | 4.048 / 4.080 | 105.75 |
| RAND1729 | +0 | +319.12 | — | 691.0 / 739.0 / 767.0 / 5617.0 | 695.4 / 750.8 / 788.7 / 5626.0 | 4.500 / 4.531 | 96.05 |
| RAND314159 | +0 | +307.82 | — | 693.3 / 739.0 / 767.0 / 5498.0 | 697.6 / 750.5 / 788.9 / 5508.1 | 4.515 / 4.544 | 97.09 |
| RAND271828 | +0 | +331.61 | — | 686.3 / 738.0 / 765.0 / 6973.0 | 692.9 / 750.7 / 807.0 / 7032.9 | 4.469 / 4.515 | 97.11 |

</details>

<details><summary>B · 16 · 1024 — timing, work contrasts and memory</summary>

| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |
|---|---:|---:|---:|---|---|---:|---:|
| FCFS | +0 | +948.50 | — | 23.1 / 32.0 / 44.0 / 3079.0 | 23.8 / 33.7 / 46.9 / 3115.8 | 0.440 / 0.462 | 94.41 |
| K | +0 | +942.53 | — | 24.4 / 34.0 / 47.0 / 2981.0 | 25.0 / 34.6 / 48.7 / 3001.6 | 0.453 / 0.461 | 94.44 |
| IMM | +0 | +940.37 | — | 24.9 / 33.0 / 45.0 / 4979.0 | 25.4 / 34.0 / 46.3 / 4983.1 | 0.460 / 0.472 | 94.53 |
| OPT | +0 | +0.00 | — | 211.5 / 234.0 / 255.0 / 5023.0 | 213.5 / 239.9 / 268.2 / 5022.7 | 1.390 / 1.408 | 97.00 |
| RANK | +0 | +53.38 | — | 201.2 / 225.0 / 244.0 / 4764.0 | 202.8 / 230.5 / 254.5 / 4914.6 | 1.333 / 1.354 | 105.22 |
| RAND1729 | +0 | +103.36 | — | 190.6 / 214.0 / 236.0 / 4823.0 | 192.8 / 219.8 / 259.8 / 4853.6 | 1.453 / 1.472 | 96.58 |
| RAND314159 | +0 | +74.01 | — | 197.3 / 215.0 / 231.0 / 5323.0 | 198.7 / 219.8 / 240.2 / 5347.0 | 1.504 / 1.520 | 95.55 |
| RAND271828 | +0 | +89.73 | — | 193.7 / 215.0 / 231.0 / 3574.0 | 195.5 / 219.7 / 243.1 / 3577.0 | 1.480 / 1.497 | 96.56 |

</details>

### Mechanism on the optimized trajectory

A tied cohort has multiple immediately optimal orders. Distinct exits count full MRU states. Changes compare OPT with its deterministic immediate incumbent **from that same entry state**. Window effects compare the separate continuous OPT and IMM trajectories, so a later window can inherit earlier choices. The historical index grows with the IDs seen over the episode. Allocated bytes include spare vector capacity.

| Traffic / block / slots | Tied cohorts / multiple exits | Distinct exits, sum / max | Changed orders (residency / recency only) | Replays / direct scores / memo hits | Index slots after warm → end (active at end) | Index / full history / pair memo peak (KiB) | ΔP by chronological window |
|---|---:|---:|---:|---:|---|---|---|
| A / 512 / 128 | 5,169 / 4,643 | 43,988 / 24 | 0 (0 / 0) | 21 / 939 / 25 | 2,215 → 44,906 (152) | 136.0 / 139.8 / 0.4 | +0 / +0 / +0 / +0 |
| A / 512 / 32 | 5,169 / 4,643 | 43,442 / 24 | 3 (1 / 2) | 171 / 541 / 270 | 2,215 → 44,636 (152) | 136.0 / 139.7 / 1.1 | +0 / +0 / +0 / +0 |
| A / 16 / 4096 | 5,169 / 5,169 | 113,567 / 24 | 0 (0 / 0) | 69 / 3,200 / 131 | 83,113 → 1,620,275 (5,696) | 4564.0 / 4621.8 / 4.4 | +0 / +0 / +0 / +0 |
| A / 16 / 1024 | 5,169 / 5,169 | 112,368 / 24 | 13 (3 / 10) | 590 / 1,701 / 1,157 | 83,091 → 1,610,932 (5,696) | 4476.0 / 4533.1 / 42.7 | +0 / +0 / +0 / +0 |
| B / 512 / 128 | 5,000 / 3,367 | 21,563 / 24 | 0 (0 / 0) | 0 / 0 / 0 | 1,207 → 26,639 (80) | 96.0 / 98.8 / 0.0 | +0 / +0 / +0 / +0 |
| B / 512 / 32 | 5,000 / 3,367 | 21,538 / 24 | 0 (0 / 0) | 0 / 0 / 0 | 1,207 → 26,329 (80) | 96.0 / 98.6 / 0.0 | +0 / +0 / +0 / +0 |
| B / 16 / 4096 | 5,000 / 5,000 | 120,000 / 24 | 0 (0 / 0) | 0 / 0 / 0 | 51,475 → 1,135,767 (3,395) | 3824.0 / 3849.7 / 0.0 | +0 / +0 / +0 / +0 |
| B / 16 / 1024 | 5,000 / 5,000 | 119,814 / 24 | 0 (0 / 0) | 0 / 0 / 0 | 51,475 → 1,125,501 (3,395) | 3824.0 / 3848.4 / 0.0 | +0 / +0 / +0 / +0 |

Per-cohort orders, displacement, eligibility counts, and per-repetition resource records are available in the [raw replay outputs](../../data/external-timing-rows.tar.gz) and [numerical summary](summary.json). Counts describe the observed mechanism. They cannot identify how much of the episode effect was caused by changes in residency versus recency.

**Final judgment.** Retain the exact evaluator and the earlier measured acceleration. On the external chat episode, even abundant immediately optimal exits yielded no incremental saving over the immediate scheduler. The structurally isolated API episode adds an overhead measurement. Together they leave a deployment benefit unsupported.
