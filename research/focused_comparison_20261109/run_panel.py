"""Matched comparison on recorded Mooncake episodes. No evaluation data or policy selection."""
from collections import Counter
from collections import deque
import datetime as dt
import gzip
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random
import resource
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
PREV = ROOT.parent / 'exact_tie_20261108'
spec = importlib.util.spec_from_file_location('archived_benchmark', PREV/'benchmark.py')
archive = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = archive
spec.loader.exec_module(archive)
METHODS = ('FULL','FOCUSED','R10','R01','R11')
REPS = (1,2,3)
SCHEDULE_SEED = 20261109


def sha(path):
    with path.open('rb') as f:
        h = hashlib.sha256()
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
        return h.hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def usage():
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time()+child.ru_utime+child.ru_stime


class Native(archive.Native):
    def __init__(self):
        self.proc=subprocess.Popen([str(ROOT/'evaluator')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   text=True,encoding='ascii',bufsize=1)


def packed(order):
    code=0
    for index in order:
        code=(code<<2)|index
    return code


def oracle_vectors(ep,traj):
    """Independent stamped-leaf updates (parent Python). All permutations on both archived integration bins."""
    history=deque(ep.warm_groups,maxlen=16)
    state=ep.initial.copy()
    tick=ep.tick
    vectors=[]
    calls=0
    for group,target in zip(ep.groups,traj):
        cohort=archive.base.Cohort(group,ep.trie,ep.cap,False,tick)
        reps={}
        inc=tuple(target['incumbent'])
        for order in itertools.permutations(range(len(group))):
            cost,_,exit_state=cohort.roll(state,'DFS',order)
            if cost!=target['miss']: continue
            key=tuple(archive.old.canonical(exit_state,ep.trie))
            if key not in reps or order==inc:
                reps[key]=(order,exit_state)
        assert reps
        result=[]
        for order,exit_state in reps.values():
            past=list(history)
            total=0
            for first in range(len(past)%2,len(past),2):
                after=exit_state
                clock=tick+len(group)
                for g in past[first:first+2]:
                    q=archive.base.Cohort(g,ep.trie,ep.cap,False,clock)
                    missing,_,after=q.roll(after,'kLPM')
                    total+=missing
                    clock+=len(g)
                calls+=1
            result.append([packed(order),total])
        vectors.append(sorted(result))
        _,_,state=cohort.roll(state,'DFS',target['order'])
        tick+=len(group)
        history.append(group)
    return vectors,calls


def check(row,t,expected_vector,absolute):
    assert row['order']==t['order'] and row['selected_exit']==t['state']
    assert row['immediate_blocks']==t['miss'] and row['incumbent']==t['incumbent']
    if absolute:
        scores=sorted(row['candidate_scores'])
        assert scores and len(scores)==len({code for code,_ in scores})==row['candidate_states']
        winner=packed(t['order'])
        assert dict(scores)[winner]==min(v for _,v in scores)==t['future']
        assert (row['den'],row['future_blocks'],row['objective_num'])==(t['den'],t['future'],t['value'])
        if expected_vector is not None: assert scores==expected_vector, 'absolute candidate-vector disagreement'
        return scores
    assert not row.get('candidate_scores')


def archived_winners(episodes):
    archive_path=PREV/'equivalence.jsonl.gz'
    assert sha(archive_path)=='054c0eee80048839d8ea0a9772bff64ec14a929a59d2d5ed803939ded2cf2f2b'
    winners={}
    with gzip.open(archive_path,'rt') as f:
        for line in f:
            stage,tr,bid,cap,i,order,state,work,inc,den,value=json.loads(line)
            key=((stage,tr,bid),cap)
            ep=episodes[key]
            seq=winners.setdefault(key,[])
            assert len(seq)==i
            old=ep.expected['TIE']['cohorts'][i]
            assert order==old['order'] and inc==old['incumbent'] and work==old['prefill']
            missing,rem=divmod(work-ep.tail_tokens[i],512)
            assert rem==0 and missing>=0
            seq.append(dict(order=order,state=state,work=work,incumbent=inc,miss=missing,
                            den=den,value=value,future=value-den*missing))
    assert set(winners)==set(episodes)
    assert all(len(seq)==len(episodes[key].groups) for key,seq in winners.items())
    return winners


def verification(episodes,log):
    native=Native()
    truth=archived_winners(episodes)
    counts=Counter()
    try:
        for key,ep in episodes.items():
            stage,tr,bid=ep.key
            targets=truth[key]
            independent=None
            if stage=='development':
                independent,calls=oracle_vectors(ep,targets)
                counts['integration_independent_historical_pair_rollouts']+=calls
            native.begin(ep,'FULL',True)
            for i,(msg,target) in enumerate(zip(ep.msgs,targets)):
                result=native.call(msg)
                vector=check(result,target,independent[i] if independent is not None else None,True)
                target['scores']=vector
                log.write(json.dumps([stage,tr,bid,ep.cap,i,target],separators=(',',':'))+'\n')
                counts[stage+'_full_vectors']+=1
                counts[stage+'_candidate_scores']+=len(vector)
            # Every integration case on each implementation, both modes.
            # All online comparisons are subsequently checked on EACH timed repetition.
            if stage=='development':
                for m in METHODS:
                    for absolute in (False,True):
                        if m=='FULL' and absolute: continue
                        native.begin(ep,m,absolute)
                        for msg,t in zip(ep.msgs,targets):
                            check(native.call(msg),t,t['scores'],absolute)
                            counts['integration_additional_checked_calls']+=1
    finally:
        used=native.close()
    return truth,dict(counts),used


def timed(keys,episodes,truth,method,absolute,rep,path):
    begin=time.monotonic();cpu=time.process_time()
    native=Native()
    work=0;called=0
    try:
        with gzip.open(path,'xt',compresslevel=1) as raw:
            for key in keys:
                ep=episodes[key]
                native.begin(ep,method,absolute)
                episode_sum=0
                for i,(msg,t) in enumerate(zip(ep.msgs,truth[key])):
                    wall=time.perf_counter_ns()
                    rec=native.call(msg)
                    wall=time.perf_counter_ns()-wall
                    check(rec,t,t['scores'],absolute)
                    positions=ep.tail_tokens[i]+512*rec['immediate_blocks']
                    assert positions==t['work']
                    episode_sum+=positions
                    called+=1
                    vals={k:v for k,v in rec.items() if type(v)==int}
                    vals.update(bin=ep.key[2],i=i,positions=positions,wall_ns=wall)
                    print(json.dumps(vals,separators=(',',':')),file=raw)
                assert episode_sum==ep.expected['TIE']['prefill']
                work+=episode_sum
    finally:
        used=native.close()
    return dict(method=method,absolute=absolute,rep=rep,trace=keys[0][0][1],cap=keys[0][1],
                cohorts=called,prefill=work,child_cpu=used['cpu'],rss_bytes=archive.resident_bytes(used['rss']),
                wrapper_cpu=time.process_time()-cpu,elapsed_s=time.monotonic()-begin,raw=path.name,sha256=sha(path))


def run():
    freeze=json.loads((ROOT/'freeze.json').read_text())
    for name,h in freeze['hashes'].items():
        assert sha(ROOT/name)==h,name
    with (ROOT/'benchmark.lock').open('x') as f: f.write(now()+'\n')
    def stop(*_): raise TimeoutError('numerical replay wall-time guard')
    signal.signal(signal.SIGALRM,stop)
    signal.alarm(1400) # At most one wrapper and one active single-threaded native child.
    tick=time.monotonic();cpu=time.process_time()
    (ROOT/'timings').mkdir(exist_ok=False)
    cells=[]
    try:
        episodes,prep=archive.prepare()
        assert sum(len(ep.groups) for ep in episodes.values())==8766
        before=usage()
        with gzip.open(ROOT/'reference_vectors.jsonl.gz','xt',compresslevel=1) as raw:
            truth,checks,verify_process=verification(episodes,raw)
        verification_cpu=usage()-before
        verification_record=dict(cpu_including_wrapper_and_child=verification_cpu,counts=checks,
            native=verify_process,sha256=sha(ROOT/'reference_vectors.jsonl.gz'))
        (ROOT/'verification_receipt.json').write_text(json.dumps(verification_record,indent=2)+'\n')
        order=random.Random(SCHEDULE_SEED)
        for rep in REPS:
            groups=[(tr,c,absolute) for tr in ('conversation','toolagent') for c in (128,32) for absolute in (False,True)]
            order.shuffle(groups)
            for tr,c,absolute in groups:
                keys=sorted(k for k in episodes if k[0][:2]==('online',tr) and k[1]==c)
                assert len(keys)==28
                methods=list(METHODS)
                order.shuffle(methods)
                for m in methods:
                    name=f'{tr}_{c}_{int(absolute)}_{m}_{rep}.jsonl.gz'
                    cell=timed(keys,episodes,truth,m,absolute,rep,ROOT/'timings'/name)
                    with (ROOT/'timing_receipts.jsonl').open('a') as f: print(json.dumps(cell),file=f)
                    cells.append(cell)
            print('Completed repetition',rep,flush=True)
        assert len(cells)==120
        result=dict(status='COMPLETE',cells=len(cells),preparation=prep,verification=verification_record,
                    stage_cpu_including_wrapper_and_children=usage(),stage_wrapper_cpu=time.process_time()-cpu,
                    stage_wall=time.monotonic()-tick,finished=now())
        (ROOT/'benchmark_receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    except BaseException as exc:
        (ROOT/'benchmark_failure.json').write_text(json.dumps(dict(status='FAILED',error=repr(exc),
            completed_cells=len(cells),stage_cpu=usage(),stage_wall=time.monotonic()-tick))+'\n')
        raise
    finally:
        signal.alarm(0)


if __name__=='__main__':
    run()
