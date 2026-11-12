"""Trace replay for the frozen commitment study. No model or scheduler dependencies."""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import heapq
import itertools
import json
import math
from pathlib import Path
import platform
import random
import sys
import time

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text())
BLOCK = CFG["full_block_tokens"]
POLICIES = ("FCFS", "kLPM", "cLPM", "portfolio", "search", "search_LRU")


class Trie:
    def __init__(self):
        self.edges = {}
        self.parent = [-1]
        self.depth = [0]

    def path(self, hashes):
        parent = 0
        path = []
        for h in hashes:
            edge = (parent, h)
            node = self.edges.get(edge)
            if node is None:
                node = len(self.parent)
                self.edges[edge] = node
                self.parent.append(parent)
                self.depth.append(self.depth[parent]+1)
            path.append(node)
            parent = node
        return tuple(path)


@dataclass(frozen=True)
class Request:
    line: int
    arrival: int
    tokens: int
    path: tuple


def hits(path, state):
    # Prefix closure makes the predicate monotone along a path.
    left, right = 0, len(path)
    while left < right:
        mid = (left + right) // 2
        if path[mid] in state:
            left = mid + 1
        else:
            right = mid
    return left


class Cohort:
    def __init__(self, reqs, trie, cap, queue_eviction, tick):
        self.reqs, self.trie, self.cap = reqs, trie, cap
        self.paths = [r.path[:cap] for r in reqs]
        self.queue_eviction, self.tick = queue_eviction, tick
        self.n = len(reqs)
        self.all = (1 << self.n)-1
        self.demands = {}
        self.scores = {}
        self.ops = Counter()

    def indices(self, mask):
        return [i for i in range(self.n) if mask & (1 << i)]

    def demand(self, mask):
        if mask not in self.demands:
            self.demands[mask] = Counter(x for i in self.indices(mask) for x in self.paths[i])
        return self.demands[mask]

    def priority(self, node, mask):
        if not self.queue_eviction or not mask:
            return 0
        if mask not in self.scores:
            self.scores[mask] = {0: 0}
        memo = self.scores[mask]
        trail = []
        while node not in memo:
            trail.append(node)
            node = self.trie.parent[node]
        value = memo[node]
        for v in reversed(trail):
            value = max(value, self.demand(mask)[v] * self.trie.depth[v])
            memo[v] = value
        return value

    def step(self, state, i, mask):
        self.ops["simulated_transitions"] += 1
        path = self.paths[i]
        missing = len(path) - hits(path, state)
        retained = state.copy()
        stamp = self.tick + self.n - mask.bit_count() + 1
        retained.update(dict.fromkeys(path, stamp))
        excess = len(retained)-self.cap
        if excess > 0:
            protected = set(path)
            parents = self.trie.parent
            children = Counter(parents[v] for v in retained)
            remaining = mask ^ (1 << i)

            def key(v):
                return self.priority(v,remaining),retained[v],-self.trie.depth[v],v

            heap = [key(v) for v in retained if v not in children and v not in protected]
            heapq.heapify(heap)
            for _ in range(excess):
                v = heapq.heappop(heap)[-1]
                del retained[v]
                u = parents[v]
                children[u] -= 1
                if u and not children[u] and u not in protected:
                    heapq.heappush(heap,key(u))
        return retained, missing

    def dfs_order(self, state):
        children, ending = defaultdict(list), defaultdict(list)
        size, cached, count, first = Counter(), Counter(), Counter(), {}
        seen = set()
        for i,path in enumerate(self.paths):
            ending[path[-1] if path else 0].append(i)
            for v in path:
                count[v] += 1
                first.setdefault(v,i)
                if v not in seen:
                    children[self.trie.parent[v]].append(v)
                    seen.add(v)
                    size[v] = 1
                    cached[v] = int(v in state)
        for v in sorted(seen, key=lambda u:-self.trie.depth[u]):
            size[self.trie.parent[v]] += size[v]
            cached[self.trie.parent[v]] += cached[v]
        out = []
        stack = [0]
        while stack:
            u = stack.pop()
            out.extend(ending[u])
            def key(v):
                return -(10000*cached[v]/size[v]+.001*count[v]),first[v],v
            stack.extend(reversed(sorted(children[u],key=key)))
        return out

    def pick(self, mode, mask, state):
        choices = self.indices(mask)
        if mode=="FCFS" or (mode=="kLPM" and (self.n-len(choices))%2==0):
            return choices[0]
        if mode in ("kLPM","LPM"):
            return max(choices,key=lambda i:hits(self.paths[i],state))
        demand = self.demand(mask)
        ranks, cold_roots = [], set()
        for i in choices:
            path = self.paths[i]
            h = hits(path,state)
            root = path[0] if path else -(i+1)
            section = 0 if h else (2 if root in cold_roots else 1)
            if h==0:
                cold_roots.add(root)
            shared = next((demand[v] for v in reversed(path) if demand[v]>=2),0)
            ranks.append((section,-h,-sum(demand[v] for v in path),-shared,i))
        return min(ranks)[-1]

    def roll(self, state, mode, order=None):
        chosen, misses, mask = [], 0, self.all
        while mask:
            i = order[len(chosen)] if order is not None else self.pick(mode,mask,state)
            state, m = self.step(state,i,mask)
            misses += m
            chosen.append(i)
            mask ^= 1 << i
        return misses,tuple(chosen),state

    def schedule(self, state, policy):
        if policy not in ("portfolio","search","search_LRU"):
            return self.roll(state,policy)
        trials = [self.roll(state,m) for m in ("FCFS","kLPM","LPM","cLPM")]
        trials.append(self.roll(state,"DFS",self.dfs_order(state)))
        best = min(trials,key=lambda t:t[0])
        if policy=="portfolio":
            return best
        incumbent = best[0]
        self.ops["legal_permutations"] += math.factorial(self.n)

        def explore(curr,mask,cost,order):
            nonlocal best
            self.ops["visited_nodes"] += 1
            lb = cost + sum(v not in curr for v in self.demand(mask))
            if lb >= best[0]:
                self.ops["pruned_nodes"] += 1
                if mask==self.all: self.ops["root_certificates"] += 1
                return
            if not mask:
                best=cost,order,curr
                return
            for i in self.indices(mask):
                nxt,m = self.step(curr,i,mask)
                explore(nxt,mask^(1<<i),cost+m,order+(i,))
        explore(state,self.all,0,())
        self.ops["strict_local_wins"] += int(best[0]<incumbent)
        self.ops["own_entry_saved_blocks"] += incumbent-best[0]
        return best


def packing(intervals, cap):
    """Maximum cardinality intervals on C lanes: drop the latest finish on overflow."""
    # Equal endpoints are interchangeable here, even when blocks differ.
    active, end_heap, negative_ends = Counter(), [], []
    alive = discarded = 0
    for a,b in sorted(intervals):
        while end_heap and end_heap[0]<=a:
            end=heapq.heappop(end_heap)
            alive-=active.pop(end,0)
        heapq.heappush(end_heap,b)
        heapq.heappush(negative_ends,-b)
        active[b]+=1
        alive+=1
        if alive>cap:
            while not active[-negative_ends[0]]:
                heapq.heappop(negative_ends)
            end=-heapq.heappop(negative_ends)
            active[end]-=1
            alive-=1
            discarded+=1
    return len(intervals)-discarded


def lower_bounds(groups,cap,initial):
    prev, seen, intervals = dict.fromkeys(initial,-1),set(),[]
    total=distinct=0
    for i,g in enumerate(groups):
        u={v for r in g for v in r.path[:cap]}
        total+=sum(r.tokens-BLOCK*min(cap,len(r.path)) for r in g)
        distinct+=len(u)
        for v in u:
            if v in prev: intervals.append((prev[v],i))
            prev[v]=i
        seen.update(u)
    h=packing(intervals,cap)
    return dict(cut_lb=total+BLOCK*(distinct-h),unique_lb=total+BLOCK*len(seen-initial.keys()),
                always_tokens=total,cohort_demands=distinct,packed_intervals=h)


def gates(reqs,end_time):
    groups,flush=[],[]
    current=[]
    for r in reqs:
        if current and r.arrival>current[0].arrival+1000:
            groups.append(current);flush.append(current[0].arrival+1000);current=[]
        current.append(r)
        if len(current)==4:
            groups.append(current);flush.append(r.arrival);current=[]
    if current:
        groups.append(current);flush.append(min(end_time,current[0].arrival+1000))
    return groups,flush


def replay(rows,interval,workload,bid,stage):
    tree=Trie()
    left,right=interval
    warm,measured=[],[]
    short=long_hash=0
    for timestamp,line,tokens,blocks in rows:
        if not left<=timestamp<right: continue
        full=max(0,(tokens-1)//BLOCK)
        short+=len(blocks)<full
        long_hash+=len(blocks)>math.ceil(tokens/BLOCK)
        path=tree.path(blocks[:full])
        req=Request(line,timestamp,tokens,path)
        (warm if 4*(timestamp-left)<right-left else measured).append(req)
    groups,flush=gates(measured,right)
    result=dict(workload=workload,bin=bid,start_ms=left,end_ms=right,warm_requests=len(warm),
                requests=len(measured),tokens=sum(r.tokens for r in measured),
                max_transient_input_tokens=max((r.tokens for r in warm+measured),default=0),
                short_hash_rows=short,extra_beyond_ceiling_hash_rows=long_hash,
                cohort_sizes=dict(Counter(map(len,groups))),
                intentional_wait_ms=[f-r.arrival for g,f in zip(groups,flush) for r in g],
                capacities={})
    for cap in (128,32):
        state0={}; warm_compute=0
        for j,r in enumerate(warm):
            w=Cohort([r],tree,cap,False,j)
            state0,m=w.step(state0,0,1)
            warm_compute+=r.tokens-BLOCK*(len(w.paths[0])-m)
        bound=lower_bounds(groups,cap,state0)
        runs={}
        for policy in POLICIES:
            cpu=time.process_time_ns()
            state=state0;tick=len(warm);computed=0;ops=Counter();orders=[];displaced=[]
            for g in groups:
                q=Cohort(g,tree,cap,policy in ("portfolio","search","cLPM"),tick)
                before=state
                miss,order,state=q.schedule(state,policy)
                if stage=="development" and policy.startswith('search'):
                    ref=Cohort(g,tree,cap,q.queue_eviction,tick)
                    brute=min(ref.roll(before,'DFS',perm)[0] for perm in itertools.permutations(range(len(g))))
                    assert brute==miss
                assert len(state)<=cap and all(tree.parent[v]==0 or tree.parent[v] in state for v in state)
                total=sum(r.tokens for r in g)
                computed+=total-BLOCK*(sum(map(len,q.paths))-miss)
                ops.update(q.ops);tick+=len(g)
                orders.append([g[i].line for i in order])
                displaced.extend(abs(k-i) for k,i in enumerate(order))
            assert bound['unique_lb']<=bound['cut_lb']<=computed<=result['tokens']
            runs[policy]=dict(prefill=computed,cpu_ns=time.process_time_ns()-cpu,
                              max_displacement=max(displaced,default=0),sum_displacement=sum(displaced),
                              ops=dict(ops),dispatch_lines=orders)
        result['capacities'][str(cap)]=dict(warm_prefill=warm_compute,initial_size=len(state0),**bound,runs=runs)
    return result


def read_trace(name):
    src=HERE/'inputs'/(name+'.jsonl')
    data=src.read_bytes()
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==CFG['git_blobs'][name]
    rows=[]
    for i,l in enumerate(data.splitlines()):
        v=json.loads(l)
        timestamp,length,blocks=v['timestamp'],v['input_length'],v['hash_ids']
        assert type(timestamp) is int and timestamp>=0 and type(length) is int and length>=0
        assert isinstance(blocks,list) and all(type(b) is int for b in blocks)
        rows.append((timestamp,i,length,blocks))
    rows.sort(key=lambda r:(r[0],r[1]))
    return rows


def checks():
    tree=Trie(); a=tree.path(['a']); by=tree.path(['b','y']); byz=tree.path(['b','y','z'])
    def req(path,i):
        return Request(i,i,BLOCK*len(path)+1,path)
    initial={a[0]:1,by[0]:2,by[1]:2}
    q=Cohort([req(byz,0),req(a,1)],tree,3,True,2)
    assert q.roll(initial,'LPM')[0]==2 and q.schedule(initial,'search')[0]==1
    # Every small instance independently verifies the interval count against all subsets.
    rng=random.Random(3419)
    for _ in range(60):
        intervals=[]
        for j in range(7):
            start=rng.randrange(-1,3);intervals.append((start,rng.randrange(start+1,5)))
        for cap in (1,2):
            feasible=[len(sel) for k in range(8) for sel in itertools.combinations(intervals,k)
                      if all(sum(a<=t<b for a,b in sel)<=cap for t in range(-1,5))]
            assert packing(intervals,cap)==max(feasible)
    # Global reversal with the same mandatory path retention and transient workspace.
    az,ax,bt=tree.path(['a','z']),tree.path(['a','x']),tree.path(['b','t'])
    q=Cohort([req(bt,0),req(ax,1)],tree,2,True,1)
    init=dict.fromkeys(az,1)
    nextq=Cohort([req(ax,2)],tree,2,True,3)
    costs=[]
    for o in [(1,0),(0,1)]:
        first,_,end=q.roll(init,'DFS',o)
        costs.append(first+nextq.roll(end,'FCFS')[0])
    assert costs==[5,4]
    # A capacity-one global relaxation can grant an impossible free within-cohort hit.
    b=tree.path(['b'])
    groups=[[req(a,0)],[req(b,1),req(b,2)],[req(a,3)]]
    assert lower_bounds(groups,1,{})['cut_lb']==2*BLOCK+4
    return 'PASS'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('stage',choices=['checks','development','evaluation'])
    stage=ap.parse_args().stage
    if stage=='checks':
        print(checks());return
    out=HERE/(stage+'.jsonl')
    if stage=='evaluation':
        receipt=json.loads((HERE/'development_receipt.json').read_text())
        assert receipt['status']=='COMPLETE' and receipt['groups']==8
        assert receipt['script_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    time0=time.perf_counter();cpu0=time.process_time();count=0
    with out.open('x') as f:
        try:
            for name in CFG['paths']:
                rows=read_trace(name)
                start,stop=rows[0][0],rows[-1][0]+1
                chosen=random.Random(CFG['split']['seeds'][name]).sample(range(48),20)
                chosen=chosen[:4] if stage=='development' else chosen[4:]
                # Integer ceilings implement half-open equal-duration bins for integer timestamps.
                edges=[start+((stop-start)*k+47)//48 for k in range(49)]
                for bid in sorted(chosen):
                    record=replay(rows,(edges[bid],edges[bid+1]),name,bid,stage)
                    f.write(json.dumps(record,separators=(',',':'))+'\n');f.flush();count+=1
                    print(name,bid,'completed',flush=True)
        except BaseException as exc:
            (HERE/(stage+'_failure.json')).write_text(json.dumps({'completed':count,'reason':repr(exc)}))
            raise
    receipt=dict(status='COMPLETE',groups=count,wall_seconds=time.perf_counter()-time0,
                 cpu_seconds=time.process_time()-cpu0,python=sys.version,platform=platform.platform(),
                 raw_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
                 script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 config_sha256=hashlib.sha256((HERE/'config.json').read_bytes()).hexdigest())
    (HERE/(stage+'_receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    main()
