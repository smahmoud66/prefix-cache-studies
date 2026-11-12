"""Summarize the matched benchmark. Every timing repetition stays identifiable."""
import gzip
import json
import math
from pathlib import Path
import statistics as st
import time

root=Path(__file__).resolve().parent
start=time.process_time()
receipt=json.loads((root/'benchmark_receipt.json').read_text())
assert receipt['status']=='COMPLETE'
with gzip.open(root/'timings.jsonl.gz','rt') as f:
    records=[json.loads(l) for l in f]
def dist(ns):
    values=sorted(ns)
    return dict(total_sec=sum(values)/1e9,mean_us=st.mean(values)/1000,
                p95_us=values[math.ceil(.95*len(values))-1]/1000,
                p99_us=values[math.ceil(.99*len(values))-1]/1000,
                max_us=values[-1]/1000)

def subset(data,trace,cap,mode):
    return [x for x in data if x['mode']==mode and x['cap']==cap and (trace=='both' or x['trace']==trace)]

def stats(rows,cells):
    keys=('current_transitions','rollout_transitions','rollouts','candidate_states','eligible_orders',
          'visited_actions','common_pairs','form_scores','memo_hits','current_nodes','current_cache_hits')
    native=lambda r:r['parse_ns']+r['cpu_ns']+r['update_ns']
    nrep=len({r['rep'] for r in rows})
    assert nrep==3
    counters={}
    for k in keys:
        if k not in rows[0]:continue
        counts=[sum(x[k] for x in rows if x['rep']==j) for j in (1,2,3)]
        assert counts[0]==counts[1]==counts[2],(k,counts)
        counters[k]=counts[0]
    per=[]
    for j in (1,2,3):
        a=[r for r in rows if r['rep']==j]; cs=[r for r in cells if r['rep']==j]
        per.append(dict(rep=j,cohorts=len(a),prefill=sum(r['work'] for r in a),kernel_cpu_s=sum(r['cpu_ns'] for r in a)/1e9,
                        native_measured_cpu_s=sum(native(r) for r in a)/1e9,
                        wrapper_decision_cpu_s=sum(r['wrapper_cpu_ns'] for r in a)/1e9,
                        decision_wall_s=sum(r['wall_ns'] for r in a)/1e9,
                        child_all_s=sum(c['cpu_child_all'] for c in cs),wrapper_all_s=sum(c['cpu_wrapper_all'] for c in cs),
                        whole_cells_wall_s=sum(c['wall_all'] for c in cs)))
    assert len({r['prefill'] for r in per})==1
    return dict(cohorts_each=len(rows)//nrep,prefill_each=per[0]['prefill'],reps=per,kernel=dist([r['cpu_ns'] for r in rows]),
      native_including_parse_and_update=dist([native(r) for r in rows]),wall=dist([r['wall_ns'] for r in rows]),
      wrapper_cpu=dist([r['wrapper_cpu_ns'] for r in rows]),parse=dist([r['parse_ns'] for r in rows]),
      update=dist([r['update_ns'] for r in rows]),counters_one_rep=counters,
      maxima={k:max(r[k] for r in rows) for k in ('memo_bytes','memo_entries','history_bytes','index_bytes','interned_nodes','current_cache_bytes','current_cache_entries','rank_diff_bytes') if k in rows[0]},
      child_rss_max_bytes=max(c['child_peak_rss_bytes'] for c in cells))

summary={}
for cap in (128,32):
    for trace in ('conversation','toolagent','both'):
        methods={}
        for m in ('K','IMM','REF','OPT'):
            methods[m]=stats(subset(records,trace,cap,m),subset(receipt['cells'],trace,cap,m))
        summary[f'{trace}_{cap}']=methods
p=root/'benchmark_summary.json'
p.write_text(json.dumps(dict(methods=summary,analysis_cpu_seconds=time.process_time()-start),indent=2)+'\n')
for label,methods in summary.items():
    print(label,'kernel/native/e2e mean microseconds k,imm,ref,opt:')
    print([(round(r['kernel']['mean_us'],2),round(r['native_including_parse_and_update']['mean_us'],2),round(r['wall']['mean_us'],2)) for r in methods.values()])
