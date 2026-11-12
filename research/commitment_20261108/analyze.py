"""Aggregate frozen replay outputs and independently account for the decisive order change."""
import hashlib
import json
import math
from pathlib import Path
import random
import statistics as st
import time
from collections import Counter
from scipy.stats import t

ROOT=Path(__file__).resolve().parent
load=lambda name:json.loads((ROOT/name).read_text())
start_cpu=time.process_time()
cfg=load('config.json')
rows=[json.loads(l) for l in (ROOT/'evaluation.jsonl').read_text().splitlines()]
dev=[json.loads(l) for l in (ROOT/'development.jsonl').read_text().splitlines()]
for stage in ['development','evaluation']:
    receipt=load(stage+'_receipt.json')
    for key,name in [('raw_sha256',stage+'.jsonl'),('script_sha256','study.py'),('config_sha256','config.json')]:
        assert receipt[key]==hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
for trace in cfg['paths']:
    sample=random.Random(cfg['split']['seeds'][trace]).sample(range(48),20)
    assert sorted(d['bin'] for d in dev if d['workload']==trace)==sorted(sample[:4])
    assert sorted(d['bin'] for d in rows if d['workload']==trace)==sorted(sample[4:])
assert len(rows)==32
for d in rows:
    assert sum(int(k)*v for k,v in d['cohort_sizes'].items())==d['requests']
    assert all(0<=v<=1000 for v in d['intentional_wait_ms'])
    for c in ['128','32']:
        ref=d['capacities'][c]['runs']['FCFS']['dispatch_lines']
        for p,r in d['capacities'][c]['runs'].items():
            assert list(map(sorted,r['dispatch_lines']))==list(map(sorted,ref))
            assert r['max_displacement']<=3

def interval(groups):
    means=[st.mean(v) for v in groups]
    vv=[.25*(1-len(v)/44)*st.variance(v)/len(v) for v in groups]
    center=st.mean(means); se=math.sqrt(sum(vv))
    if se==0:
        return dict(mean=center,means=means,se=0,ci95=None,reason='zero sampled variance')
    df=sum(vv)**2/sum(var**2/(len(v)-1) for var,v in zip(vv,groups))
    half=float(t.ppf(.975,df))*se
    return dict(mean=center,means=means,se=se,df=df,ci95=[center-half,center+half])

summary={}
for cap in ['128','32']:
    ss={}
    for pol in ('FCFS','kLPM','cLPM','portfolio','search','search_LRU'):
        groups=[[],[]];levels=[[],[]];ops=Counter();cost=cpu=total=0
        for d in rows:
            group=int(d['workload']=='toolagent')
            runs=d['capacities'][cap]['runs']
            r=runs[pol]
            n=max(1,d['requests'])
            groups[group].append((runs['portfolio']['prefill']-r['prefill'])/n)
            levels[group].append(r['prefill']/n)
            cost+=r['prefill'];cpu+=r['cpu_ns'];total+=d['tokens'];ops.update(r['ops'])
        ss[pol]=dict(equal_weight_prefill=st.mean(map(st.mean,levels)),by_trace=list(map(st.mean,levels)),
            paired_savings=interval(groups),total_prefill=cost,token_hit_fraction=1-cost/total,
            cpu_seconds=cpu/1e9,ops=dict(ops),paired_bin_savings=groups)
    for key in ('cut_lb','unique_lb','always_tokens'):
        ss[key]=st.mean(d['capacities'][cap][key]/max(1,d['requests']) for d in rows)
    ss['per_trace_ceiling']=[st.mean((d['capacities'][cap]['runs']['portfolio']['prefill']-d['capacities'][cap]['cut_lb'])/d['requests'] for d in rows if d['workload']==tr) for tr in cfg['paths']]
    summary[cap]=ss

def verify_orders(d):
    """Simple tuple-prefix replay of the saved orders; no optimization or new treatment."""
    cap=128
    raw=[json.loads(l) for l in (ROOT/'inputs'/(d['workload']+'.jsonl')).read_text().splitlines()]
    selected=sorted((x['timestamp'],i,x) for i,x in enumerate(raw) if d['start_ms']<=x['timestamp']<d['end_ms'])
    path={};rank={};warm=[]
    for ts,i,x in selected:
        ids=x['hash_ids'][:max(0,(x['input_length']-1)//512)]
        full=[tuple(ids[:j+1]) for j in range(len(ids))]
        for node in full:rank.setdefault(node,len(rank)+1)
        path[i]=full[:cap]
        if 4*(ts-d['start_ms'])<d['end_ms']-d['start_ms']:warm.append(i)

    def advance(cache,i,remaining,clock):
        pre=path[i]
        h=0
        for node in pre:
            if node not in cache:break
            h+=1
        cache.update(dict.fromkeys(pre,clock))
        count=Counter(node for j in remaining for node in path[j])
        protected=set(pre)
        while len(cache)>cap:
            parents={node[:-1] for node in cache}
            leaves=cache.keys()-parents-protected
            def key(node):
                priority=max((k*count[node[:k]] for k in range(1,len(node)+1)),default=0)
                return priority,cache[node],-len(node),rank[node]
            del cache[min(leaves,key=key)]
        return raw[i]['input_length']-512*h

    initial={};clock=0
    for i in warm:
        clock+=1;advance(initial,i,[],clock)
    per={}
    for policy in ('portfolio','search'):
        cache=initial.copy();tick=clock;counts=[]
        for order in d['capacities']['128']['runs'][policy]['dispatch_lines']:
            total=0
            for j,i in enumerate(order):
                tick+=1
                total+=advance(cache,i,order[j+1:],tick)
            counts.append(total)
        assert sum(counts)==d['capacities']['128']['runs'][policy]['prefill']
        per[policy]=counts
    return [{'cohort_index':j,'portfolio_minus_search_tokens':a-b}
        for j,(a,b) in enumerate(zip(per['portfolio'],per['search'])) if a!=b]

changes=[]
for d in rows:
    runs=d['capacities']['128']['runs']
    if runs['search']['dispatch_lines']!=runs['portfolio']['dispatch_lines']:
        changes.append(dict(trace=d['workload'],bin=d['bin'],deltas=verify_orders(d)))
waits=sorted(x for d in rows for x in d['intentional_wait_ms'])
sizes=Counter()
for d in rows:sizes.update(d['cohort_sizes'])
out=dict(capacities=summary,changed_primary_episodes=changes,cohort_sizes=dict(sizes),
    requests=sum(d['requests'] for d in rows),input_tokens=sum(d['tokens'] for d in rows),
    warm_requests=sum(d['warm_requests'] for d in rows),warm_prefill={c:sum(d['capacities'][c]['warm_prefill'] for d in rows) for c in ['128','32']},
    hold_ms=dict(mean=st.mean(waits),p95=waits[math.ceil(.95*len(waits))-1],maximum=max(waits)),
    max_transient_input_tokens=max(d['max_transient_input_tokens'] for d in rows),
    per_trace_requests={tr:sum(d['requests'] for d in rows if d['workload']==tr) for tr in cfg['paths']},
    analysis_cpu_seconds_after_imports=time.process_time()-start_cpu)
(ROOT/'summary.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='capacities'},indent=2))
print('Primary',summary['128']['search']['paired_savings'])
