# Reproduction guide

Use a POSIX machine (Linux or macOS) with Python 3.11+, a C++17 compiler on PATH as `c++`, and NumPy. The original machine used Apple clang and an Apple M2. No model, cluster login, API key or GPU is required. Create a virtual environment if needed. `python3 -m pip install numpy` suffices for the offline verification and the numerical replay. The other packages in [requirements.txt](../requirements.txt) are for plotting and rebuilding the upstream calibration.

**Inspect and verify the published outcomes.** Run from the repository root:

```sh
python3 tools/reproduce.py summary
python3 tools/reproduce.py verify
```

The first command reads small JSON summaries. The second uses a temporary directory: it builds the two native components, checks focused updates and exact score vectors against independent fixtures, re-reads the native timing counters, checks the external TSV digests, verifies that predictions were locked before the held-out scoring and audits every saved primary start. It neither trains a rule nor rescores the held-out traffic. Use `--work PATH` with a nonexistent path to retain the verification copy. The reference outputs remain unchanged.

**Replicate the evaluator benchmark on a new machine.** A fresh benchmark downloads the two pinned Mooncake inputs (about 7.5 MB), checks their SHA-256 digests, rebuilds the native binary and repeats the frozen cohorts and interfaces with three timing repetitions. The local binary gets a new digest in the scratch copy. Work and counts should match; CPU and wall times depend on the machine.

```sh
python3 tools/reproduce.py benchmark-evaluator --work /tmp/new-evaluator-replication
```

**Replicate the ordering study from source traces.** Also install the `zstd` executable and `clang++` (used for the compiler fingerprint). The little-endian trace adapter streams the data; it does not expand the full FreeInference file on disk. The command downloads the public source objects using [the input manifest](../data/upstream.json), verifies their digests, rebuilds the Qwen panels, compiles the simulator, freezes the new environment and reproduces the original pipeline in a fresh directory. A new run uses already-exposed data: it does not create a second independent test. The saved command below is optional; verification above suffices to audit the published result.

```sh
python3 tools/reproduce.py replay-ordering --work /tmp/new-ordering-replication
```

For the original coefficient fit, [the exported NVIDIA component points](../research/prefix_order_pilot_20261112/sources/profile_points.json) are sufficient for [calibrate.py](../research/prefix_order_pilot_20261112/calibrate.py) (NumPy and SciPy); [export_profile.py](../research/prefix_order_pilot_20261112/export_profile.py) can extract them from the two pinned component Parquet files using DuckDB. The [exact hash and provenance record](../research/prefix_order_pilot_20261112/freeze.json) describes the original machine, inputs and historical file layout, including nonportable binaries not redistributed here.
