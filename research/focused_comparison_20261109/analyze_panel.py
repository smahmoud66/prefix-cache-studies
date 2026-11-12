"""Aggregate complete frozen cells, preserving pairing of cohorts and repetitions."""
import gzip
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import statistics as st
import time
from run_panel import ROOT, METHODS, REPS, sha

METRICS=('history_cpu','native_cpu','caller_wall','generation_cpu','parse_cpu','update_cpu')


def dist(values):
    v=sorted(values)
    return dict(mean_us=st.mean(v)/1000, p95_us=v[math.ceil(.95*len(v))-1]/1000,
                p99_us=v[math.ceil(.99*len(v))-1]/1000, max_us=v[-1]/1000,
                summed_s=sum(v)/1e9)


def frames(item):
    p=ROOT/'timings'/item['raw']
    assert sha(p)==item['sha256']
    with gzip.open(p,'rt') as f:
        yield from (json.loads(line) for line in f)


def characterize(receipts):
    series={k:[] for k in METRICS}
    per=[]
    totals=None;maxima={}
    coordinates=[]
    observed_work=None
    for r in sorted(receipts,key=lambda x:x['rep']):
        start=len(series['native_cpu'])
        counts=defaultdict(int)
        work=0
        for row in frames(r):
            coordinates.append((r['rep'],row['bin'],row['i']))
            for metric,ns in zip(METRICS,(row['hist_ns'],row['parse_ns']+row['cpu_ns']+row['update_ns'],row['wall_ns'],
                                           row['common_gen_ns'],row['parse_ns'],row['update_ns'])):
                series[metric].append(ns)
            work+=row['positions']
            for k,v in row.items():
                if k in ('bin','i','positions','den','future_blocks','objective_num','immediate_blocks') or k.endswith('_ns'):continue
                if k.endswith(('_bytes','_entries')) or k in ('interned_nodes','rank_diff_bytes','memo_entries'):
                    maxima[k]=max(maxima.get(k,0),v)
                else:
                    counts[k]+=v
        if totals is None:
            totals=dict(counts)
        else:
            assert totals==counts,(r['raw'],'operation-count mismatch across repetitions')
        assert len(series['native_cpu'])-start==r['cohorts'] and work==r['prefill']
        if observed_work is None: observed_work=work
        assert observed_work==work
        per.append(dict(rep=r['rep'],child_cpu_all_s=r['child_cpu'],rss_peak_bytes=r['rss_bytes'],wrapper_cpu_all_s=r['wrapper_cpu'],
                        process_cell_wall_s=r['elapsed_s'],**{k+'_s':sum(v[start:])/1e9 for k,v in series.items()}))
    return (dict(cohorts_per_rep=len(coordinates)//3,prefill_per_rep=observed_work,per_rep=per,
                 timing={k:dist(v) for k,v in series.items()},counters_per_rep=totals,
                 max_components=maxima,peak_native_rss_bytes=max(r['rss_bytes'] for r in receipts)),
            coordinates,series)


def contrasts(methods,allseries):
    comparisons={}
    for base in ('FOCUSED','R01','R10','FULL'):
        contrasts={}
        for k in ('history_cpu','native_cpu','caller_wall'):
            bas=allseries[base][k]; opt=allseries['R11'][k]
            ds=[x-y for x,y in zip(bas,opt)]
            repeats=[]
            for i,j in zip(methods[base]['per_rep'],methods['R11']['per_rep']):
                x=i[k+'_s']; y=j[k+'_s']
                repeats.append(dict(rep=i['rep'],saved_s=x-y,ratio=x/y if y else None))
            contrasts[k]=dict(baseline_over_R11=sum(bas)/sum(opt) if sum(opt) else None,
                              paired_mean_saved_us=st.mean(ds)/1000,delta_mean_total_s=sum(ds)/3e9,
                              paired_repetitions=repeats)
        comparisons[base]=contrasts
    interact={}
    for metric in ('history_cpu','native_cpu','caller_wall'):
        t={m:allseries[m][metric] for m in METHODS}
        row=[a-b-c+d for a,b,c,d in zip(t['FULL'],t['R10'],t['R01'],t['R11'])]
        interact[metric]=dict(mean_us=st.mean(row)/1000,mean_total_s=sum(row)/3e9)
    return comparisons,interact


def summarize():
    started=time.process_time()
    assert json.loads((ROOT/'benchmark_receipt.json').read_text())['status']=='COMPLETE'
    receipts=[json.loads(line) for line in (ROOT/'timing_receipts.jsonl').read_text().splitlines()]
    assert len(receipts)==120 and len(set(r['raw'] for r in receipts))==120
    summaries={}
    for tr in ('conversation','toolagent'):
        for cap in (32,128):
            for absolute in (False,True):
                selected=[r for r in receipts if (r['trace'],r['cap'],r['absolute'])==(tr,cap,absolute)]
                methods={};allseries={};coords=None
                for m in METHODS:
                    rs=[r for r in selected if r['method']==m]
                    assert sorted(r['rep'] for r in rs)==list(REPS)
                    data,co,s=characterize(rs)
                    if coords is None: coords=co
                    assert co==coords
                    methods[m]=data;allseries[m]=s
                assert len({v['prefill_per_rep'] for v in methods.values()})==1
                comp,inter=contrasts(methods,allseries)
                key=f'{tr}_{cap}_'+('absolute' if absolute else 'decision')
                summaries[key]=dict(methods=methods,paired=comp,factorial_interaction=inter)
    summary=dict(cells=summaries,alias={'R00':'FULL'},
        definitions={'paired':'For the same cohort, traffic, capacity, interface and repetition: saved time = baseline minus R11. Ratios are sums of baseline divided by R11. No workload uncertainty is derived from repeated timings.',
                     'interaction':'T00 - T10 - T01 + T11, where T00=FULL. Positive values imply the sum of two standalone time savings overstates their joint saving.'},
        analysis_cpu_s=time.process_time()-started)
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    summarize()
