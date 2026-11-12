"""Post-run descriptive checks. Does not open or run the simulator."""
from decide import *
from statistics import median
from collections import Counter
import math
def details():
    dev=read(R/'development_cells.json'); test=read(R/'heldout_cells.json'); model=read(R/'fitted.json')
    print('model',model)
    print('decision',read(R/'decision.json'))
    for s in (*DEV,TEST):
        cells=[z for z in (test if s==TEST else dev) if z['trace']==s]
        for W in (500,2000):
            a=[z for z in cells if z['W']==W]; fields=['g1','g2_order','g2_mixed','g3']; print(s,W, 'mats',sum(z['material'] for z in a),sum(z['literal_material'] for z in a),
             'ranges', [(k, round(min(z[k] for z in a),4),round(max(z[k] for z in a),4)) for k in fields], 'max p99 ratio order',round(max(z['online_p99_ms']/z['fcfs_p99_ms'] for z in a),3))
    a=[z for z in test if z['W']==500]; raw={(*key(z),z['W']):z['policies'] for z in scorefile(TEST)}
    print('joint choices',Counter(z['joint_ref'] for z in a))
    print('online choices',Counter(z['online'] for z in a))
    for k in ('g1','g2_order','g2_mixed','g3'):
        z=max(a,key=lambda z:z[k]);print('peak',k,{x:z[x] for x in ['rho','u','d',k,'g1_tokens','g2_order_tokens','g2_mixed_tokens','g3_tokens','fcfs_p99_ms','online_p99_ms','order_ref_p99_ms','joint_ref_p99_ms','online','order_ref','joint_ref']})
    print('counts',[(m,sum(z[m]>=3 for z in a)) for m in ('g1','g2_order','g2_mixed','g3')])
    print('capacities',[(z['rho'],z['features']['capacity_blocks'], round(z['features']['realized_rho'],4)) for z in a if z['d']==4 and z['u']==.6])
    for d in [4,16,64]:
        b=[z for z in a if z['d']==d];print('queue',d, min(z['features']['mean_ready'] for z in b),max(z['features']['mean_ready'] for z in b), min(z['features']['max_ready'] for z in b),max(z['features']['max_ready'] for z in b),min(z['features']['cap_reached_fraction'] for z in b),max(z['features']['cap_reached_fraction'] for z in b))
    pool=[raw[(*key(z),500)][m] for z in a for m in ['LPM',f"K{model['k']}",'DFS']]
    print('proposals',sum(p['proposed_groups'] for p in pool),sum(p['vetoed_groups'] for p in pool),sum(p['reordered_groups'] for p in pool));print('largest nonoracle lag',max(raw[(*key(z),500)][m]['max_lag_ms'] for z in a for m in ['FCFS','LPM',f"K{model['k']}",'DFS','LOOK']))
    print('timing range',min(z['fcfs_p99_ms'] for z in a),max(z['fcfs_p99_ms'] for z in a))
    for lab in ('material','literal_material'):
        print('class',lab, [('rho',cr,sum(z[lab] for z in a if z['rho']==cr)) for cr in (.1,.25,.5,1.)])
    p=R/'panels/freeinference.txt'
    with p.open() as f: nn,nw=map(int,next(f).split());rows=[[int(v) for v in line.split()[:4]] for line in f]
    lm=[v[1] for v in rows[nw:]];print('lengths',len(lm),max(lm),sum(v>16384 for v in lm),sum(v>40960 for v in lm),sum(v>65536 for v in lm), 'span secs', (rows[-1][0]-rows[nw][0])/1e6)
if __name__=='__main__':details()
