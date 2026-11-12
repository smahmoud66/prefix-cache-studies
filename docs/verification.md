# Release checks

The offline release audit was run from the packaged files on November 12, 2026. Both C++ components compiled from source. The evaluator passed its independent semantic fixtures and candidate-vector tests. Published native timings and counters were re-read from the compressed rows, and the external Qwen timing files matched their recorded digests. The ordering simulator passed the 4,000 cache-pair fixtures and a synthetic 14,400-start audit. The independent audit of the saved held-out schedules reproduced 180 trajectories and checked 540,000 starts (maximum absolute numerical difference below 4.5 × 10⁻⁸ ms). The fitted rule and prediction digest preceded held-out scoring in the saved event log.

These are checks of the original evidence. This release did not produce a new blind test or a new GPU measurement.
