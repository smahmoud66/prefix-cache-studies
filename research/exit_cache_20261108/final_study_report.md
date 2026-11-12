# Does recent demand identify a better exit cache?

**MIXED_OR_INCONCLUSIVE.** Historical rollout improved whole-episode prefill work over both strong LRU baselines on the tool/agent trace. Conversation traffic tied throughout. At the primary cache capacity, almost all of the gain was available by using history to break ties among immediately optimal orders. The additional computation of the full two-cohort planner has limited support at this operating point.

### Registered measurement

The question was whether the scheduler should consider which prefixes and recency order survive its choice, even when the current cohort costs slightly more. We retained the parent simulator's ordinary leaf LRU, four-request/one-second gate, 512-token blocks, final-token convention, separate active workspace, quarter-bin FCFS warm-up and bin resets. The single control using queue-aware eviction is identified in the table. Prefill counts input positions requiring computation under this model.

From each candidate exit, replay up to eight completed pairs of past cohorts with fixed k-LPM/LRU continuation. Minimize current prefill plus their average continuation prefill. Candidate orders see the same chronological history and current cohort. Exact ties retain the same-entry immediate incumbent, then use arrival lexicographic order. Changing recency while keeping the resident set can change the next eviction. Collapsing identical complete MRU tuples retains identical future transition costs by induction. A two-block hand construction in the contract requires spending one additional block immediately to improve the two-cohort objective. The one-step control uses the first member of every same history pair. The tie-only control prohibits this immediate sacrifice. No estimator, horizon or weight was selected from development effects. [Contract and derivation](contract.md) · [Independent reasoning and checks](review.md)

TOPAS is the closest conceptual precedent. Its value estimate uses known workflow structure, stage progress and near-future prefix reuse for joint residency and execution decisions. Learned Prefix Caching uses content and timestamps for eviction; PEEK uses the pending queue for scheduling and retention. Here the test is what history of anonymous prefix identities can achieve by choosing only a legal order while ordinary LRU carries the exit state forward. The original contribution is the scoped comparison and its mechanism evidence; predictive caching and post-decision state scoring have substantial prior art. TOPAS was inspected as a preprint. Published k-LPM and PEEK comparisons inherit the original block-resolution adaptations. [TOPAS v1](https://arxiv.org/abs/2608.25523v1) · [Learned Prefix Caching, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/414f642a1ea9350006669774cba9bcd4-Abstract-Conference.html) · [Source coverage](sources.md)

### Comparison on the complete evaluation frame

We reconciled the original development and evaluation IDs against their raw outcome records. Each public trace had 28 bins left without recorded project outcome exposure. Their identities were frozen before this study computed policy effects. All 56 completed. The census contains 15,432 measured requests in 4,245 cohorts: 5,221 conversation and 10,211 tool/agent requests. The known reversal in old tool/agent bin 3 was excluded. There were no substitutions, unfinished groups, capacity violations or excess displacements. [Pinned inputs and split](split.json)

Lower prefill is better. The primary column averages requests inside each bin, then bins within each trace, then the two traces equally. The CPU column gives measured mean per-cohort scheduler computation at 128 blocks.

| Full-episode policy | Conversation, 128 | Tool/agent, 128 | Primary mix, 128 | Pressure mix, 32 | CPU ms, 128 |
|---|---:|---:|---:|---:|---:|
| FCFS/LRU | 11,564.52 | 5,970.71 | 8,767.61 | 9,123.61 | 0.089 |
| k-LPM/LRU | 11,564.52 | 5,961.72 | 8,763.12 | 9,074.55 | 0.085 |
| Exact immediate order/LRU | 11,564.52 | 5,938.12 | **8,751.32** | **9,044.96** | 0.562 |
| Historical heuristic selector, queue-aware eviction | 11,564.52 | 6,228.13 | 8,896.32 | 9,065.02 | 0.773 |
| Historical rollout, two cohorts/LRU | 11,564.52 | 5,913.66 | **8,739.09** | **8,978.93** | 0.992 |
| Historical rollout, one cohort/LRU | 11,564.52 | 5,919.97 | 8,742.24 | 8,978.59 | 0.858 |
| Two cohorts, immediate ties only/LRU | 11,564.52 | 5,914.12 | 8,739.32 | 8,983.62 | 0.983 |

**Primary savings were 12.23 positions/request** versus exact-immediate/LRU (about 0.14%), 24.03 versus k-LPM/LRU and 28.52 versus FCFS/LRU. On tool/agent traffic the primary contrast was +24.47, with 25 positive bins and three ties. All 28 conversation bins tied. Across all 56 bins, the median was zero and the range was 0 to +64.38. Among tool/agent bins the proposal also lost once to k-LPM, despite beating it on average. Counting actual requests rather than equally weighting bins and traces gives **249,344 positions saved**, or **16.16 per request**, from 119,746,315 to 119,496,971. These are different weightings of the same observations.

At 32 blocks the primary-comparator contrast rose to +66.03 in the equal-weight mix, comprising 0 on conversation and +132.06 on tool/agent traffic. Tool/agent yielded 27 gains and one loss (−5.14 positions/request); range across both traces was −5.14 to +179.20. The pooled saving was 1,353,728 positions, or 87.72 per request. One-step history was slightly cheaper than two-step in this condition, by 0.33 positions/request in the mix, with eight bin wins and eight losses in their direct comparison. The primary-capacity one-step comparison favored two-step by 3.16 positions/request. These are descriptive finite-census differences. The public one-hour samples, temporal dependence, and bin resets leave uncertainty about other traffic and longer-running cache states.

### Which decisions mattered?

Of 4,245 primary cohorts, 3,967 offered multiple legal orders and 3,879 offered multiple complete exits. In 3,490 all alternative exits retained identical sets, with differences entirely in recency. In 389 a different resident set was possible. The proposed method changed its same-entry incumbent order 330 times. **290 of those choices changed only recency**, and 40 changed residency. Three changes were on conversation traffic. Only six choices spent extra immediate work, totaling 13,312 positions. Full-episode savings of 249,344 therefore reflect a residual 262,656-position benefit from how later entry states and choices developed, offset by the immediate premium. This is an accounting identity and does not assign independent causal benefits to individual choices.

At 128 blocks the tie-only policy saved 244,736 positions versus the exact immediate baseline. Allowing sacrifice saved another **4,608** positions, with three bin wins, one loss and 52 ties versus tie-only. At 32 blocks there were 1,223 cohorts with recency-only variation and 2,656 with possible residency variation. The proposed order changed 979 times (374 recency-only and 605 residency changes). Its 140 immediate sacrifices cost 248,320 positions. It saved another 94,720 positions over tie-only across complete episodes. More aggressive historical valuation helped under pressure, but the one-step control already achieved similar overall work.

**Privileged diagnostic.** We sealed the 56 online records before passing real successors to a separate offline process. Among the 330 changed primary decisions, 323 had two successors. Relative to the immediate incumbent, actual current-plus-two-cohort work improved in **58**, tied in **264**, and worsened in **one**. The history choice attained the short-horizon minimum in 319/323, but the incumbent already attained it in 263/323. Among the deterministic sample of unchanged decisions, 248/256 were observable; the incumbent missed a strictly better alternative in three. At 32 blocks the changed decisions with two successors yielded 383 improvements, 516 ties and 65 losses; 15 of 979 were truncated. Four of 217 evaluable sampled unchanged decisions missed a strict opportunity (three truncated). These comparisons condition on the proposed policy's entry state and k-LPM continuation. They overlap in time and are not added to episode gains. The offline lower bound averaged 8,527.74 positions/request at 128 and 8,609.02 at 32. These bounds leave possible room for other schedules and retention choices; the gap is a ceiling.

### Overhead, limitations and decision

At 128 blocks the proposed scheduler averaged **0.992 ms** of measured CPU per cohort (p95 1.682, p99 1.908, maximum 2.592 ms), versus 0.562 ms for exact immediate search. End-to-end local decision wall time averaged 1.308 ms (p99 2.299, maximum 5.391). The 4,245 primary decisions considered 85,840 legal permutations, producing 55,519 distinct complete exits summed across cohorts. Native enumeration used 227,882 current transitions and 441,094 historical rollouts comprising 3,202,974 continuation transitions. The parent immediate-incumbent calculation and application used another 78,493 simulated transitions. Historical rollout CPU alone was 1.17 seconds inside the primary policy's 4.21 seconds of measured scheduler CPU. At 32 blocks mean/p95/p99/max CPU was 0.453/0.682/0.765/1.025 ms, and historical replay required 2,503,685 transitions. The [summary](summary.json) gives timings and simulation counts for all controls. Per-decision computation includes wrapper CPU and native selection; whole-process totals also include native parsing and serialization.

Development, sealed online evaluation and offline diagnostics used **38.37 process CPU-seconds combined** (1.38, 35.84 and 1.15 respectively), with 38.52 seconds of wall time. Peak wrapper RSS across those stages was 163.4 MiB and peak native child RSS was 3.0 MiB. Every method saw identical warm-up demand: 5,204 requests and 41,552,506 simulated warm-up positions per policy at 128 blocks (43,876,986 at 32). Intentional cohort collection delay averaged 96.3 ms, with p95 and maximum 1,000 ms. Maximum queue-rank displacement was three or less; active transient input reached 126,195 tokens. These quantities are separate from the retained-cache budget and measured scheduler overhead. The protocol leaves actual accelerator latency, energy, throughput and monetary value unknown. No GPU allocation, PACE submission, model inference or paid API call occurred. Native-agent service usage was unmetered. [Resource reconciliation](costs.json)

The strongest finding is that **history can resolve equal-immediate-cost orders usefully on tool/agent demand under ordinary LRU**. The full two-cohort policy offers little additional primary-capacity benefit over tie-breaking and incurs extra scheduling CPU. Recommendation: retain the narrower tie-breaking result as research evidence and withhold a deployment recommendation for the full planner. The commercial traces support this fixed replay only.

### Evidence and reproduction

[Prospective contract](contract.md) · [Frozen files](freeze.json) · [Causal engine](engine.cpp) · [Online and offline runner](runner.py) · [Per-bin results and selected state records](../../data/exit_cache_20261108-online.jsonl.gz) · [Privileged checks](../../data/exit_cache_20261108-hindsight.jsonl.gz) · [Independent reconstruction of tool/agent bin 0](review.md) · [Analysis code](analyze.py).

The following commands reproduce the scientific outputs on the recorded macOS/arm64 environment from the project root, in a fresh sibling directory. The frozen original binary, development receipt and input files are required. Wall/CPU timing and file hashes containing timing will vary. The archived compile command, compiler identity and C++ source hash are in freeze.json; the runner pins its evaluation executable.

```sh
mkdir research/exit_cache_reproduction
cp research/exit_cache_20261108/{runner.py,analyze.py,engine,engine.cpp,freeze.json,split.json,contract.md,development_receipt.json} research/exit_cache_reproduction/
cd research/exit_cache_reproduction
export PYTHONDONTWRITEBYTECODE=1
./engine --self-test
../../.venv-research/bin/python runner.py online
../../.venv-research/bin/python runner.py hindsight
../../.venv-research/bin/python analyze.py
```
