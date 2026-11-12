# Prefix cache studies

Two research artifacts by **Mohammad Ali Seyed Mahmoud**, Georgia Institute of Technology ([contact](mailto:m.seyedmahmoud@gatech.edu)). Both studies concern the prefill work that remains when requests share prompt prefixes. They ask different questions:

| Study | Main observation | Start here |
|---|---|---|
| Exact evaluation of adaptive cache continuations | Two exact implementations saved the same replays across eight conditions. In one 128-block tool/agent condition, the focused implementation took 66.59 microseconds per decision and the full-state implementation with the same shortcuts took 89.00. No independent planner benefit was demonstrated. | [Evaluator: code and results](docs/evaluator.md) |
| Request ordering under a waiting limit | None of 36 primary configurations on one held-out FreeInference period achieved the registered 3% modeled prefill saving through ordering. Nine qualified when the offline reference could also change eviction. These are CPU simulations, not GPU latency measurements. | [Ordering: code and results](docs/ordering.md) |

To print the two headline tables using Python 3.11+:

```sh
python3 tools/reproduce.py summary
```

The [reproduction guide](docs/reproduce.md) describes the offline audit and optional full CPU replications. [Data sources](data/README.md) lists the pinned public inputs, transformations and attribution. Scientific code, comparison baselines, numerical outputs and original freeze records are under `research/`. The dated folder names preserve the relative imports in the frozen programs. The top-level guides are the entry points for this distribution.
