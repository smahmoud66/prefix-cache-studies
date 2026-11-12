"""Execute a frozen panel once, respecting a cumulative numerical CPU limit."""
import datetime as dt
import hashlib
import json
import os
import random
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEDULE = [(512,128),(512,32),(16,4096),(16,1024)]
SEEDS = [1729,314159,271828]
REPS = 2
METHODS = [(s,0) for s in ['FCFS','K','IMM','OPT','RANK']] + [('RAND',s) for s in SEEDS]


def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def child_cpu():
    u = resource.getrusage(resource.RUSAGE_CHILDREN)
    return u.ru_utime + u.ru_stime


def run():
    raw = ROOT / 'runs'
    raw.mkdir(exist_ok=True)
    (ROOT / 'evaluation.lock').open('x').close()
    since = time.process_time()
    freeze = json.loads((ROOT / 'freeze.json').read_text())
    for name, digest in freeze['hashes'].items():
        assert sha(ROOT / name) == digest, name
    rng = random.Random(20261109)
    cells = [(b,c,w,'CHECK',0,0) for b,c in SCHEDULE for w in 'AB']
    for b,c in SCHEDULE:
        for rep in range(1,REPS+1):
            for w in 'AB':
                order = METHODS.copy()
                rng.shuffle(order)
                cells.extend((b,c,w,m,s,rep) for m,s in order)
    receipts = ROOT / 'run_receipts.jsonl'
    for block,cap,w,method,seed,rep in cells:
        tag = f'{w}_{block}_{cap}_{method}_{seed}_{rep}'
        name = 'replay_128' if block == 512 else 'replay_4096'
        cmd = [str(ROOT / name),method,str(cap),str(block),str(seed)]
        if method == 'CHECK':
            cmd.append('16')
        # Room for preparation, validation, summary, and reporting CPU outside this driver.
        limit = int(6600 - child_cpu() - time.process_time())
        if limit < 2 or dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(freeze['expires']):
            raise RuntimeError('frozen resource or expiry stop')
        def bounded():
            resource.setrlimit(resource.RLIMIT_CPU,(limit,limit))
        cpu_before=child_cpu()
        clock=time.monotonic()
        with (ROOT/'panel'/f'{w}_{block}.episode').open('rb') as inp, (raw/f'{tag}.tsv').open('xb') as out, (raw/f'{tag}.log').open('xb') as err:
            with subprocess.Popen(cmd,stdin=inp,stdout=out,stderr=err,preexec_fn=bounded) as p:
                _,status,usage=os.wait4(p.pid,0)
                p.returncode=os.waitstatus_to_exitcode(status)
        rec=dict(tag=tag,block=block,cap=cap,w=w,method=method,seed=seed,rep=rep,
                 code=p.returncode,peak_rss_bytes=usage.ru_maxrss,cpu_s=child_cpu()-cpu_before,wall_s=time.monotonic()-clock,
                 output_sha256=sha(raw/f'{tag}.tsv'))
        with receipts.open('a') as f: print(json.dumps(rec),file=f,flush=True)
        if p.returncode: raise RuntimeError(f'{tag} exited {p.returncode}')
    (ROOT/'replay_receipt.json').write_text(json.dumps(dict(cells=len(cells),children_cpu_s=child_cpu(),driver_cpu_s=time.process_time()-since),indent=2))


if __name__ == '__main__':
    run()
