"""Independent witness reconstruction (ordered dictionary) and synthetic grid checks."""
from collections import OrderedDict, Counter
from pathlib import Path
import gzip, json, math, struct, subprocess, tempfile
import numpy as np
from decide import R, TEST, read, lines, key
def panel(p):
    with p.open() as f:
        n,nw=map(int,next(f).split());rows=[]
        for line in f:
            t,L,pa,q,*p=map(int,line.split());assert q==len(p);rows.append((t,L,pa,p))
    assert len(rows)==n;return nw,rows
def apply(cache,path,C):
    q=path[:C];h=sum(v in cache for v in q)
    assert all(v in cache for v in q[:h])
    for v in reversed(q):cache[v]=0;cache.move_to_end(v)
    while len(cache)>C:cache.popitem(last=False)
    return h
def audit(file,pfile,scores,cal):
    nw,rows=panel(pfile);N=len(rows);calset=Counter(v for _,_,_,p in rows[:999] for v in p);sizes=[]
    for j in range(999,nw):
        calset.update(rows[j][3])
        if j>=1000:
            for v in rows[j-1000][3]:
                calset[v]-=1
                if not calset[v]:del calset[v]
        sizes.append(len(calset))
    wss=sorted(sizes)[math.ceil(.5*len(sizes))-1];a,b,c=[cal[k] for k in ['a_ms','b_ms_per_token','c_ms_per_token2']]
    rhs={(x['rho'],x['u'],x['d']):x['policies'] for x in scores if x['W']==500}
    fc={};total=0;records=0;maxerr=0
    op=gzip.open if file.suffix=='.gz' else open
    with op(file,'rb') as f:
        while head:=f.readline():
            rho,u,d,name,n=head.decode().split();rho=float(rho);u=float(u);d=int(d);n=int(n);assert n==N-nw
            raw=f.read(12*n);assert len(raw)==12*n
            if (rho,u) not in fc:
                C=max(1,math.floor(wss*rho+.5));warm=OrderedDict()
                for row in rows[:nw]:apply(warm,row[3],C)
                css=warm.copy();dur=[]
                for _,L,_,p in rows[nw:]:h=apply(css,p,C);dur.append(a+(L-h*512)*(b+c*L))
                sc=sum(dur)/(u*(rows[-1][0]-rows[nw][0]));ar=[(v[0]-rows[nw][0])*sc for v in rows[nw:]]
                t=0;ss=[]
                for ar_i,dt in zip(ar,dur):s=max(t,ar_i);ss.append(s);t=s+dt
                fc[(rho,u)]=C,warm,ar,ss
            C,warm,ar,ss=fc[(rho,u)];cache=warm.copy();seen=set();tokens=0;work=0;tt=[];old=0;t=0;ml=-1e9;chunks=0
            for id,start in struct.iter_unpack('<id',raw):
                i=id-nw;ts,L,pa,p=rows[id];assert 0<=i<n and id not in seen and (pa<nw or pa in seen)
                assert sum(j not in seen for j in range(old+nw,id))<d and start+1e-6>=max(t,ar[i]) and start<=ss[i]+500+1e-5
                seen.add(id)
                while old<n and old+nw in seen:old+=1
                ml=max(ml,start-ss[i]);h=apply(cache,p,C);v=L-512*h;cost=a+v*(b+c*L);work+=cost;tokens+=v;chunks+=(v+4095)//4096;t=start+cost;tt.append(t-ar[i])
            v=rhs[(rho,u,d)][name];tt.sort()
            for actu,ref in [(work,v['work_ms']),(tt[math.ceil(.5*n)-1],v['median_ttft_ms']),(tt[math.ceil(.99*n)-1],v['p99_ttft_ms']),(ml,v['max_lag_ms'])]:
                maxerr=max(maxerr,abs(actu-ref));assert math.isclose(actu,ref,rel_tol=1e-9,abs_tol=1e-5)
            assert tokens==v['tokens'] and chunks==v['chunks'] and len(seen)==n and v['violations']==0
            total+=n;records+=1
    return dict(witnesses=records,request_starts_checked=total,max_absolute_numeric_difference_ms=maxerr)
def fixtures():
    root=R;cal=read(R/'calibration.json'); args=[str(cal[k]) for k in ('a_ms','b_ms_per_token','c_ms_per_token2')]
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);src=td/'p';w=1001;n=w+80
        with src.open('w') as out:
            print(n,w,file=out)
            for i in range(n):
                # Interleaved sister paths and independent roots, with linked rows, a mixed long tail, and real queuing.
                x=i%6;pa=i-3 if i>=w+3 and i%13==0 else -1;p=[1+x%3,10+x,20+x]
                L=1537+(i%4)*411;print(i//7*1000,L,pa,len(p),*p,file=out)
        subprocess.run([str(R/'build/pilot'),str(src),'scores',*args,'2',str(td/'raw'),str(td/'w')],check=True)
        res=audit(td/'w',src,lines(td/'raw'),cal)
        assert res['witnesses']==180 and any(v['policies']['DFS']['reordered_groups'] for v in lines(td/'raw'))
        return res
if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='fixtures':print(json.dumps(fixtures()))
    else:
        z=audit(R/'raw/freeinference.witness.gz',R/'panels/freeinference.txt',lines(R/'raw/freeinference.scores.jsonl'),read(R/'calibration.json'))
        assert z['witnesses']==180
        from decide import save
        save(R/'heldout_audit.json',z);print(json.dumps(z))
