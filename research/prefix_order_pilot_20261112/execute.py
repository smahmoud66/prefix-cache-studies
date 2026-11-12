"""Execute the pre-hashed CPU pilot once. Stages are append-only; predictions precede all test policy scores."""
import concurrent.futures, datetime, gzip, hashlib, json, os, platform, resource, shutil, subprocess, sys, time
from pathlib import Path
import decide, prepare
R=Path(__file__).resolve().parent
STAMP=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def event(name,**details):
    with (R/'events.jsonl').open('a') as f:f.write(json.dumps(dict(utc=STAMP(),stage=name,**details))+'\n')
def sha(p):return prepare.sha(p)
def frozen():
    names=['protocol.md','calibration.json','calibrate.py','export_profile.py','simulator.cpp','prepare.py','decide.py','verify.py','execute.py','build/pilot','fixtures.json']+[str(p.relative_to(R)) for part in ['panels','sources'] for p in sorted((R/part).glob('*')) if p.is_file()]
    d={p:sha(R/p) for p in names};assert d['sources/freeinference.lcp.zst']==prepare.FI
    decide.save(R/'freeze.json',dict(utc=STAMP(),files=d,compiler=subprocess.check_output(['clang++','--version'],text=True).splitlines()[0],python=platform.python_version()))
    event('freeze',digest=sha(R/'freeze.json'))
def checkfreeze():
    f=decide.read(R/'freeze.json')
    assert all(sha(R/k)==v for k,v in f['files'].items())
def limits():resource.setrlimit(resource.RLIMIT_CPU,(8000,8010))
def sim(s,mode,k):
    c=decide.read(R/'calibration.json');raw=R/'raw';tmp=raw/f'{s}.{mode}.partial';out=raw/f'{s}.{mode}.jsonl';assert not out.exists() and not tmp.exists()
    wit=raw/'freeinference.witness' if mode=='scores' and s==decide.TEST else None
    args=[str(R/'build/pilot'),str(R/'panels'/f'{s}.txt'),mode,*[str(c[p]) for p in ('a_ms','b_ms_per_token','c_ms_per_token2')],str(k),str(tmp),str(wit or '-')]
    subprocess.run([sys.executable,"-c","import os,sys,resource; resource.setrlimit(resource.RLIMIT_CPU,(8000,8010)); os.execv(sys.argv[1],sys.argv[1:])",*args],check=True,timeout=14400);num=len(decide.lines(tmp));assert num==(36 if mode=='features' else 72);tmp.rename(out)
    if wit:
        with wit.open('rb') as a,gzip.open(str(wit)+'.gz','wb',compresslevel=5) as b:shutil.copyfileobj(a,b)
        wit.unlink()
    return dict(name=s,phase=mode,rows=num,digest=sha(out))
def dev(s):
    return [sim(s,'features',0),sim(s,'scores',0)]
def main():
    os.chdir(R);checkfreeze()
    with (R/'execution.lock').open('x') as f:f.write(STAMP()+'\n')
    start=time.monotonic();(R/'raw').mkdir()
    event('development_started')
    # Local jobs use disjoint files. POSIX RLIMIT is applied separately to each child.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fut={ex.submit(dev,s):s for s in decide.DEV}
        for v in concurrent.futures.as_completed(fut):event('development_trace_complete',outputs=v.result())
    decide.train();event('predictors_locked',fitted_sha256=sha(R/'fitted.json'))
    prepare.panel(decide.TEST);event('heldout_panel_created',panel_sha256=sha(R/'panels/freeinference.txt'))
    k=decide.read(R/'fitted.json')['k'];event('heldout_fcfs_features',output=sim(decide.TEST,'features',k))
    decide.predict();pd=sha(R/'heldout_predictions.json');fd=sha(R/'fitted.json');event('heldout_predictions_locked',prediction_sha256=pd,model_sha256=fd)
    with (R/'holdout_scores.lock').open('x') as f:f.write(pd+'\n')
    event('heldout_outcomes_started',prediction_sha256=pd)
    event('heldout_outcomes_complete',output=sim(decide.TEST,'scores',k))
    assert pd==sha(R/'heldout_predictions.json') and fd==sha(R/'fitted.json')
    decide.evaluate()
    subprocess.run([sys.executable,str(R/'verify.py')],check=True,preexec_fn=limits)
    checkfreeze();cpu=resource.getrusage(resource.RUSAGE_CHILDREN);me=resource.getrusage(resource.RUSAGE_SELF)
    sec=cpu.ru_utime+cpu.ru_stime+me.ru_utime+me.ru_stime
    assert sec<172800
    event('verified',cpu_seconds=sec,wall_seconds=time.monotonic()-start,results_sha256=sha(R/'decision.json'),audit_sha256=sha(R/'heldout_audit.json'))
if __name__=='__main__':
    if sys.argv[1]=='freeze':frozen()
    elif sys.argv[1]=='run':main()
