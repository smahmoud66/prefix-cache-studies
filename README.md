# Prefix cache studies

This repository accompanies *Exact Evaluation of Adaptive Prefix-Cache Continuations* by **Mohammad Ali Seyed Mahmoud**, Georgia Institute of Technology ([contact](mailto:m.seyedmahmoud@gatech.edu)). It includes the evaluator and a separate trace-replay pilot on request ordering.

| Study | Main observation | Start here |
|---|---|---|
| Exact evaluation of adaptive cache continuations | Complete-state and focused-state replay agreed on every checked score and reused the same terms by construction. In one 128-block tool/agent condition, the focused implementation took 66.59 microseconds per decision and the full-state implementation with the same shortcuts took 89.00. No independent planner benefit was demonstrated. | [Evaluator: code and results](docs/evaluator.md) |
| Request ordering under a waiting limit | None of 36 primary configurations on one held-out FreeInference period achieved the registered 3% modeled prefill saving through ordering. Nine qualified at the smallest cache when the offline reference could also change eviction. These are CPU simulations, not GPU latency measurements. | [Ordering: code and results](docs/ordering.md) |

The [technical report and its source](papers/README.md) form the sole arXiv package. The [v1.2.0 release](https://github.com/smahmoud66/prefix-cache-studies/releases/tag/v1.2.0) contains the source upload, review PDF, submission metadata and checksums. The [full ordering pilot](research/prefix_order_pilot_20261112/result.md) includes its protocol, held-out results and audit.

To print the two headline tables using Python 3.11+:

```sh
python3 tools/reproduce.py summary
```

The [reproduction guide](docs/reproduce.md) describes the offline audit and optional full CPU replications. [Data sources](data/README.md) lists the pinned public inputs, transformations and attribution. Scientific code, comparison baselines, numerical outputs and original freeze records are under `research/`. The dated folder names preserve the relative imports in the frozen programs. The top-level guides are the entry points for this distribution.

The technical report and the companion pilot report are available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The original software currently has no reuse license. See the [upstream terms](data/README.md) for the datasets.
