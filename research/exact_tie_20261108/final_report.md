# An exact, cheaper evaluator for history-informed tie-breaking

**Judgment.** An exact implementation emerged. At 128 retained cache blocks it reduced reference tie-only CPU from **283.03 to 68.72 μs per cohort** (4.12×), and end-to-end local decision time from **332.13 to 113.18 μs** (2.93×). It reproduced every selected order and all **244,736 pooled prefill positions saved** over exact immediate ordering in the previously reported workload. Matched native exact-immediate ordering took **9.74 μs CPU** and k-LPM took **9.24 μs**. The optimization materially lowers the cost of choosing the historical policy; a user paying solely for cheap scheduling would still favor the immediate controls.

### Method and correctness

The scheduler first computes the exact immediate minimum with the parent incumbent priority. It considers all orders attaining that minimum. Among equal complete exits it keeps the preferred representative. It then chooses the least summed historical continuation work over up to eight completed chronological two-cohort pairs. Each pair starts afresh from that exit and follows k-LPM/LRU. Exact objective ties favor the immediate incumbent, then lexicographic arrival order. The previous fallback, admission, displacement, capacity and partial-block conventions are inherited from the frozen policy. Only the evaluation of this finite objective changes. The immediate minimum alone cannot eliminate other co-optimal exits.

For one historical pair, let U be the union of its capped prefix-node identities. Replace an exit by the ordered list of **(absolute MRU rank, identity)** for resident members of U. The rest of the cache matters through the gaps it leaves in those ranks. For an admitted path P, an old tracked node outside P at rank r moves to rank |P| + r − the number of P-nodes initially at ranks ≤r. Nodes of P move to positions 1 through |P| in path order. Truncating at capacity C gives the new projected state. Equal projections therefore yield equal hit lengths, the same next k-LPM choice, and equal cumulative misses, by induction even when the historical order adapts to the cache.

The same projection sometimes gives the score directly. Let h be the number of resident U-nodes, and z the number of outsiders ahead of the deepest such node (zero if h=0). If |U|+z≤C, then each initially resident tracked node survives to its first use, and each touched node survives all later uses in the pair. The exact score is |U|−h blocks. Otherwise the evaluator executes the original continuation once for each distinct relevant projection it needs. If every eligible exit has the same projection for a pair, its contribution is common to every action. Decision-only mode may skip it; absolute-verification mode restores it. All accounting uses integer missing blocks. Compulsory tails are common to every candidate. A causal 16-slot membership index is updated as each completed cohort enters or leaves history. Pair-score memoization expires within the decision.

For example, the two MRU states (a,b) and (b,a) have identical residents. With capacity two and subsequent singleton requests c then a, they incur one and two misses respectively. The projection retains that distinction. Likewise, freezing the historical request order from one exit can give a different score on another exit. Exact full-state and projection ties retain the original incumbent and lexicographic rules. The [derivation and counterexamples](derivation.md) give assumptions, complexity and limiting cases.

LRU rank updates and focusing analysis on observable blocks have established precedents. The implementation contribution is to index historical pairs once, share future computations across co-optimal exits and bypass a replay when the direct score is certified. The scoped algorithmic distinction is the rank projection and sufficient survival test for atomic prefix admissions with adaptive k-LPM continuation. Priority beyond the inspected literature remains unresolved. [Mattson et al.](https://bitsavers.computerhistory.org/pdf/ibm/IBM_Systems_Journal/092/ibmsj0902B.pdf) · [Touzeau et al., §4.2](https://valentintouzeau.fr/papers/POPL2019.pdf)

### Equivalence and matched performance

Independent synthetic checks covered 3,287 decision inputs, 546 incremental decisions and 134,640 reachable-state/history-pair inputs. The correctness pass then checked **8,766 cohort–capacity cases per method**, comprising both saved integration bins and all 56 previously reported workload bins, each at both capacities. Reference and optimized tie-only matched the archived order, full reconstructed MRU exit, immediate work, total episode work, incumbent and independently reconstructed absolute selected objective in every case. The absolute values came from replaying each historical pair from the selected exit with the pinned parent simulator. All three decision-only timing repetitions were checked against those actions and complete states. There were zero mismatches. [Independent tests](audit.md) · [Cohort-level evidence](equivalence.jsonl.gz)

Mean μs per measured decision, **native CPU / caller wall**, pooled across three fixed repetitions of each of the original 4,245 measured cohorts. Native CPU includes ingestion, selection and live history/state updates. Caller wall includes writing the framed request to a native process, native processing and response formatting, IPC, reading the response and decoding its JSON.

| Traffic | Capacity | k-LPM | Exact immediate | Reference tie-only | Optimized tie-only |
|---|---:|---:|---:|---:|---:|
| Conversation | 128 | 10.21 / 54.86 | 10.27 / 54.35 | 280.77 / 330.01 | **31.21 / 77.79** |
| Tool/agent | 128 | 8.70 / 50.26 | 9.44 / 53.09 | 284.26 / 333.30 | **89.21 / 132.51** |
| Conversation | 32 | 7.72 / 38.98 | 7.73 / 37.36 | 59.52 / 90.55 | **14.49 / 47.07** |
| Tool/agent | 32 | 6.90 / 35.39 | 7.48 / 36.82 | 57.47 / 87.61 | **39.95 / 69.92** |

The largest speedup occurred on conversation traffic, where historical tie-breaking and immediate ordering consumed exactly the same prefill work. On tool/agent traffic, where the savings occurred, native CPU improved **3.19×** at 128 blocks and **1.44×** at 32 blocks against reference tie-only. At primary capacity, optimized tie-only still used **9.45×** the native CPU of immediate ordering on tool/agent requests. The exposed bins measure computational performance and exact replay equivalence. They supply no new traffic-generalization evidence.

At 128 blocks both tie-only implementations retained 53,013 candidate full states across the workload and used the same 226,182 current-order transitions per repetition. Historical continuations fell from **420,910 to 46,766**, reducing their transitions from 3,053,444 to 355,224. The optimized evaluator recorded 140,053 direct scores and 55,095 memo hits. At 32 blocks the corresponding continuation counts were 276,052 and 69,253, with 2,000,228 and 518,390 transitions. A pair with entirely different projected states and no direct certificate can still require all reference rollouts plus bookkeeping.

Primary measured native CPU totals per pass were **1.201 s reference, 0.292 s optimized, 0.041 s immediate and 0.039 s k-LPM**. For optimized tie-only, the three totals were 0.292, 0.294 and 0.289 s. Entire native process CPU, including startup, resets, warm-up and result formatting, averaged 1.343, 0.430, 0.179 and 0.175 s respectively. Primary end-to-end measured wall totals averaged 1.410, 0.480, 0.227 and 0.220 s respectively. At 32 blocks reference versus optimized averaged 0.247 versus 0.131 s of measured native CPU and 0.376 versus 0.263 s of measured decision wall. These are local timings from one Mac. Three repetitions describe measurement variability on identical traffic.

At primary capacity optimized historical storage peaked at 29,080 bytes including its membership index, versus 9,640 for the reference. The index alone peaked at 22,272 bytes and grows with distinct IDs encountered in a bin. The pair memo peaked at 24 entries and 4,736 bytes including temporary key capacity. The shared current-transition cache reserved up to 35,100 bytes. Peak native process RSS was 3.97 MiB optimized, 3.66 MiB reference and 3.50 MiB for each immediate control. Allocator and process overhead are included in RSS. Component maxima need not coincide. The preparation pass took 0.699 CPU-seconds, including pinned trace parsing/hashing (0.216), grouping/ID construction (0.128), wire encoding across capacities (0.066), archived records and verification warm-up. Every timed method received the same pre-framed current-group messages. The wrapper's measured per-decision CPU per primary pass totaled 0.081 s for optimized tie-only. Full wrapper process costs also include validation and logging. [Repetition totals, memory, counters and percentiles by traffic and capacity](benchmark_summary.json)

**Prefill reproduction.** At 128 blocks tie-only used 119,501,579 positions, exact immediate used 119,746,315 and k-LPM used 119,980,811. At 32 blocks the corresponding totals were 124,522,251, 125,781,259 and 126,377,739. Conversation tied on prefill. At each capacity the pooled gains came from tool/agent traffic. The older full planner's reported primary saving of 249,344 gives the 98.15% retention figure. Only the tie-only and immediate controls were replayed in this benchmark. The previous Python/native timing (0.983 ms tie-only, 0.992 ms full, 0.562 ms immediate) supplies historical context; this study's comparisons use a single compiled native implementation and a common decision interface. Gains cannot be attributed solely to recency changes, and scheduler time and prefill positions have different units.

### Cost, tails and reproducibility

The integrated verification and timing process used **27.13 CPU-seconds** (wrapper and native children) and **27.52 wall-seconds**, including the absolute-score checks. Its wrapper peak RSS was 186.9 MiB, mainly for trace records and verification sequences. Synthetic checks, compilation, report aggregation and administrative charges are separately reconciled in [costs.json](costs.json). GPU use, new traffic acquisition and paid inference were zero. Agent-service consumption was unmetered.

<details><summary>Timing tails by workload and capacity</summary>

All figures are μs per cohort. Each cell lists mean / p95 / p99 / maximum. Process and memo high-water marks and individual repetition totals are also in the linked summary.

| Trace | Blocks | Method | Native CPU | End-to-end wall |
|---|---:|---|---|---|
| conversation | 128 | K | 10.2 / 21.0 / 27.0 / 49.0 | 54.9 / 82.4 / 101.8 / 217.0 |
| conversation | 128 | IMM | 10.3 / 20.0 / 27.0 / 54.0 | 54.3 / 83.9 / 106.2 / 487.0 |
| conversation | 128 | REF | 280.8 / 548.0 / 575.0 / 668.0 | 330.0 / 604.1 / 648.2 / 1733.9 |
| conversation | 128 | OPT | 31.2 / 50.0 / 61.0 / 97.0 | 77.8 / 114.5 / 135.0 / 240.6 |
| conversation | 32 | K | 7.7 / 13.0 / 19.0 / 42.0 | 39.0 / 54.5 / 70.1 / 169.2 |
| conversation | 32 | IMM | 7.7 / 13.0 / 19.0 / 48.0 | 37.4 / 53.3 / 66.4 / 1079.8 |
| conversation | 32 | REF | 59.5 / 131.0 / 146.0 / 173.0 | 90.5 / 161.9 / 178.6 / 244.4 |
| conversation | 32 | OPT | 14.5 / 23.0 / 30.0 / 70.0 | 47.1 / 64.8 / 89.4 / 1451.7 |
| toolagent | 128 | K | 8.7 / 17.0 / 23.0 / 51.0 | 50.3 / 73.2 / 91.1 / 161.3 |
| toolagent | 128 | IMM | 9.4 / 18.0 / 25.0 / 54.0 | 53.1 / 77.9 / 101.2 / 1334.4 |
| toolagent | 128 | REF | 284.3 / 566.0 / 596.0 / 769.0 | 333.3 / 621.0 / 673.0 / 2122.7 |
| toolagent | 128 | OPT | 89.2 / 200.0 / 269.0 / 399.0 | 132.5 / 250.0 / 323.9 / 597.3 |
| toolagent | 32 | K | 6.9 / 11.0 / 15.0 / 51.0 | 35.4 / 47.6 / 57.2 / 101.8 |
| toolagent | 32 | IMM | 7.5 / 12.0 / 17.0 / 52.0 | 36.8 / 51.6 / 72.9 / 191.7 |
| toolagent | 32 | REF | 57.5 / 148.0 / 160.0 / 202.0 | 87.6 / 177.0 / 194.8 / 1783.3 |
| toolagent | 32 | OPT | 40.0 / 99.0 / 140.0 / 200.0 | 69.9 / 128.9 / 171.7 / 1294.3 |

</details>

[Prospective design](protocol.md) · [Pinned source, compiler, binary and benchmark procedure](freeze.json) · [Native evaluator](evaluator.cpp) · [Compressed timing records](timings.jsonl.gz) · [Receipts and raw hashes](benchmark_receipt.json). The frozen benchmark compiler was Apple Clang 21.0.0 with C++17 and `-O3`. The evaluator includes the original engine source for the shared transition semantics. A fresh sibling directory keeps original run locks and results intact. The commands below reproduce the measurement with the supplied macOS arm64 binary and the existing pinned parent artifacts; CPU timings will vary.

```sh
mkdir research/exact_tie_reproduction
cp research/exact_tie_20261108/{evaluator,evaluator.cpp,benchmark.py,summarize.py,test_exact.py,freeze.json,protocol.md,derivation.md,audit.md} research/exact_tie_reproduction/
cd research/exact_tie_reproduction
export PYTHONDONTWRITEBYTECODE=1
../../.venv-research/bin/python test_exact.py
../../.venv-research/bin/python benchmark.py
../../.venv-research/bin/python summarize.py
```
