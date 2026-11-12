"""Independent readback of both primary kernels' integer counters and clocks."""
from pathlib import Path
import gzip
import json
import math
import time

root=Path(__file__).resolve().parent
clock=time.process_time()
summary=json.loads((root/'summary.json').read_text())
cells=[json.loads(line) for line in (root/'timing_receipts.jsonl').read_text().splitlines()]
assert len(cells)==120
checked=0
primary={}
for trace in ('conversation','toolagent'):
    for cap in (32,128):
        for absolute in (0,1):
            key=f"{trace}_{cap}_"+('absolute' if absolute else 'decision')
            ref=summary['cells'][key]
            detail={}
            for rep in (1,2,3):
                pair={}
                for mode in ['R11','FOCUSED']:
                    tag=f'{trace}_{cap}_{absolute}_{mode}_{rep}.jsonl.gz'
                    clock_totals=[0,0,0]
                    work=0; n=0
                    counters=[]
                    with gzip.open(root/'timings'/tag,'rt') as f:
                        for line in f:
                            r=json.loads(line)
                            n+=1
                            work+=r['positions']
                            clock_totals[0]+=r['hist_ns']
                            clock_totals[1]+=r['parse_ns']+r['cpu_ns']+r['update_ns']
                            clock_totals[2]+=r['wall_ns']
                            counters.append((r['bin'],r['i'],r['rollouts'],r['rollout_transitions'],
                                             r['form_scores'],r['cert_checks'],r['memo_hits'],
                                             r['memo_lookups'],r['common_elided']))
                    assert work==ref['methods'][mode]['prefill_per_rep']
                    assert n==ref['methods'][mode]['cohorts_per_rep']
                    pair[mode]=(clock_totals,counters)
                    checked+=n
                assert pair['R11'][1]==pair['FOCUSED'][1]
                ratios=[]
                for i,metric in enumerate(['history_cpu','native_cpu','caller_wall']):
                    a=pair['FOCUSED'][0][i]; b=pair['R11'][0][i]
                    tab=ref['paired']['FOCUSED'][metric]['paired_repetitions'][rep-1]
                    assert math.isclose(tab['saved_s'],(a-b)*1e-9,rel_tol=1e-12,abs_tol=1e-12)
                    assert math.isclose(tab['ratio'],a/b,rel_tol=1e-12)
                    ratios.append(a/b)
                detail[rep]=ratios
            primary[key]=detail
receipt=dict(status='PASS',primary_native_rows_read=checked,all_eligible_operational_counts_tested=['rollouts','rollout_transitions','form_scores','cert_checks','memo_hits','memo_lookups','common_elided'],
             ratios_by_rep_history_native_wall=primary,cpu_s=time.process_time()-clock)
(root/'primary_readback.json').write_text(json.dumps(receipt,indent=2)+'\n')
