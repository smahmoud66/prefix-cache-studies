"""Frozen replay adapter. Only the external driver owns the future stream."""
import argparse
from collections import Counter, deque
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent / 'commitment_20261108'
sys.path.insert(0, str(PARENT))
import study as base

MODES = ('FCFS', 'kLPM', 'search_LRU', 'portfolio', 'H2', 'H1', 'TIE')
ROLLOUT = {'H2','H1','TIE'}
SPLIT = json.loads((ROOT/'split.json').read_text())


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x') as f:
        json.dump(value, f, separators=(',',':'))
        f.write('\n')


def canonical(state, tree):
    return sorted(state, key=lambda v: (-state[v],tree.depth[v],-v))


def cohort_wire(paths):
    fields = [len(paths)]
    for path in paths:
        fields.append(len(path))
        fields.extend(path)
    return ' '.join(map(str,fields))


def make_message(opcode, cap, state, current, incumbent):
    return ' '.join((opcode,str(cap),str(len(state)),' '.join(map(str,state)),
                     'Q',current,'I',' '.join(map(str,incumbent))))


class Native:
    def __init__(self, offline=False):
        self.proc = subprocess.Popen([str(ROOT/'engine'), '--hindsight' if offline else '--online'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='ascii',bufsize=1)

    def call(self, line):
        self.proc.stdin.write(line+'\n')
        self.proc.stdin.flush()
        answer = json.loads(self.proc.stdout.readline())
        if 'error' in answer:
            raise RuntimeError(answer['error'])
        return answer

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()


def read_bin(trace, rows, bid):
    start, stop = rows[0][0],rows[-1][0]+1
    edges = [start+((stop-start)*k+47)//48 for k in range(49)]
    left,right = edges[bid:bid+2]
    warm, measure = [],[]
    for ts,line,length,raw_ids in rows:
        if left<=ts<right:
            req=base.Request(line,ts,length,tuple(raw_ids[:max(0,(length-1)//512)]))
            (warm if 4*(ts-left)<right-left else measure).append(req)
    boundary = left+(right-left+3)//4
    warm_groups,_=base.gates(warm,boundary)
    groups,flush=base.gates(measure,right)
    return warm_groups,groups,flush


def materialize(group, tree):
    return tuple(base.Request(r.line,r.arrival,r.tokens,tree.path(r.path)) for r in group)


def warm_start(raw_groups,cap):
    tree=base.Trie()
    state,tick,work={},0,0
    history=deque(maxlen=16)
    for raw in raw_groups:
        group=materialize(raw,tree)
        for r in group:
            q=base.Cohort([r],tree,cap,False,tick)
            state,miss=q.step(state,0,1)
            work+=r.tokens-512*(len(q.paths[0])-miss)
            tick+=1
        history.append(cohort_wire([r.path[:cap] for r in group]))
    return tree,state,tick,history,work


def sample_unchanged(trace,bid,cap,index):
    label=f'{trace}/{bid}/{cap}/{index}'.encode()
    return int(hashlib.sha256(label).hexdigest()[:8],16)%16==0


def decide(mode,state,tick,group,tree,cap,history,engine):
    """Online boundary: observed trie metadata, present group, past groups only."""
    q=base.Cohort(group,tree,cap,mode=='portfolio',tick)
    if mode not in ROLLOUT:
        miss,order,after=q.schedule(state,mode)
        return miss,list(order),after,dict(parent_transitions=q.ops['simulated_transitions'])
    minmiss,inc,incstate=q.schedule(state,'search_LRU')
    ordered=canonical(state,tree)
    current=cohort_wire(q.paths)
    g=len(history)//2*2
    past=list(history)[len(history)-g:]
    msg=make_message('D '+mode,cap,ordered,current,inc)+' H '+str(g)+' '+' '.join(past)
    rec=engine.call(msg)
    order=rec['order']
    assert rec['incumbent']==list(inc) and rec['min_blocks']==minmiss
    if tuple(order)==inc:
        after,miss=incstate,minmiss
    else:
        miss,_,after=q.roll(state,'DFS',order)
    assert sorted(order)==list(range(len(group))) and miss==rec['immediate_blocks']
    assert canonical(after,tree)==rec.pop('selected_exit')
    rec.update(parent_transitions=q.ops['simulated_transitions'],
               same_residents_as_incumbent=(after.keys()==incstate.keys()),
               same_full_exit_as_incumbent=(canonical(after,tree)==canonical(incstate,tree)))
    return miss,order,after,rec


def run_bin(trace,rows,bid,engine,development):
    warm,groups,flush=read_bin(trace,rows,bid)
    record={'workload':trace,'bin':bid,'n':sum(map(len,groups)),'input_tokens':sum(r.tokens for g in groups for r in g),
            'groups':[[r.line for r in g] for g in groups],'warm_n':sum(map(len,warm)),
            'wait_ms':[f-r.arrival for g,f in zip(groups,flush) for r in g],
            'max_transient':max((r.tokens for g in warm+groups for r in g),default=0),'capacities':{}}
    assert all(0<=w<=1000 for w in record['wait_ms'])
    for cap in (128,32):
        tree,initial,tick,hist,warm_work=warm_start(warm,cap)
        states={mode:initial.copy() for mode in MODES}
        histories={mode:deque(hist,maxlen=16) for mode in MODES}
        runs={mode:{'prefill':0,'cohorts':[]} for mode in MODES}
        audits=[]
        for j,raw in enumerate(groups):
            group=materialize(raw,tree)
            total=sum(r.tokens for r in group)
            cacheable=sum(min(len(r.path),cap) for r in group)
            hist_msg=cohort_wire([r.path[:cap] for r in group])
            for mode in MODES:
                before=states[mode]
                wall0=time.perf_counter_ns();cpu0=time.process_time_ns()
                misses,order,after,meta=decide(mode,before,tick,group,tree,cap,histories[mode],engine)
                wrap_cpu=time.process_time_ns()-cpu0; wall=time.perf_counter_ns()-wall0
                assert len(after)<=cap and all(tree.parent[v]==0 or tree.parent[v] in after for v in after)
                assert sorted(order)==list(range(len(group)))
                maxmove=max((abs(pos-i) for pos,i in enumerate(order)),default=0)
                assert maxmove<=3
                cost=total-512*(cacheable-misses)
                entry=dict(order=order,prefill=cost,wall_ns=wall,wrapper_cpu_ns=wrap_cpu,
                           max_displacement=maxmove,**{k:v for k,v in meta.items() if k!='order'})
                runs[mode]['cohorts'].append(entry)
                runs[mode]['prefill']+=cost
                if mode=='H2':
                    changed=order!=meta['incumbent']
                    if changed or sample_unchanged(trace,bid,cap,j):
                        audits.append(dict(j=j,changed=changed,state=canonical(before,tree),
                            incumbent=meta['incumbent'],order=order,den=meta['den'],
                            advantage_numerator=meta['adv_num_blocks']))
                states[mode]=after
                histories[mode].append(hist_msg)
            tick+=len(group)
        record['capacities'][str(cap)]=dict(warm_prefill=warm_work,runs=runs,audit_entries=audits)
        # Development reproduction against parent is checked after this complete record is saved.
    return record


def diagnose(record,rows,engine):
    trace,bid=record['workload'],record['bin']
    warm,groups,_=read_bin(trace,rows,bid)
    result=dict(workload=trace,bin=bid,capacities={})
    for cap in (128,32):
        tree,initial,_,_,_=warm_start(warm,cap)
        reqs=[materialize(raw,tree) for raw in groups]
        current=record['capacities'][str(cap)]
        output=[]
        for snap in current['audit_entries']:
            j=snap['j']; future=reqs[j+1:j+3]
            if len(future)<2:
                output.append(dict(j=j,changed=snap['changed'],status='truncated_at_bin_end'));continue
            def encode(g):
                return cohort_wire([r.path[:cap] for r in g])
            msg=make_message('X',cap,snap['state'],encode(reqs[j]),snap['incumbent'])
            msg+=' A '+' '.join(map(str,snap['order']))+' F 2 '+' '.join(map(encode,future))
            ans=engine.call(msg)
            assert ans['best_blocks']<=min(ans['selected_blocks'],ans['incumbent_blocks'])
            output.append(dict(j=j,changed=snap['changed'],status='complete',**ans))
        bound=base.lower_bounds(reqs,cap,initial)
        assert all(bound['cut_lb']<=r['prefill'] for r in current['runs'].values())
        result['capacities'][str(cap)]={'diagnostics':output,'offline_bound':bound}
    return result


def read_stage(name):
    return [json.loads(l) for l in (ROOT/(name+'.jsonl')).read_text().splitlines()]


def check_parent(dev):
    prior=[json.loads(l) for name in ['development','evaluation'] for l in (PARENT/(name+'.jsonl')).read_text().splitlines()]
    for d in dev:
        match=next(z for z in prior if (z['workload'],z['bin'])==(d['workload'],d['bin']))
        assert (d['n'],d['warm_n'],d['input_tokens'])==(match['requests'],match['warm_requests'],match['tokens'])
        for c in ('128','32'):
            a,b=d['capacities'][c],match['capacities'][c]
            assert a['warm_prefill']==b['warm_prefill']
            for mode in ['FCFS','kLPM','search_LRU','portfolio']:
                assert a['runs'][mode]['prefill']==b['runs'][mode]['prefill']
                orders=[[d['groups'][j][i] for i in row['order']] for j,row in enumerate(a['runs'][mode]['cohorts'])]
                assert orders==b['runs'][mode]['dispatch_lines']


def cutoff(sig,frame):
    raise TimeoutError('Numerical allocation reached. Preserve partial output.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['development','online','hindsight'])
    stage=parser.parse_args().stage
    if stage=='online':
        freeze=json.loads((ROOT/'freeze.json').read_text())
        for name,expected in freeze['files'].items():
            assert file_hash(ROOT/name)==expected,name
    if stage=='hindsight':
        seal=json.loads((ROOT/'online_receipt.json').read_text())
        assert seal['status']=='COMPLETE' and seal['bins']==56
        assert file_hash(ROOT/'online.jsonl')==seal['raw_sha256']
    cpu0=time.process_time();w0=time.perf_counter()
    used=sum(json.loads(p.read_text())['replay_cpu_seconds'] for p in ROOT.glob('*_receipt.json')
             if p.name in ['development_receipt.json','online_receipt.json'])
    # Conservative upper bound on concurrent wrapper/child CPU. Leave 120 CPU-s for checks/analysis.
    signal.signal(signal.SIGALRM,cutoff)
    signal.alarm(max(1,int((3480-used)/2)))
    out=ROOT/(stage+'.jsonl');count=0
    with out.open('x') as f:
        engine=Native(stage=='hindsight')
        try:
            saved=read_stage('online') if stage=='hindsight' else []
            for trace,frame in SPLIT['traces'].items():
                rows=base.read_trace(trace)
                bins=([3] if trace=='toolagent' else [frame['parent_dev'][0]]) if stage=='development' else frame['new_eval']
                for bid in bins:
                    if stage=='hindsight':
                        online=next(d for d in saved if (d['workload'],d['bin'])==(trace,bid))
                        data=diagnose(online,rows,engine)
                    else:
                        data=run_bin(trace,rows,bid,engine,stage=='development')
                    f.write(json.dumps(data,separators=(',',':'))+'\n');f.flush()
                    count+=1
                    print(stage,trace,bid,'complete',flush=True)
            if stage=='development':check_parent(read_stage('development'))
        except BaseException as exc:
            write_new(ROOT/(stage+'_failure.json'),dict(error=repr(exc),completed=count))
            raise
        finally:
            engine.close()
    signal.alarm(0)
    ch=resource.getrusage(resource.RUSAGE_CHILDREN);su=resource.getrusage(resource.RUSAGE_SELF)
    write_new(ROOT/(stage+'_receipt.json'),dict(status='COMPLETE',bins=count,wall_seconds=time.perf_counter()-w0,
        wrapper_cpu_seconds=time.process_time()-cpu0,child_cpu_seconds=ch.ru_utime+ch.ru_stime,
        replay_cpu_seconds=time.process_time()-cpu0+ch.ru_utime+ch.ru_stime,
        wrapper_peak_rss=su.ru_maxrss,child_peak_rss=ch.ru_maxrss,rss_unit='bytes on macOS, KiB on Linux',
        raw_sha256=file_hash(out),parent_study_sha256=file_hash(PARENT/'study.py')))


if __name__=='__main__':
    main()
