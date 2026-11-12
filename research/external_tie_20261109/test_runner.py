"""Small synthetic adapter/causality/control checks independent of the scheduler's transition."""
import csv
from io import StringIO
from itertools import permutations
from pathlib import Path
from collections import Counter
import json
import resource
import subprocess
import time

here=Path(__file__).resolve().parent
# A rooted prefix trie truncated by the caller's capacity; includes an empty reusable path.
paths=[(), (1,), (1,2), (1,2,3), (1,4), (5,), (5,6), (5,6,7), (8,9,10,11)]
ix=[(1,), (2,3,4,5), (0,6), (6,3,1,8), (4,7,3,8), (1,1), (7,6,0,8),
    (5,1,6,4), (8,7,3,2), (0,), (0,8,2), (7,8,3), (2,4,1,8)]
seq=[tuple(paths[j] for j in group) for group in ix*2]

def frame(group,stage,block):
    fields=[stage,str(len(group))]
    for path in group:
        fields.extend([str(block*len(path)+1),str(len(path)),*map(str,path)])
    return ' '.join(fields)+'\n'

def step(s,p,cap):
    missing=sum(x not in s for x in p)
    return tuple((list(p)+[x for x in s if x not in p])[:cap]),missing

def all_exits(s, g,cap):
    out={}
    for order in permutations(range(len(g))):
        state=s
        cost=0
        for i in order:
            state,m=step(state,g[i],cap)
            cost+=m
        out[order]=(cost,state)
    return out

def test(exe,size,kind):
    panels=['W']*3+['G']*(len(seq)-3)
    data=''.join(frame(g,z,16) for g,z in zip(seq,panels))
    p=subprocess.run([str(exe),kind,str(size),'16','4719'],input=data,text=True,
                     capture_output=True,check=True)
    states=[]
    state=()
    for k,(row,group,stage) in enumerate(zip(csv.DictReader(StringIO(p.stdout), delimiter='\t'),
                                              seq,panels,strict=True)):
        g=tuple(path[:size] for path in group)
        orders=all_exits(state,g,size)
        order=tuple(map(int,row['order']))
        cost,nextstate=orders[order]
        assert int(row['blocks'])==cost and int(row['work'])==sum(16*(len(a)-len(b))+1 for a,b in zip(group,g))+16*cost
        if stage=='W' or kind=='FCFS':
            assert order==tuple(range(len(g)))
        elif kind=='K':
            observed=[]
            cache=state
            pending=list(range(len(g)))
            while pending:
                i=pending[0] if len(observed)%2==0 else max(pending,key=lambda j:sum(x in cache for x in g[j]))
                observed.append(i);pending.remove(i)
                cache,_=step(cache,g[i],size)
            assert tuple(observed)==order
        else:
            mincost=min(x[0] for x in orders.values())
            co={o:e for o,(m,e) in orders.items() if m==mincost}
            inc=tuple(map(int,row['inc']))
            assert inc in co and order in co
            if kind!='IMM':
                assert int(row['exits'])==len(set(co.values())) and int(row['eligible'])==len(co)
                assert order==min([o for o in co if co[o]==nextstate],key=lambda o:(o!=inc,o))
            if kind=='RANK':
                recent=seq[max(0,k-16):k]
                if len(recent)%2: recent=recent[1:]
                freq=Counter(node for group in recent for p in group for node in p[:size])
                def key(o):
                    return (-sum((size-k)*freq[node] for k,node in enumerate(co[o])),o!=inc,o)
                assert order==min(co,key=key)
        state=nextstate
        states.append((order,state))
    assert len(states)==len(seq)
    return states

if __name__=='__main__':
    wall=time.monotonic(); cpu=time.process_time()
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    cases=0
    for executable,capacity in [('replay_128',3),('replay_4096',3),('replay_4096',4096)]:
        for kind in ('OPT','IMM','K','FCFS','RANK','RAND','CHECK'):
            test(here/executable,capacity,kind)
            cases+=len(seq)
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    print(json.dumps(dict(result='PASS',synthetic_cohorts_across_cells=cases,
        test_cpu_seconds=time.process_time()-cpu+after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
        wall_seconds=time.monotonic()-wall)))
