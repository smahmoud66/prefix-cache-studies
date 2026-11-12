"""Frozen selection, learning, evaluation; every gap uses the same FCFS denominator."""
import json, math
from pathlib import Path
R=Path(__file__).resolve().parent
DEV=('conversation','toolagent','qwenchat','qwenapi')
PRIMARY=DEV[:2]; TEST='freeinference'
FEATS=('queue_sharing','rho','reuse_over_capacity','mean_ready')
def read(p):return json.loads(Path(p).read_text())
def lines(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def save(path,obj):
    with Path(path).open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
def key(x):return (x['rho'],x['u'],x['d'])
def features(s):
    z=lines(R/'raw'/f'{s}.features.jsonl');assert len(z)==len({key(x) for x in z})==36
    return {key(x):dict(x['features'],rho=x['rho']) for x in z}
def scorefile(s):
    z=lines(R/'raw'/f'{s}.scores.jsonl');assert len(z)==len({(*key(x),x['W']) for x in z})==72;return z
def best(p,names):return min((name for name in names if p[name]['violations']==0),key=lambda name:p[name]['work_ms'])
def summarize(s,k):
    cells=[];f=features(s)
    for x in scorefile(s):
        p=x['policies'];names=['FCFS','LPM',f'K{k}','DFS'];assert all(p[a]['violations']==0 for a in names+['LOOK'])
        e=best(p,names);o=best(p,[e,'LOOK'])
        # The offline envelope may retain LRU. Never claim positive savings from an infeasible trajectory.
        joint=best(p,[o]+['MIN_'+n for n in names+['LOOK']])
        inf='INF_'+joint.removeprefix('MIN_')
        F=p['FCFS']['work_ms']; T=p['FCFS']['tokens']; tail=p['FCFS']['p99_ttft_ms']
        def g(a,b):return 100*(p[a]['work_ms']-p[b]['work_ms'])/F
        def gt(a,b):return 100*(p[a]['tokens']-p[b]['tokens'])/T
        g1,g2l,g2,g3=g('FCFS',e),g(e,o),g(e,joint),g(joint,inf)
        def ok(gap,pol):return gap>=3 and p[pol]['p99_ttft_ms']<=1.10*tail and p[pol]['violations']==0
        v={a:b for a,b in x.items() if a!='policies'}
        v.update(trace=s,online=e,order_ref=o,joint_ref=joint,matching_inf=inf,g1=g1,g2_order=g2l,g2_mixed=g2,eviction_increment=g(o,joint),g3=g3,
          g1_tokens=gt('FCFS',e),g2_order_tokens=gt(e,o),g2_mixed_tokens=gt(e,joint),g3_tokens=gt(joint,inf),
          material=ok(g1,e) or ok(g2l,o),literal_material=ok(g1,e) or ok(g2,joint),
          g1_qualifies=ok(g1,e),g2_order_qualifies=ok(g2l,o),g2_mixed_qualifies=ok(g2,joint),
          fcfs_p50_ms=p['FCFS']['median_ttft_ms'],fcfs_p99_ms=tail,online_p99_ms=p[e]['p99_ttft_ms'],order_ref_p99_ms=p[o]['p99_ttft_ms'],joint_ref_p99_ms=p[joint]['p99_ttft_ms'],
          fcfs_tokens=T,fcfs_ms=F,features=f[key(x)],online_maxlag_ms=p[e]['max_lag_ms'],
          online_violations=max(p[n]['violations'] for n in names+['LOOK']),joint_variants_rejected=sum(p['MIN_'+n]['violations']>0 for n in names+['LOOK']))
        assert min(g1,g2l,g2,g3)>-1e-6 and abs(g1+g2+g3-g('FCFS',inf))<1e-7
        cells.append(v)
    return cells
def pred(model,f):
    if model['feature']=='none':return False
    if model['feature']=='all':return True
    a=f[model['feature']];return a>=model['cut'] if model['dir']=='ge' else a<=model['cut']
def metrics(y,flags):
    tp=sum(a and b for a,b in zip(y,flags));n=sum(flags);P=sum(y)
    return dict(n=len(y),material=P,flagged=n,correct_flags=tp,false_positive=n-tp,false_negative=P-tp,
                precision=tp/n if n else None,recall=tp/P if P else None,f1=2*tp/(P+n) if P+n else 0)
def fit(cells,label):
    y=[x[label] for x in cells];candidates=[dict(feature='none'),dict(feature='all')]
    for feat in FEATS:
        xs=sorted(set(c['features'][feat] for c in cells));thresholds=[(a+b)/2 for a,b in zip(xs,xs[1:])]
        for d in ('ge','le'):
            candidates.extend(dict(feature=feat,dir=d,cut=t) for t in thresholds)
    # Among development rules with precision >=0.8, maximize true positives, then precision. A stable first tie wins.
    bestm=candidates[0];bestscore=(0,0.);bm=metrics(y,[False]*len(y))
    for m in candidates[1:]:
        z=metrics(y,[pred(m,c['features']) for c in cells]);pr=z['precision']
        if pr is not None and pr>=.8 and (z['correct_flags'],pr)>bestscore:bestm,bestscore,bm=m,(z['correct_flags'],pr),z
    return {'rule':bestm,'development':bm}
def train():
    kcost={}
    for k in [2,4]:
        vals=[x['policies'][f'K{k}']['work_ms']/x['policies']['FCFS']['work_ms'] for s in PRIMARY for x in scorefile(s) if x['W']==500];kcost[str(k)]=sum(vals)/len(vals)
    k=min((2,4),key=lambda k:kcost[str(k)])
    cells=[z for s in DEV for z in summarize(s,k)];trainset=[z for z in cells if z['trace'] in PRIMARY and z['W']==500];assert len(trainset)==72
    models={lab:fit(trainset,lab) for lab in ['material','literal_material']}
    out=dict(k=k,k_dev_relative_cost=kcost,models=models)
    save(R/'fitted.json',out);save(R/'development_cells.json',cells)
def predict():
    fitted=read(R/'fitted.json');f=features(TEST);out=[]
    for (rho,u,d),v in f.items():out.append(dict(rho=rho,u=u,d=d,flags={lab:pred(model['rule'],v) for lab,model in fitted['models'].items()},features=v))
    save(R/'heldout_predictions.json',out)
def evaluate():
    k=read(R/'fitted.json')['k'];predictions={key(v):v['flags'] for v in read(R/'heldout_predictions.json')};cells=summarize(TEST,k)
    for z in cells:z['flags']=predictions[key(z)]
    result={}
    for lab in ['material','literal_material']:
        primary=[z for z in cells if z['W']==500];m=metrics([x[lab] for x in primary],[x['flags'][lab] for x in primary]);m['go']=bool(m['correct_flags'] and m['precision']>=.8);result[lab]=m
    save(R/'heldout_cells.json',cells);save(R/'decision.json',result)
