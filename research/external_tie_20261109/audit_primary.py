"""Independently check primary prefill/time contrasts without running scheduling policies."""
import csv
import hashlib
import json
import statistics
import time
from pathlib import Path

here = Path(__file__).resolve().parent
cpu_start = time.process_time()
out = {}
for w in "AB":
    gates = json.loads((here / "panel" / f"{w}_gate.json").read_text())
    results = {}
    for target, seed in [("FCFS",0),("K",0),("IMM",0),("OPT",0),("RANK",0),
                         ("RAND",1729),("RAND",314159),("RAND",271828)]:
        method = target if target != "RAND" else f"RAND{seed}"
        reps = []
        for repeat in [1, 2]:
            work = 0
            wait = 0
            n_requests = 0
            wall = 0
            changed = 0
            tokens = 0
            windows = [0,0,0,0]
            trajectory = hashlib.sha256()
            with (here / "runs" / f"{w}_512_128_{target}_{seed}_{repeat}.tsv").open() as file:
                for row, gate in zip(csv.DictReader(file, delimiter="\t"), gates, strict=True):
                    if gate["phase"] == "W":
                        assert row["stage"] == "W"
                        continue
                    assert row["stage"] == "G"
                    cost = int(row["work"])
                    input_tokens = gate["tokens"]
                    n = int(row["n"])
                    assert len(gate["wait_ms"]) == n and not (input_tokens-cost)%512
                    assert 0 <= input_tokens - cost <= 65536*n
                    if w=="B":
                        assert cost == input_tokens
                    windows[n_requests//5000] += cost
                    work += cost
                    wait += sum(gate["wait_ms"])
                    n_requests += n
                    wall += int(row["wall_ns"])
                    changed += int(row["changed"])
                    tokens += input_tokens
                    trajectory.update(f"{row['order']}:{cost};".encode())
            assert n_requests == 20000
            reps.append([work,windows,changed,tokens,wait,trajectory.hexdigest(),wall])
        assert reps[0][:-1] == reps[1][:-1]
        work,windows,changed,tokens,wait,_,_ = reps[0]
        results[method] = dict(work=work, windows=windows, changed=changed,
                               mean_wait_ms=wait/20000, input_tokens=tokens,
                               mean_wall_ns=statistics.mean(r[-1] for r in reps))
    opt = results["OPT"]
    out[w] = {}
    for k, r in results.items():
        d = r["work"]-opt["work"]
        out[w][k]=dict(delta=d,by_window=[a-b for a,b in zip(r["windows"],opt["windows"])],
                       relative=d/r["work"], per_req=d/20000,
                       extra_ns=opt["mean_wall_ns"]-r["mean_wall_ns"], initial=r, optimized=opt)
s = json.loads((here/"summary.json").read_text())
for w, block in out.items():
    for name, v in block.items():
        p = s["comparisons"][f"{w}_512_128"][name]
        assert p["savings"] == v["delta"] and p["window_savings"]==v["by_window"]
        assert p["fraction"]==v["relative"] and p["savings_per_request"]==v["per_req"]
        assert p["extra_decision_wall_ns"]==v["extra_ns"]
        actual = v["extra_ns"]/v["delta"] if v["delta"]>0 else None
        assert actual == p["break_even_ns_per_position"]
print(json.dumps(dict(primary=out, cpu_s=time.process_time()-cpu_start),indent=2))
