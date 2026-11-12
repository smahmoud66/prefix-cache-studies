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

The largest extra gain with LRU unchanged was 0.591% in the primary grid. The mixed offline comparator can choose both an order and a different eviction rule; it cannot establish an ordering-only gain. Neither it nor the tested ordering policies are optimality proofs. See the [reproduction guide](reproduce.md).
