"""Summarize the fixed finite-frame census. No policy selection or resampling."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

ROOT=Path(__file__).resolve().parent
MODES=('FCFS','kLPM','search_LRU','portfolio','H2','H1','TIE')
CAPS=('128','32')
TRACE=('conversation','toolagent')
start=time.process_time()


def read(name):
    return json.loads((ROOT/name).read_text())


def rows(stage):
    path=ROOT/(stage+'.jsonl')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==read(stage+'_receipt.json')['raw_sha256']
    return [json.loads(line) for line in path.read_text().splitlines()]


def describe(values):
    x=sorted(values)
    return {'mean':statistics.mean(x),'median':statistics.median(x),'min':x[0],
            'p95':x[math.ceil(len(x)*.95)-1],'p99':x[math.ceil(len(x)*.99)-1],'max':x[-1]}


def signs(values):
    return {'positive':sum(v>0 for v in values),'zero':sum(v==0 for v in values),
            'negative':sum(v<0 for v in values)}


data=rows('online')
future=rows('hindsight')
split=read('split.json')
assert [(d['workload'],d['bin']) for d in data]==[(d['workload'],d['bin']) for d in future]
for tr in TRACE:
    assert sorted(d['bin'] for d in data if d['workload']==tr)==split['traces'][tr]['new_eval']
assert len(data)==len(future)==56
report={'frame':'fixed previously unused project-outcome bins','bins':56,'traces':{},'capacities':{},'paired_per_bin':[]}
for tr in TRACE:
    subset=[d for d in data if d['workload']==tr]
    report['traces'][tr]={k:sum(d[k] for d in subset) for k in ('n','warm_n','input_tokens')}
    report['traces'][tr]['cohorts']=sum(len(d['groups']) for d in subset)
report['gating_wait_ms']=describe([w for d in data for w in d['wait_ms']])
report['max_active_input_plus_warmup_tokens']=max(d['max_transient'] for d in data)
for c in CAPS:
    modes={}; contrasts={}; mechanism={}; summed={}
    for mode in MODES:
        levels={};changes=[];cohorts=[];work=0
        for tr in TRACE:
            levels[tr]=[]
            for d in data:
                if d['workload']!=tr:continue
                group=d['capacities'][c]['runs'][mode]
                assert group['prefill']==sum(v['prefill'] for v in group['cohorts'])
                assert len(d['groups'])==len(group['cohorts'])
                for ids,rec in zip(d['groups'],group['cohorts']):
                    assert sorted(rec['order'])==list(range(len(ids)))
                    assert 0<=rec['max_displacement']<=3
                work+=group['prefill'];cohorts.extend(group['cohorts'])
                levels[tr].append(group['prefill']/max(1,d['n']))
        times=[(x['wrapper_cpu_ns']+x.get('cpu_ns',0))/1e6 for x in cohorts]
        keys=('parent_transitions','current_transitions','rollout_transitions','rollouts','legal','distinct_full','distinct_sets')
        modes[mode]=dict(equal_mean=statistics.mean(statistics.mean(v) for v in levels.values()),
            by_trace={k:statistics.mean(v) for k,v in levels.items()},positions_total=work,
            timing_cpu_ms=describe(times),timing_wall_ms=describe([x['wall_ns']/1e6 for x in cohorts]),
            cpu_total_sec=sum(times)/1e3,rollout_cpu_sec=sum(x.get('rollout_cpu_ns',0) for x in cohorts)/1e9,
            max_displacement=max(x['max_displacement'] for x in cohorts),counters={k:sum(x.get(k,0) for x in cohorts) for k in keys})
        if mode in ('H2','H1','TIE'):
            changed=[x for x in cohorts if x['order']!=x['incumbent']]
            assert all(x['excess_blocks']>=0 and x['adv_num_blocks']>=0 and x['den']>=1 for x in cohorts)
            assert all(x['adv_num_blocks']>0 for x in changed)
            mechanism[mode]=dict(cohorts=len(cohorts),multiple_orders=sum(x['legal']>1 for x in cohorts),
               multiple_full_exits=sum(x['distinct_full']>1 for x in cohorts),
               recency_only_offered=sum(x['distinct_full']>1 and x['distinct_sets']==1 for x in cohorts),
               different_sets_offered=sum(x['distinct_sets']>1 for x in cohorts),
               at_least_one_recency_pair=sum(x['distinct_full']>x['distinct_sets'] for x in cohorts),
               changed=len(changed),recency_only_chosen=sum(x['same_residents_as_incumbent'] for x in changed),
               residency_changed=sum(not x['same_residents_as_incumbent'] for x in changed),
               strict_sacrifice=sum(x['excess_blocks']>0 for x in cohorts),
               sacrifice_positions=512*sum(x['excess_blocks'] for x in cohorts),
               predicted_adv_positions_mean_changed=statistics.mean([512*x['adv_num_blocks']/x['den'] for x in changed]) if changed else None)
    for mode in MODES:
        diffs=[]
        for d in data:
            runs=d['capacities'][c]['runs']
            delta=runs[mode]['prefill']-runs['H2']['prefill']
            diffs.append(dict(trace=d['workload'],bin=d['bin'],positions=delta,per_request=delta/max(1,d['n'])))
        v=[x['per_request'] for x in diffs]
        contrasts[mode]=dict(census=statistics.mean(v),by_trace={tr:statistics.mean(x['per_request'] for x in diffs if x['trace']==tr) for tr in TRACE},
            by_trace_signs={tr:signs([x['per_request'] for x in diffs if x['trace']==tr]) for tr in TRACE},
            signs=signs(v),distribution=describe(v),positions_sum=sum(x['positions'] for x in diffs),
            request_pooled=sum(x['positions'] for x in diffs)/sum(d['n'] for d in data))
        if mode=='search_LRU':
            report['paired_per_bin'].extend(dict(cap=c,**x) for x in diffs)
    diags=[v for d in future for v in d['capacities'][c]['diagnostics']]
    for changed in (True,False):
        records=[v for v in diags if v['changed']==changed]
        complete=[v for v in records if v['status']=='complete']
        gains=[v['incumbent_blocks']-v['selected_blocks'] for v in complete]
        summed['changed' if changed else 'unchanged_sample']=dict(requested=len(records),complete=len(complete),
            end_truncated=len(records)-len(complete),actual_short_horizon_signs=signs(gains),
            selected_optimal=sum(x['selected_optimal'] for x in complete),
            incumbent_optimal=sum(x['incumbent_blocks']==x['best_blocks'] for x in complete),
            strictly_available_opportunity=sum(x['incumbent_blocks']>x['best_blocks'] for x in complete),
            mean_regret_positions_against_best=statistics.mean(512*(x['selected_blocks']-x['best_blocks']) for x in complete) if complete else None)
    assert summed['changed']['requested']==mechanism['H2']['changed']
    report['capacities'][c]=dict(modes=modes,contrasts_baseline_minus_H2=contrasts,mechanism=mechanism,
        hindsight=summed,mean_cut_lower_bound=statistics.mean(x['capacities'][c]['offline_bound']['cut_lb']/max(1,d['n']) for x,d in zip(future,data)),
        warm_prefill_each_policy=sum(d['capacities'][c]['warm_prefill'] for d in data))
report['analysis_cpu_sec_after_imports']=time.process_time()-start
(ROOT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
