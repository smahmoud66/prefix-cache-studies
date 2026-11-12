# Matched measurements by interface, traffic and capacity

Each row uses all 28 previously evaluated Mooncake bins for that traffic type at that capacity. Three fresh native processes supply the three timing repetitions. Each process resets and applies common FCFS warm-up at each bin. The absolute interface returns the preferred representative and exact historical sum for every distinct immediately optimal exit. The decision interface returns the selected order and actual complete exit. The checks against archived dispatches and the validated score vectors occur outside the individual caller-wall interval. The two interfaces are summarized separately.

Native CPU includes current request parsing and identity ingestion, candidate enumeration, history scoring and live index/state updates. Historical CPU is the scoring and ranking interval inside native CPU. Candidate CPU is the common candidate construction interval. Caller wall includes IPC, formatting, response and JSON decoding. Read timing totals below as seconds per workload pass averaged over the three repetitions, and mean and tail latencies as microseconds per cohort over the same three runs. Fractions and speed ratios describe these finite measurements.

## conversation · 32 blocks · decision

1,500 measured cohorts per repetition. Every policy returned 59,702,504 prefill positions.

| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |
|---|---:|---:|---|---|---:|
| FULL = RANK-00 | 0.0660 / 44.01 | 5.61 | 0.0855 / 57.0 / 126.0 / 145.0 / 182.0 | 0.1325 / 88.3 / 160.0 / 181.4 / 575.9 | 3.44 |
| FOCUSED | 0.0019 / 1.26 | 5.63 | 0.0214 / 14.3 / 22.0 / 28.0 / 68.0 | 0.0681 / 45.4 / 62.1 / 75.0 / 274.8 | 3.72 |
| RANK-10 | 0.0640 / 42.67 | 5.55 | 0.0836 / 55.7 / 122.0 / 144.0 / 255.0 | 0.1322 / 88.1 / 159.6 / 193.1 / 575.3 | 3.66 |
| RANK-01 | 0.0019 / 1.27 | 5.46 | 0.0211 / 14.1 / 22.0 / 28.0 / 97.0 | 0.0671 / 44.8 / 62.5 / 84.7 / 249.1 | 3.75 |
| RANK-11 | 0.0019 / 1.24 | 5.40 | 0.0207 / 13.8 / 21.0 / 28.0 / 64.0 | 0.0664 / 44.3 / 62.1 / 96.8 / 314.5 | 3.70 |

Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.

| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |
|---|---|---|---|---:|---|---:|---|---|
| FULL = RANK-00 | 106,828 / 743,534 | 0 / 0 / 0 | 0 / 0 | 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 6,772 / 0 / 0 |
| FOCUSED | 151 / 1,092 | 408 / 0 / 0 | 408 / 257 | 10,511 | 427,584 / 12,478 / 5,326 | 161,700 | 4,832 / 1,092 / 34,648 | 19,976 / 1,568 / 2,056 |
| RANK-10 | 104,994 / 732,789 | 106,828 / 1,834 / 59,200 | 0 / 0 | 0 | 0 / 0 / 0 | 161,700 | 0 / 0 / 0 | 19,976 / 0 / 0 |
| RANK-01 | 151 / 1,092 | 0 / 0 / 0 | 408 / 257 | 10,511 | 427,584 / 12,478 / 5,326 | 161,700 | 0 / 0 / 0 | 19,976 / 1,568 / 0 |
| RANK-11 | 151 / 1,092 | 408 / 0 / 0 | 408 / 257 | 10,511 | 427,584 / 12,478 / 5,326 | 161,700 | 0 / 0 / 0 | 19,976 / 1,568 / 0 |

Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.

| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |
|---|---:|---:|---:|
| FOCUSED | +0.02 / 1.014× | +0.51 / 1.037× | +1.14 / 1.026× |
| RANK-01 | +0.02 / 1.020× | +0.28 / 1.020× | +0.48 / 1.011× |
| RANK-10 | +41.43 / 34.365× | +41.93 / 4.044× | +43.86 / 1.991× |
| FULL = RANK-00 | +42.77 / 35.441× | +43.23 / 4.138× | +44.05 / 1.995× |

FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.

| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |
|---|---:|---:|---:|
| 1 | -0.080 / 0.961× | +0.227 / 1.010× | -2.026 / 0.972× |
| 2 | +0.240 / 1.140× | +2.306 / 1.118× | +7.971 / 1.129× |
| 3 | -0.083 / 0.954× | -0.256 / 0.988× | -0.818 / 0.987× |

Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was +1.31 historical CPU, +1.02 native CPU and -0.30 caller wall.

## conversation · 32 blocks · absolute

1,500 measured cohorts per repetition. Every policy returned 59,702,504 prefill positions.

| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |
|---|---:|---:|---|---|---:|
| FULL = RANK-00 | 0.0672 / 44.78 | 5.61 | 0.0864 / 57.6 / 127.0 / 146.0 / 179.0 | 0.1369 / 91.3 / 166.7 / 187.5 / 418.9 | 3.30 |
| FOCUSED | 0.0087 / 5.81 | 5.49 | 0.0278 / 18.5 / 27.0 / 32.0 / 78.0 | 0.0769 / 51.3 / 70.3 / 80.9 / 195.2 | 3.66 |
| RANK-10 | 0.0663 / 44.20 | 5.61 | 0.0860 / 57.3 / 124.0 / 142.0 / 176.0 | 0.1368 / 91.2 / 162.9 / 182.2 / 289.8 | 3.62 |
| RANK-01 | 0.0113 / 7.54 | 5.64 | 0.0309 / 20.6 / 29.0 / 34.0 / 53.0 | 0.0811 / 54.0 / 72.8 / 80.7 / 159.9 | 3.72 |
| RANK-11 | 0.0111 / 7.43 | 5.63 | 0.0307 / 20.5 / 29.0 / 35.0 / 70.0 | 0.0812 / 54.1 / 73.1 / 84.7 / 226.7 | 3.67 |

Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.

| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |
|---|---|---|---|---:|---|---:|---|---|
| FULL = RANK-00 | 108,276 / 753,662 | 0 / 0 / 0 | 0 / 0 | 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 6,772 / 0 / 0 |
| FOCUSED | 11,908 / 83,304 | 12,367 / 202 / 6,720 | 408 / 257 | 0 | 427,584 / 12,478 / 5,326 | 161,700 | 381,056 / 83,304 / 2,427,694 | 19,976 / 1,568 / 2,056 |
| RANK-10 | 106,422 / 742,797 | 108,276 / 1,854 / 59,904 | 0 / 0 | 0 | 0 / 0 / 0 | 161,700 | 0 / 0 / 0 | 19,976 / 0 / 0 |
| RANK-01 | 12,110 / 84,498 | 0 / 0 / 0 | 408 / 257 | 0 | 427,584 / 12,478 / 5,326 | 161,700 | 0 / 0 / 0 | 19,976 / 1,568 / 0 |
| RANK-11 | 11,908 / 83,304 | 12,367 / 202 / 6,720 | 408 / 257 | 0 | 427,584 / 12,478 / 5,326 | 161,700 | 0 / 0 / 0 | 19,976 / 1,568 / 0 |

Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.

| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |
|---|---:|---:|---:|
| FOCUSED | -1.63 / 0.781× | -1.94 / 0.905× | -2.86 / 0.947× |
| RANK-01 | +0.11 / 1.015× | +0.09 / 1.004× | -0.10 / 0.998× |
| RANK-10 | +36.77 / 5.948× | +36.84 / 2.798× | +37.05 / 1.684× |
| FULL = RANK-00 | +37.35 / 6.026× | +37.12 / 2.812× | +37.14 / 1.686× |

FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.

| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |
|---|---:|---:|---:|
| 1 | -2.299 / 0.792× | -2.691 / 0.912× | -4.073 / 0.950× |
| 2 | -2.886 / 0.753× | -4.379 / 0.865× | -8.284 / 0.903× |
| 3 | -2.134 / 0.801× | -1.674 / 0.943× | -0.514 / 0.993× |

Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was +0.47 historical CPU, +0.20 native CPU and +0.19 caller wall.

## conversation · 128 blocks · decision

1,500 measured cohorts per repetition. Every policy returned 59,702,504 prefill positions.

| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |
|---|---:|---:|---|---|---:|
| FULL = RANK-00 | 0.3623 / 241.56 | 18.79 | 0.4049 / 269.9 / 544.0 / 574.0 / 1045.0 | 0.4833 / 322.2 / 601.3 / 674.2 / 1969.2 | 3.75 |
| FOCUSED | 0.0039 / 2.62 | 18.33 | 0.0450 / 30.0 / 48.0 / 57.0 / 127.0 | 0.1117 / 74.5 / 108.6 / 127.5 / 426.8 | 4.09 |
| RANK-10 | 0.2158 / 143.87 | 18.71 | 0.2581 / 172.0 / 402.0 / 457.0 / 582.0 | 0.3288 / 219.2 / 456.2 / 517.8 / 693.4 | 3.95 |
| RANK-01 | 0.0042 / 2.81 | 18.05 | 0.0448 / 29.8 / 48.0 / 65.0 / 121.0 | 0.1109 / 73.9 / 109.6 / 131.1 / 330.8 | 4.00 |
| RANK-11 | 0.0041 / 2.72 | 18.20 | 0.0449 / 29.9 / 48.0 / 58.0 / 105.0 | 0.1116 / 74.4 / 109.0 / 131.5 / 395.6 | 4.03 |

Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.

| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |
|---|---|---|---|---:|---|---:|---|---|
| FULL = RANK-00 | 153,238 / 1,066,293 | 0 / 0 / 0 | 0 / 0 | 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 9,640 / 0 / 0 |
| FOCUSED | 156 / 1,156 | 633 / 182 / 38,784 | 451 / 295 | 10,511 | 2,453,888 / 37,433 / 14,656 | 228,179 | 19,968 / 1,156 / 100,660 | 29,080 / 4,160 / 2,056 |
| RANK-10 | 87,036 / 626,998 | 153,238 / 66,202 / 9,346,944 | 0 / 0 | 0 | 0 / 0 / 0 | 228,179 | 0 / 0 / 0 | 29,080 / 0 / 0 |
| RANK-01 | 223 / 1,640 | 0 / 0 / 0 | 633 / 410 | 10,511 | 2,453,888 / 52,357 / 18,290 | 228,179 | 0 / 0 / 0 | 29,080 / 4,160 / 0 |
| RANK-11 | 156 / 1,156 | 633 / 182 / 38,784 | 451 / 295 | 10,511 | 2,453,888 / 37,433 / 14,656 | 228,179 | 0 / 0 / 0 | 29,080 / 4,160 / 0 |

Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.

| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |
|---|---:|---:|---:|
| FOCUSED | -0.10 / 0.962× | +0.08 / 1.003× | +0.08 / 1.001× |
| RANK-01 | +0.09 / 1.033× | -0.09 / 0.997× | -0.49 / 0.993× |
| RANK-10 | +141.15 / 52.914× | +142.10 / 5.746× | +144.77 / 2.945× |
| FULL = RANK-00 | +238.84 / 88.843× | +239.99 / 9.015× | +247.79 / 4.330× |

FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.

| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |
|---|---:|---:|---:|
| 1 | -0.217 / 0.948× | -1.113 / 0.976× | -2.457 / 0.978× |
| 2 | -0.308 / 0.925× | -1.159 / 0.974× | -3.902 / 0.965× |
| 3 | +0.061 / 1.015× | +2.631 / 1.059× | +6.703 / 1.061× |

Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was +97.60 historical CPU, +97.98 native CPU and +103.51 caller wall.

## conversation · 128 blocks · absolute

1,500 measured cohorts per repetition. Every policy returned 59,702,504 prefill positions.

| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |
|---|---:|---:|---|---|---:|
| FULL = RANK-00 | 0.3674 / 244.92 | 18.86 | 0.4098 / 273.2 / 539.0 / 564.0 / 643.0 | 0.4872 / 324.8 / 598.2 / 632.2 / 877.0 | 3.58 |
| FOCUSED | 0.0159 / 10.61 | 18.00 | 0.0565 / 37.6 / 57.0 / 67.0 / 113.0 | 0.1299 / 86.6 / 126.5 / 159.9 / 392.8 | 4.06 |
| RANK-10 | 0.2197 / 146.44 | 18.80 | 0.2621 / 174.7 / 406.0 / 465.0 / 588.0 | 0.3384 / 225.6 / 466.2 / 523.2 / 758.7 | 4.08 |
| RANK-01 | 0.0348 / 23.18 | 18.54 | 0.0766 / 51.0 / 71.0 / 86.0 / 117.0 | 0.1501 / 100.0 / 139.7 / 160.0 / 304.0 | 4.16 |
| RANK-11 | 0.0225 / 14.98 | 18.38 | 0.0637 / 42.5 / 63.0 / 73.0 / 121.0 | 0.1360 / 90.7 / 128.2 / 145.5 / 328.4 | 3.98 |

Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.

| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |
|---|---|---|---|---:|---|---:|---|---|
| FULL = RANK-00 | 154,686 / 1,076,421 | 0 / 0 / 0 | 0 / 0 | 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 9,640 / 0 / 0 |
| FOCUSED | 6,975 / 50,461 | 12,592 / 5,322 / 757,504 | 451 / 295 | 0 | 2,453,888 / 37,433 / 14,656 | 228,179 | 892,800 / 50,461 / 4,553,569 | 29,080 / 4,160 / 2,056 |
| RANK-10 | 87,895 / 633,216 | 154,686 / 66,791 / 9,427,200 | 0 / 0 | 0 | 0 / 0 / 0 | 228,179 | 0 / 0 / 0 | 29,080 / 0 / 0 |
| RANK-01 | 12,182 / 85,046 | 0 / 0 / 0 | 633 / 410 | 0 | 2,453,888 / 52,357 / 18,290 | 228,179 | 0 / 0 / 0 | 29,080 / 4,160 / 0 |
| RANK-11 | 6,975 / 50,461 | 12,592 / 5,322 / 757,504 | 451 / 295 | 0 | 2,453,888 / 37,433 / 14,656 | 228,179 | 0 / 0 / 0 | 29,080 / 4,160 / 0 |

Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.

| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |
|---|---:|---:|---:|
| FOCUSED | -4.37 / 0.708× | -4.85 / 0.886× | -4.05 / 0.955× |
| RANK-01 | +8.20 / 1.547× | +8.55 / 1.201× | +9.37 / 1.103× |
| RANK-10 | +131.46 / 9.773× | +132.25 / 4.112× | +134.93 / 2.488× |
| FULL = RANK-00 | +229.94 / 16.346× | +230.69 / 6.428× | +234.14 / 3.582× |

FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.

| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |
|---|---:|---:|---:|
| 1 | -6.523 / 0.711× | -7.278 / 0.886× | -5.333 / 0.961× |
| 2 | -6.873 / 0.697× | -8.237 / 0.871× | -5.957 / 0.956× |
| 3 | -6.287 / 0.717× | -6.305 / 0.900× | -6.929 / 0.949× |

Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was +90.28 historical CPU, +89.89 native CPU and +89.84 caller wall.

## toolagent · 32 blocks · decision

2,745 measured cohorts per repetition. Every policy returned 64,819,747 prefill positions.

| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |
|---|---:|---:|---|---|---:|
| FULL = RANK-00 | 0.1154 / 42.04 | 6.29 | 0.1504 / 54.8 / 142.0 / 159.0 / 195.0 | 0.2327 / 84.8 / 173.5 / 193.8 / 324.1 | 3.31 |
| FOCUSED | 0.0565 / 20.57 | 6.37 | 0.0925 / 33.7 / 82.0 / 110.0 / 181.0 | 0.1855 / 67.6 / 122.0 / 207.8 / 1770.1 | 3.70 |
| RANK-10 | 0.1097 / 39.96 | 6.43 | 0.1463 / 53.3 / 135.0 / 156.0 / 265.0 | 0.2327 / 84.8 / 168.8 / 192.3 / 478.6 | 3.56 |
| RANK-01 | 0.0747 / 27.23 | 6.42 | 0.1106 / 40.3 / 102.0 / 140.0 / 189.0 | 0.1956 / 71.3 / 135.0 / 177.0 / 320.7 | 3.62 |
| RANK-11 | 0.0725 / 26.41 | 6.51 | 0.1090 / 39.7 / 99.0 / 137.0 / 174.0 | 0.1947 / 70.9 / 129.8 / 172.0 / 226.8 | 3.72 |

Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.

| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |
|---|---|---|---|---:|---|---:|---|---|
| FULL = RANK-00 | 169,224 / 1,256,694 | 0 / 0 / 0 | 0 / 0 | 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 6,264 / 0 / 0 |
| FOCUSED | 69,102 / 517,298 | 142,201 / 8,574 / 494,144 | 133,627 / 64,525 | 4,807 | 676,896 / 3,664,059 / 2,919,044 | 266,842 | 2,211,264 / 517,298 / 16,022,849 | 20,484 / 4,016 / 2,056 |
| RANK-10 | 157,736 / 1,177,628 | 169,224 / 11,488 / 597,760 | 0 / 0 | 0 | 0 / 0 / 0 | 266,842 | 0 / 0 / 0 | 20,484 / 0 / 0 |
| RANK-01 | 73,285 / 546,174 | 0 / 0 / 0 | 142,201 / 68,916 | 4,807 | 676,896 / 3,893,140 / 3,114,732 | 266,842 | 0 / 0 / 0 | 20,484 / 4,016 / 0 |
| RANK-11 | 69,102 / 517,298 | 142,201 / 8,574 / 494,144 | 133,627 / 64,525 | 4,807 | 676,896 / 3,664,059 / 2,919,044 | 266,842 | 0 / 0 / 0 | 20,484 / 4,016 / 0 |

Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.

| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |
|---|---:|---:|---:|
| FOCUSED | -5.84 / 0.779× | -6.03 / 0.848× | -3.37 / 0.952× |
| RANK-01 | +0.82 / 1.031× | +0.58 / 1.015× | +0.33 / 1.005× |
| RANK-10 | +13.55 / 1.513× | +13.57 / 1.341× | +13.85 / 1.195× |
| FULL = RANK-00 | +15.63 / 1.592× | +15.07 / 1.379× | +13.83 / 1.195× |

FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.

| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |
|---|---:|---:|---:|
| 1 | -15.540 / 0.789× | -15.975 / 0.856× | -15.465 / 0.921× |
| 2 | -15.805 / 0.781× | -16.772 / 0.846× | -20.990 / 0.892× |
| 3 | -16.730 / 0.766× | -16.897 / 0.843× | +8.674 / 1.045× |

Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was +1.26 historical CPU, +0.93 native CPU and -0.35 caller wall.

## toolagent · 32 blocks · absolute

2,745 measured cohorts per repetition. Every policy returned 64,819,747 prefill positions.

| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |
|---|---:|---:|---|---|---:|
| FULL = RANK-00 | 0.1190 / 43.36 | 6.40 | 0.1546 / 56.3 / 144.0 / 159.0 / 216.0 | 0.2441 / 88.9 / 180.6 / 200.7 / 435.2 | 3.27 |
| FOCUSED | 0.0622 / 22.65 | 6.49 | 0.0985 / 35.9 / 82.0 / 113.0 / 283.0 | 0.1899 / 69.2 / 119.4 / 155.6 / 591.3 | 3.66 |
| RANK-10 | 0.1136 / 41.39 | 6.50 | 0.1503 / 54.8 / 137.0 / 156.0 / 249.0 | 0.2424 / 88.3 / 175.9 / 199.0 / 416.9 | 3.48 |
| RANK-01 | 0.0807 / 29.42 | 6.47 | 0.1169 / 42.6 / 101.0 / 138.0 / 252.0 | 0.2096 / 76.3 / 140.0 / 182.1 / 611.7 | 3.64 |
| RANK-11 | 0.0792 / 28.84 | 6.55 | 0.1160 / 42.3 / 99.0 / 136.0 / 267.0 | 0.2091 / 76.2 / 136.7 / 178.1 / 485.6 | 3.62 |

Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.

| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |
|---|---|---|---|---:|---|---:|---|---|
| FULL = RANK-00 | 172,040 / 1,277,792 | 0 / 0 / 0 | 0 / 0 | 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 6,264 / 0 / 0 |
| FOCUSED | 75,988 / 568,917 | 149,824 / 9,311 / 521,920 | 133,627 / 64,525 | 0 | 676,896 / 3,664,059 / 2,919,044 | 266,842 | 2,431,616 / 568,917 / 17,524,418 | 20,484 / 4,016 / 2,056 |
| RANK-10 | 160,321 / 1,197,112 | 172,040 / 11,719 / 607,904 | 0 / 0 | 0 | 0 / 0 / 0 | 266,842 | 0 / 0 / 0 | 20,484 / 0 / 0 |
| RANK-01 | 80,908 / 602,954 | 0 / 0 / 0 | 142,201 / 68,916 | 0 | 676,896 / 3,893,140 / 3,114,732 | 266,842 | 0 / 0 / 0 | 20,484 / 4,016 / 0 |
| RANK-11 | 75,988 / 568,917 | 149,824 / 9,311 / 521,920 | 133,627 / 64,525 | 0 | 676,896 / 3,664,059 / 2,919,044 | 266,842 | 0 / 0 / 0 | 20,484 / 4,016 / 0 |

Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.

| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |
|---|---:|---:|---:|
| FOCUSED | -6.19 / 0.785× | -6.38 / 0.849× | -6.99 / 0.908× |
| RANK-01 | +0.58 / 1.020× | +0.31 / 1.007× | +0.19 / 1.002× |
| RANK-10 | +12.55 / 1.435× | +12.50 / 1.296× | +12.15 / 1.160× |
| FULL = RANK-00 | +14.52 / 1.503× | +14.05 / 1.332× | +12.77 / 1.168× |

FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.

| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |
|---|---:|---:|---:|
| 1 | -17.350 / 0.780× | -18.167 / 0.843× | -22.787 / 0.891× |
| 2 | -16.257 / 0.793× | -16.900 / 0.853× | -18.342 / 0.912× |
| 3 | -17.359 / 0.783× | -17.471 / 0.851× | -16.414 / 0.922× |

Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was +1.39 historical CPU, +1.24 native CPU and +0.44 caller wall.

## toolagent · 128 blocks · decision

2,745 measured cohorts per repetition. Every policy returned 59,799,075 prefill positions.

| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |
|---|---:|---:|---|---|---:|
| FULL = RANK-00 | 0.6929 / 252.44 | 21.25 | 0.7731 / 281.6 / 562.0 / 585.0 / 628.0 | 0.8979 / 327.1 / 612.2 / 640.2 / 879.8 | 3.58 |
| FOCUSED | 0.1055 / 38.42 | 20.47 | 0.1828 / 66.6 / 136.0 / 181.0 / 274.0 | 0.3042 / 110.8 / 189.2 / 240.0 / 421.9 | 4.08 |
| RANK-10 | 0.3205 / 116.76 | 21.24 | 0.4008 / 146.0 / 384.0 / 500.0 / 618.0 | 0.5247 / 191.1 / 436.2 / 559.6 / 798.6 | 4.00 |
| RANK-01 | 0.3503 / 127.62 | 20.96 | 0.4292 / 156.4 / 387.0 / 440.0 / 773.0 | 0.5520 / 201.1 / 433.2 / 491.5 / 1149.2 | 4.09 |
| RANK-11 | 0.1650 / 60.10 | 21.09 | 0.2443 / 89.0 / 198.0 / 270.0 / 385.0 | 0.3660 / 133.4 / 246.5 / 326.1 / 495.0 | 3.97 |

Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.

| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |
|---|---|---|---|---:|---|---:|---|---|
| FULL = RANK-00 | 267,672 / 1,987,151 | 0 / 0 / 0 | 0 / 0 | 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 8,552 / 0 / 0 |
| FOCUSED | 46,610 / 354,068 | 241,281 / 139,871 / 24,610,688 | 101,410 / 54,800 | 2,648 | 4,282,752 / 5,826,646 / 2,421,836 | 327,700 | 5,966,080 / 354,068 / 28,688,328 | 28,044 / 4,736 / 2,056 |
| RANK-10 | 114,705 / 868,101 | 267,672 / 152,967 / 27,282,304 | 0 / 0 | 0 | 0 / 0 / 0 | 327,700 | 0 / 0 / 0 | 28,044 / 0 / 0 |
| RANK-01 | 118,093 / 879,879 | 0 / 0 / 0 | 241,281 / 123,188 | 2,648 | 4,282,752 / 12,194,093 / 6,128,002 | 327,700 | 0 / 0 / 0 | 28,044 / 4,736 / 0 |
| RANK-11 | 46,610 / 354,068 | 241,281 / 139,871 / 24,610,688 | 101,410 / 54,800 | 2,648 | 4,282,752 / 5,826,646 / 2,421,836 | 327,700 | 0 / 0 / 0 | 28,044 / 4,736 / 0 |

Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.

| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |
|---|---:|---:|---:|
| FOCUSED | -21.68 / 0.639× | -22.41 / 0.748× | -22.55 / 0.831× |
| RANK-01 | +67.52 / 2.123× | +67.38 / 1.757× | +67.73 / 1.508× |
| RANK-10 | +56.67 / 1.943× | +57.02 / 1.641× | +57.79 / 1.433× |
| FULL = RANK-00 | +192.34 / 4.200× | +192.63 / 3.164× | +193.75 / 2.453× |

FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.

| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |
|---|---:|---:|---:|
| 1 | -57.244 / 0.649× | -58.465 / 0.758× | -61.314 / 0.832× |
| 2 | -63.571 / 0.619× | -68.038 / 0.725× | -68.137 / 0.816× |
| 3 | -57.694 / 0.651× | -58.005 / 0.762× | -56.245 / 0.845× |

Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was +68.15 historical CPU, +68.24 native CPU and +68.23 caller wall.

## toolagent · 128 blocks · absolute

2,745 measured cohorts per repetition. Every policy returned 59,799,075 prefill positions.

| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |
|---|---:|---:|---|---|---:|
| FULL = RANK-00 | 0.6869 / 250.25 | 21.01 | 0.7664 / 279.2 / 560.0 / 584.0 / 726.0 | 0.9506 / 346.3 / 620.2 / 688.4 / 28416.1 | 3.75 |
| FOCUSED | 0.1087 / 39.61 | 20.53 | 0.1861 / 67.8 / 135.0 / 180.0 / 255.0 | 0.3135 / 114.2 / 189.1 / 243.0 / 487.5 | 4.11 |
| RANK-10 | 0.3197 / 116.48 | 21.13 | 0.3995 / 145.5 / 381.0 / 501.0 / 627.0 | 0.5308 / 193.4 / 438.0 / 560.3 / 820.5 | 3.78 |
| RANK-01 | 0.3541 / 129.00 | 20.50 | 0.4316 / 157.2 / 376.0 / 437.0 / 571.0 | 0.5625 / 204.9 / 430.4 / 497.2 / 1058.0 | 4.06 |
| RANK-11 | 0.1686 / 61.40 | 20.86 | 0.2472 / 90.1 / 195.0 / 274.0 / 414.0 | 0.3790 / 138.1 / 253.0 / 341.2 / 964.3 | 4.14 |

Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.

| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |
|---|---|---|---|---:|---|---:|---|---|
| FULL = RANK-00 | 269,288 / 1,999,297 | 0 / 0 / 0 | 0 / 0 | 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 8,552 / 0 / 0 |
| FOCUSED | 48,403 / 367,646 | 245,545 / 142,342 / 25,038,848 | 101,410 / 54,800 | 0 | 4,282,752 / 5,826,646 / 2,421,836 | 327,700 | 6,195,584 / 367,646 / 29,734,411 | 28,044 / 4,736 / 2,056 |
| RANK-10 | 115,318 / 872,785 | 269,288 / 153,970 / 27,444,096 | 0 / 0 | 0 | 0 / 0 / 0 | 327,700 | 0 / 0 / 0 | 28,044 / 0 / 0 |
| RANK-01 | 122,357 / 911,695 | 0 / 0 / 0 | 241,281 / 123,188 | 0 | 4,282,752 / 12,194,093 / 6,128,002 | 327,700 | 0 / 0 / 0 | 28,044 / 4,736 / 0 |
| RANK-11 | 48,403 / 367,646 | 245,545 / 142,342 / 25,038,848 | 101,410 / 54,800 | 0 | 4,282,752 / 5,826,646 / 2,421,836 | 327,700 | 0 / 0 / 0 | 28,044 / 4,736 / 0 |

Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.

| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |
|---|---:|---:|---:|
| FOCUSED | -21.80 / 0.645× | -22.29 / 0.753× | -23.87 / 0.827× |
| RANK-01 | +67.60 / 2.101× | +67.17 / 1.746× | +66.83 / 1.484× |
| RANK-10 | +55.07 / 1.897× | +55.45 / 1.616× | +55.31 / 1.401× |
| FULL = RANK-00 | +188.85 / 4.076× | +189.14 / 3.100× | +208.24 / 2.508× |

FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.

| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |
|---|---:|---:|---:|
| 1 | -63.498 / 0.626× | -67.488 / 0.729× | -70.898 / 0.813× |
| 2 | -58.754 / 0.655× | -58.989 / 0.764× | -62.384 / 0.837× |
| 3 | -57.230 / 0.654× | -57.085 / 0.765× | -63.326 / 0.832× |

Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was +66.18 historical CPU, +66.51 native CPU and +86.10 caller wall.

Source data, separate repetition totals and all component high-water marks are in [summary.json](summary.json). The [cell receipts](timing_receipts.jsonl) include whole-process CPU, peak resident memory, elapsed time and raw-record hashes. The [frozen schedule and source digests](freeze.json) and [verification receipt](verification_receipt.json) identify the exact comparisons.
