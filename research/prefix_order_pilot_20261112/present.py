"""Human-readable grid/figure from recorded results only. No trace replay or refitting."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
from decide import R, read, lines
def main():
    data=read(R/'heldout_cells.json');raw={ (r['rho'],r['u'],r['d'],r['W']):r['policies'] for r in lines(R/'raw/freeinference.scores.jsonl')}
    with (R/'heldout_grid.md').open('w') as f:
        f.write('# Independent FreeInference grid\n\nAll gaps are % of FCFS modeled prefill service work. G2 order holds LRU fixed; G2 joint also permits clairvoyant eviction. G3 is remaining work above infinite cache on the *same winning order*. Flags and decisions in the table refer to the ordering-only rule. Every FCFS benchmark here has its own matched utilization and capacity. [All cell values, including token-based gaps](heldout_cells.json) · [All policies including median/p99, starts that violate W, and maximum queue depth](raw/freeinference.scores.jsonl)\n')
        for W in (500,2000):
            f.write(f'\n## Waiting allowance {W:,} ms'+(' (primary)' if W==500 else ' (sensitivity; no tuning)')+'\n\n| Utilization | Cap | Target ρ | Cache blocks | Mean / max ready¹ | G1 | G2 order | G2 joint | G3 | FCFS / best online p99, ms | Flag / material |\n|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---|\n')
            for v in sorted((c for c in data if c['W']==W),key=lambda c:(c['u'],c['d'],c['rho'])):
                fs=v['features']
                f.write(f"| {v['u']:.2f} | {v['d']} | {v['rho']:.2f} | {fs['capacity_blocks']:,} | {fs['mean_ready']:.1f} / {fs['max_ready']} | {v['g1']:.2f} | {v['g2_order']:.2f} | {v['g2_mixed']:.2f} | {v['g3']:.2f} | {v['fcfs_p99_ms']:.0f} / {v['online_p99_ms']:.0f} | {int(v['flags']['material'])} / {int(v['material'])} |\n")
        f.write('\n¹ FCFS shadow at dispatch. Actual maximum ready/backlog for each policy is in the raw results. Flags are frozen on the primary window; reusing them at 2 s is descriptive. Materiality requires the achieving policy to pass the p99 and waiting checks.\n')
    primary=[x for x in data if x['W']==500]; cs=[.1,.25,.5,1.];pairs=[(u,d) for u in [.6,.8,.95] for d in [4,16,64]]
    vl={ (x['rho'],x['u'],x['d']):x for x in primary};metrics=[('g1','A   Existing order over FCFS'),('g2_order','B   Extra saving with order alone'),('g2_mixed','C   Extra saving with order + eviction'),('g3','D   Residual to infinite cache on that order')]
    fig,axes=plt.subplots(2,2,figsize=(14.5,6.8),constrained_layout=True)
    vmax=max([3]+[vl[cr,u,d][k] for cr in cs for u,d in pairs for k,_ in metrics])
    for ax,(k,title) in zip(axes.flat,metrics):
        vals=np.array([[vl[cr,u,d][k] for u,d in pairs] for cr in cs]);im=ax.imshow(vals,cmap='Blues',norm=Normalize(0,vmax),aspect='auto')
        ax.set_xticks(range(9),[f'{d}\n{u:.2f}' for u,d in pairs]);ax.set_yticks(range(4),[str(c) for c in cs]);ax.set_ylabel('Capacity / working set')
        ax.set_xlabel('Ready cap (top) · offered utilization (bottom)');ax.set_title(title,loc='left',fontsize=11,weight='bold')
        for i in (2.5,5.5):ax.axvline(i,color='gray',lw=1)
        for i,c in enumerate(cs):
            for j,(u,d) in enumerate(pairs):
                v=vl[c,u,d];ax.text(j,i,f'{v[k]:.1f}',ha='center',va='center',size=8,color='white' if v[k]>vmax*.6 else '#102030')
    fig.suptitle('FreeInference: where prefill work went under a 500 ms waiting allowance',fontsize=16)
    fig.colorbar(im,ax=axes.ravel().tolist(),shrink=.78,label='% of FCFS modeled prefill work (common scale)')
    fig.savefig(R/'heldout_gaps.png',dpi=155);plt.close(fig)
if __name__=='__main__':main()
