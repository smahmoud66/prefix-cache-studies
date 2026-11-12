# Request ordering under a waiting limit

[Full pilot results and audit](../research/prefix_order_pilot_20261112/result.md) · [Companion report (PDF)](../reports/ordering/pilot.pdf) · [Report source](../reports/ordering/main.tex)

The CPU simulator measures modeled prefill service separately from waiting. Its waiting bound is an excess over each request's FCFS start. There is no production latency measurement.

| Stage | Artifact |
|---|---|
| Before scoring | [Frozen protocol](../research/prefix_order_pilot_20261112/protocol.md), [source and configuration hashes](../research/prefix_order_pilot_20261112/freeze.json), [service calibration](../research/prefix_order_pilot_20261112/calibration.json) |
| Implementation | [Simulator and policies](../research/prefix_order_pilot_20261112/simulator.cpp), [trace transformations](../research/prefix_order_pilot_20261112/prepare.py), [estimates, fit and decision](../research/prefix_order_pilot_20261112/decide.py) |
| Development and prediction | [Development cells](../research/prefix_order_pilot_20261112/development_cells.json), [fitted rules](../research/prefix_order_pilot_20261112/fitted.json), [36 primary predictions](../research/prefix_order_pilot_20261112/heldout_predictions.json), [chronological event record](../research/prefix_order_pilot_20261112/events.jsonl) |
| Holdout | [Read the result](../research/prefix_order_pilot_20261112/result.md), [all 72 cells](../research/prefix_order_pilot_20261112/heldout_grid.md), [machine-readable cells](../research/prefix_order_pilot_20261112/heldout_cells.json), [individual policy outcomes](../research/prefix_order_pilot_20261112/raw/freeinference.scores.jsonl) |
| Audit | [Independent implementation](../research/prefix_order_pilot_20261112/verify.py), [witnesses](../research/prefix_order_pilot_20261112/raw/freeinference.witness.gz), [audited starts](../research/prefix_order_pilot_20261112/heldout_audit.json), [decision](../research/prefix_order_pilot_20261112/decision.json) |

At the primary waiting limit the best tested LRU order saved up to 1.323% over FCFS. All nine joint positives occurred in the 28.3 GiB pool. At 60% utilization and queue cap 16, the selected future-informed order saved 0.591 additional percentage points over the best online order. Changing eviction on exactly that order added 7.174 points, for 7.765 in total. Each uses the same FCFS denominator. The offline comparator establishes an attained saving without certifying a global optimum. [Reproduction guide](reproduce.md)
