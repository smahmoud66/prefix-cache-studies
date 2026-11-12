#!/usr/bin/env python3
"""Inspect the published evidence or reproduce in a fresh POSIX directory."""
import argparse, gzip, hashlib, json, shutil, subprocess, sys, tarfile, tempfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
E, O = 'focused_comparison_20261109', 'prefix_order_pilot_20261112'
Q, M, H = 'external_tie_20261109', 'commitment_20261108', 'exit_cache_20261108'
def read(p): return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def run(cmd, cwd): subprocess.run(cmd, cwd=cwd, check=True)
def py(name, cwd, *args): run([sys.executable, name, *args], cwd)
def unpack(src,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(src,'rb') as i, dest.open('xb') as o: shutil.copyfileobj(i,o)
def seeds(work): shutil.copytree(ROOT/'research',work/'research')
def fetch(work,names):
    manifest=read(ROOT/'data/upstream.json')
    for key in names:
        v=manifest[key]; dest=work/'research'/v['path'];dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with tempfile.NamedTemporaryFile(dir=dest.parent,delete=False) as out: t=Path(out.name)
            try:
                print('Fetching',key,flush=True)
                with urlopen(Request(v['url'],headers={'User-Agent':'prefix-cache-studies-reproduction/1.0'}),timeout=180) as src, t.open('wb') as out: shutil.copyfileobj(src,out)
                if sha(t)!=v['sha256']: raise ValueError(f'Upstream digest mismatch: {key}')
                t.replace(dest)
            finally: t.unlink(missing_ok=True)
        if sha(dest)!=v['sha256']: raise ValueError(f'Input digest mismatch: {key}')
def summary():
    ev=ROOT/'research'/E; order=ROOT/'research'/O
    cells=read(ev/'summary.json')['cells']; m=cells['toolagent_128_decision']['methods']
    print('Tool/agent, C=128, decision: FULL to FOCUSED replays:',m['FULL']['counters_per_rep']['rollouts'],'to',m['FOCUSED']['counters_per_rep']['rollouts'])
    print('Complete CPU (microseconds): FOCUSED %.2f; RANK-11 %.2f'%tuple(m[k]['timing']['native_cpu']['mean_us'] for k in ('FOCUSED','R11')))
    print('Timing cells with identical replay counts:',sum(x['methods']['R11']['counters_per_rep']['rollouts']==x['methods']['FOCUSED']['counters_per_rep']['rollouts'] for x in cells.values()),'of',len(cells))
    print('FreeInference: maxima by waiting limit (% of FCFS modeled prefill work)')
    for w in (500,2000):
        rows=[x for x in read(order/'heldout_cells.json') if x['W']==w]
        print(w,'ms:',{k:round(max(x[k] for x in rows),3) for k in ('g1','g2_order','g2_mixed','g3')},'material order/mixed:',sum(x['material'] for x in rows),sum(x['literal_material'] for x in rows),'of',len(rows))
    d=read(order/'decision.json'); print('Primary joint precision:',d['literal_material']['precision'],'; go:',d['literal_material']['go'])
def clean_outputs(root,names):
    # Only called inside a newly created scratch tree.
    for name in names:
        p=root/name
        if p.is_dir(): shutil.rmtree(p)
        elif p.is_file(): p.unlink()
def compile_order(o):
    (o/'build').mkdir(exist_ok=True)
    run(['c++','-O3','-std=c++17','simulator.cpp','-o','build/pilot'],o)
def checks(work):
    seeds(work); r=work/'research'; e,o=r/E,r/O
    py('build.py',e);py('verify_focused.py',e,'--native','./evaluator');py('test_vectors.py',e)
    py('check_primary.py',e)
    again=read(e/'primary_readback.json'); archived=read(ROOT/'research'/E/'primary_readback.json')
    for key in ('primary_native_rows_read','ratios_by_rep_history_native_wall'):assert again[key]==archived[key]
    with tarfile.open(ROOT/'data/external-timing-rows.tar.gz') as pack:
        (r/Q/'runs').mkdir()
        for ent in pack.getmembers():
            assert ent.isfile() and ent.name==Path(ent.name).name and ent.name.endswith('.tsv')
            with pack.extractfile(ent) as i, (r/Q/'runs'/ent.name).open('xb') as out: shutil.copyfileobj(i,out)
    for s in (r/Q/'run_receipts.jsonl').read_text().splitlines():
        rec=json.loads(s);assert sha(r/Q/'runs'/(rec['tag']+'.tsv'))==rec['output_sha256']
    for lab in 'AB': unpack(ROOT/'data'/('qwen-'+lab+'-cohorts.json.gz'), r/Q/'panel'/(lab+'_gate.json'))
    py('audit_primary.py',r/Q)
    compile_order(o); run(['./build/pilot','fixtures'],o); py('verify.py',o,'fixtures')
    unpack(ROOT/'data/panels-freeinference.txt.gz',o/'panels/freeinference.txt')
    assert sha(o/'panels/freeinference.txt')==read(o/'panels/freeinference.json')['panel_sha256']
    (o/'heldout_audit.json').unlink()
    py('verify.py',o)
    orig=read(ROOT/'research'/O/'heldout_audit.json'); v=read(o/'heldout_audit.json')
    assert (v['witnesses'],v['request_starts_checked'])==(orig['witnesses'],orig['request_starts_checked'])==(180,540000)
    stages=[json.loads(x) for x in (o/'events.jsonl').read_text().splitlines()]
    lock=next(x for x in stages if x['stage']=='heldout_predictions_locked')
    start=next(x for x in stages if x['stage']=='heldout_outcomes_started')
    assert lock['utc']<start['utc'] and lock['prediction_sha256']==sha(o/'heldout_predictions.json')==start['prediction_sha256']
    print('PASS: native semantic fixtures, stored timing counters, external timings, frozen predictions and all 540,000 held-out starts.')
def replay_order(work):
    seeds(work);r=work/'research';o=r/O
    fetch(work,['conversation','toolagent','qwenA','qwenB','freeinference'])
    for lab in 'AB':py('adapter.py',r/Q,lab)
    py('group_panel.py',r/Q);py('prepare.py',r/'exit_aware_opportunity')
    clean_outputs(o,['raw','panels','fitted.json','heldout_predictions.json','events.jsonl','heldout_audit.json','heldout_cells.json','development_cells.json','decision.json','freeze.json','fixtures.json'])
    py('prepare.py',o,'conversation','toolagent','qwenchat','qwenapi'); compile_order(o)
    b=subprocess.check_output(['./build/pilot','fixtures'],cwd=o,text=True).strip()
    v=json.loads(subprocess.check_output([sys.executable,'verify.py','fixtures'],cwd=o,text=True))
    (o/'fixtures.json').write_text(json.dumps({'state_checks':b,'synthetic_scores':v},indent=2)+'\n')
    py('execute.py',o,'freeze');py('execute.py',o,'run')
    recorded=read(ROOT/'research'/O/'decision.json');assert recorded==read(o/'decision.json')
    print('Reproduced published decision. This is a replication on exposed data.')
def benchmark(work):
    seeds(work);r=work/'research';e=r/E
    fetch(work,['conversation','toolagent'])
    unpack(ROOT/'data/exit_cache_20261108-online.jsonl.gz',r/H/'online.jsonl')
    frozen=read(e/'freeze.json');py('build.py',e)
    for name,h in frozen['hashes'].items():
        if name!='evaluator': assert sha(e/name)==h, name
    # The historical freeze is retained in the distribution. Only the copy under --work
    # receives a fingerprint for the locally compiled binary.
    frozen['hashes']['evaluator']=sha(e/'evaluator')
    (e/'freeze.json').write_text(json.dumps(frozen,indent=2)+'\n')
    clean_outputs(e,['timings','reference_vectors.jsonl.gz','timing_receipts.jsonl','benchmark_receipt.json','verification_receipt.json'])
    py('run_panel.py',e);py('analyze_panel.py',e);py('check_primary.py',e);py('measurement_tables.py',e)
    source=read(ROOT/'research'/E/'summary.json')['cells'];new=read(e/'summary.json')['cells']
    for k,v in source.items():
        for m,method in v['methods'].items():
            for field in ('cohorts_per_rep','prefill_per_rep','counters_per_rep'):
                assert new[k]['methods'][m][field]==method[field],(k,m,field)
    print('Matched work and counters; timings describe this new machine.')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('summary','verify','benchmark-evaluator','replay-ordering'))
    p.add_argument('--work',type=Path,help='New, nonexistent path; required for a numerical replication.')
    a=p.parse_args()
    if a.action=='summary': return summary()
    if a.work:
        work=a.work.resolve();work.mkdir(parents=True,exist_ok=False)
        return {'verify':checks,'benchmark-evaluator':benchmark,'replay-ordering':replay_order}[a.action](work)
    if a.action=='verify':
        with tempfile.TemporaryDirectory(prefix='prefix-cache-verify-') as t: checks(Path(t))
    else: p.error('--work NEW_PATH is required')
if __name__=='__main__':main()
