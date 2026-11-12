"""Draw the ordering manuscript figure from the recorded 36 primary cells."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);args=p.parse_args()
root=Path(__file__).resolve().parents[1]
cells=[r for r in json.loads((root/'research/prefix_order_pilot_20261112/heldout_cells.json').read_text()) if r['W']==500]
assert len(cells)==36
plt.rcParams.update({'font.size':8.5,'font.family':'DejaVu Sans','pdf.fonttype':42,'axes.spines.right':False,'axes.spines.top':False})
fig,ax=plt.subplots(1,2,figsize=(6.55,2.76),sharex=True)
colors=['#06645d','#af4b28']; caps=[.1,.25,.5,1.0]
series=[[('g1','Existing order'),('g2_order','Extra, LRU unchanged')],[('g2_mixed','Extra, order + eviction'),('g3','Residual to infinite cache')]]
for i, (a, ss) in enumerate(zip(ax,series)):
    for j,(k,label) in enumerate(ss):
        offset=(-.065,.065)[j]
        for x,c in enumerate(caps):
            y=[z[k] for z in cells if z['rho']==c];assert len(y)==9
            a.plot([x+offset]*2,[min(y),max(y)],lw=1.2,c=colors[j],zorder=2)
            a.scatter([x+offset]*len(y),y,s=15,facecolors='none',edgecolors=colors[j],linewidths=.7,zorder=3)
    a.set_title(['A   LRU order comparisons','B   Comparisons allowing eviction'][i],loc='left',fontsize=9.8,fontweight='bold')
    a.set_xticks(range(4),['0.10','0.25','0.50','1.00']);a.set_xlim(-.36,3.36);a.set_xlabel('Capacity / warm-up working set',fontsize=8.4)
    a.grid(axis='y',color='#d9dde0',lw=.55);a.tick_params(length=2.5)
    a.set_ylim((-.14,3.65) if i==0 else (-.46,10.9));a.set_yticks([0,1,2,3] if i==0 else [0,2,4,6,8,10])
    a.axhline(3,ls=(0,(3,3)),c='#53565a',lw=.75)
    handles=[Line2D([],[],linestyle='none',marker='o',markersize=4.0,markerfacecolor='none',markeredgecolor=col,label=lab) for col,(_,lab) in zip(colors,ss)]
    a.legend(handles=handles,loc='upper right',bbox_to_anchor=(1.03,1.00 if i==1 else .95),fontsize=7.1,handletextpad=.22,framealpha=.94,edgecolor='none',labelspacing=.3)
ax[0].set_ylabel('Share of FCFS prefill work (%)')
fig.subplots_adjust(left=.095,right=.985,top=.88,bottom=.19,wspace=.32)
fig.savefig(args.output,metadata={'Creator':'Matplotlib','CreationDate':None,'ModDate':None})
