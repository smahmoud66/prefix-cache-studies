"""Summarize two deterministic timing repetitions; reporting windows never reset a trajectory."""
import csv
import hashlib
import json
import math
import re
import statistics as st
import time
from collections import Counter
from pathlib import Path
from replay_panel import ROOT, SCHEDULE, METHODS, SEEDS, sha


def dist(values):
    data=sorted(values)
    return dict(mean=st.mean(data),p95=data[math.ceil(.95*len(data))-1],
                p99=data[math.ceil(.99*len(data))-1],max=data[-1])


def readcell(rec,gate):
    tag=rec['tag']
    path=ROOT/'runs'/f'{tag}.tsv'
    assert rec['code']==0 and sha(path)==rec['output_sha256']
    with path.open() as f: rows=list(csv.DictReader(f,delimiter='\t'))
    if rec['method']=='CHECK':
        assert len(rows)==sum(r['phase']=='W' for r in gate)+16
        gate=gate[:len(rows)]
    assert len(rows)==len(gate)
    cpu,wall,orders=[],[],[]
    work=[0]*4
    sumvars=Counter()
    kinds=Counter()
    maxima=Counter()
    digest=hashlib.sha256()
    wat=0
    slots_after_warm=0
    eligible_hist=Counter()
    for row,g in zip(rows,gate):
        assert row['stage']==g['phase']
        n=int(row['n'])
        order=row['order']
        assert n==len(g['arrivals_ms']) and sorted(order)==list('0123'[:n])
        cost=int(row['work'])
        assert n<=cost<=g['tokens']
        digest.update((' '.join(v for k,v in row.items() if not k.endswith('_ns'))+'\n').encode())
        if row['stage']=='W':
            wat+=cost
            slots_after_warm=int(row['index_slots'])
            continue
        assert len(orders)==int(row['i'])
        orders.append(order)
        win=(g['first_row']-1001)//5000
        work[win]+=cost
        cpu.append(int(row['cpu_ns']))
        wall.append(int(row['wall_ns']))
        assert 0<=win<4
        exits=int(row['exits'])
        eligible=int(row['eligible'])
        if exits>=0:
            assert 1<=exits<=eligible<=math.factorial(n)
            eligible_hist[exits]+=1
            sumvars['multiple_orders']+=eligible>1
            sumvars['multiple_exits']+=exits>1
            sumvars['exit_count']+=exits
            sumvars['eligible_orders_total']+=eligible
            kinds[row['change_type']]+=1
        for k in ['changed','rollouts','direct','memo_hits','common']:
            sumvars[k]+=int(row[k])
        for k in ['memo_bytes','index_bytes','history_bytes','index_slots','ids']:
            maxima[k]=max(maxima[k],int(row[k]))
        maxima['displacement']=max(maxima['displacement'],max(abs(i-int(j)) for i,j in enumerate(order)))
        sumvars['sum_abs_displacement']+=sum(abs(i-int(j)) for i,j in enumerate(order))
    log=(ROOT/'runs'/f'{tag}.log').read_text()
    m=re.search(r'completed_measured_cohorts=(\d+) final_active_history_identities=(\d+)', log)
    assert m and int(m.group(1))==len(orders)
    return dict(warm_prefill=wat,work=sum(work),by_window=work,cohorts=len(orders),
                counters=dict(sumvars),exit_hist=dict(eligible_hist),change_type=kinds,peaks=maxima,
                ids_after_warm=slots_after_warm,active_final=int(m.group(2)),fingerprint=digest.hexdigest()),cpu,wall,orders


def analyze():
    start=time.process_time()
    assert (ROOT/'replay_receipt.json').is_file()
    recs=[json.loads(r) for r in (ROOT/'run_receipts.jsonl').read_text().splitlines()]
    assert len(recs)==136 and len(set(x['tag'] for x in recs))==136
    gates={w:json.loads((ROOT/'panel'/f'{w}_gate.json').read_text()) for w in 'AB'}
    meta={}
    for w,gate in gates.items():
        measured=[g for g in gate if g['phase']=='G']
        wait=[x for g in measured for x in g['wait_ms']]
        assert len(wait)==20000 and 0<=min(wait)<=max(wait)<=1000
        meta[w]=dict(requests=len(wait),cohorts=len(measured),input_tokens=sum(g['tokens'] for g in measured),
                     collection_ms=dist(wait),windows=[sum(len(g['wait_ms']) for g in measured if (g['first_row']-1001)//5000==i) for i in range(4)])
    for r in recs:
        if r['method']=='CHECK':
            readcell(r,gates[r['w']])
    cells={}
    comps={}
    for w in 'AB':
        for block,cap in SCHEDULE:
            key=f'{w}_{block}_{cap}'
            table={}
            orders={}
            for meth,seed in METHODS:
                reps=[r for r in recs if (r['w'],r['block'],r['cap'],r['method'],r['seed'])==(w,block,cap,meth,seed)]
                assert len(reps)==2
                name=meth if meth!='RAND' else f'RAND{seed}'
                cpus=[];walls=[];tim=[]
                for i,rec in enumerate(reps):
                    v,c,t,o=readcell(rec,gates[w])
                    if i==0: first=v; orders[name]=o
                    else: assert v==first and o==orders[name]
                    cpus+=c;walls+=t
                    tim.append(dict(measured_cpu_ns=sum(c),measured_wall_ns=sum(t),process_cpu_s=rec['cpu_s'],process_wall_s=rec['wall_s'],rss=rec['peak_rss_bytes']))
                assert v['cohorts']==meta[w]['cohorts']
                if w=='B': assert v['work']==meta[w]['input_tokens']
                table[name]=dict(**v,timing=tim,cpu_ns=dist(cpus),wall_ns=dist(walls))
            assert len(set(v['warm_prefill'] for v in table.values()))==1
            cells[key]=table
            opt=table['OPT']
            result={}
            for name,base in table.items():
                savings=base['work']-opt['work']
                extra_ns=st.mean(t['measured_wall_ns'] for t in opt['timing'])-st.mean(t['measured_wall_ns'] for t in base['timing'])
                result[name]=dict(savings=savings,savings_per_request=savings/20000,
                                  fraction=savings/base['work'],window_savings=[x-y for x,y in zip(base['by_window'],opt['by_window'])],
                                  extra_decision_wall_ns=extra_ns,
                                  break_even_ns_per_position=extra_ns/savings if savings>0 else None,
                                  different_trajectory_orders=sum(a!=b for a,b in zip(orders['OPT'],orders[name])))
            comps[key]=result
    summary=dict(episodes=meta,cells=cells,comparisons=comps,analysis_cpu_s=time.process_time()-start)
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    analyze()
