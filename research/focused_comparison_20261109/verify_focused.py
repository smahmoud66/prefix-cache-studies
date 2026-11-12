"""Verify simultaneous, correlated younger sets and the native scoring modes against leaf LRU.
Only the archived synthetic tries and cases are read. No trace input or timing panel.
"""
from collections import Counter
from contextlib import nullcontext
from functools import lru_cache
from itertools import chain
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'exact_tie_20261108'))
import test_exact as oracle


def literal(entry,support):
    """Bitmask of all younger identities for each tracked resident, including unrelated ones."""
    younger=0
    sets=dict.fromkeys(support,None)
    for identity in entry:
        if identity in sets:
            sets[identity]=younger
        younger |= 1 << identity
    return sets


def update(sets,path,cap):
    """Read every entry-time hit before assigning the complete path's new younger sets."""
    misses=sum(sets[x] is None for x in path)
    preceding=0
    result={}
    for x in path:
        result[x]=preceding
        preceding |= 1 << x
    for x,mask in sets.items():
        if x in result:
            continue
        expanded=None if mask is None else mask|preceding
        result[x]=expanded if expanded is not None and expanded.bit_count()<cap else None
    return misses,result


def packed(order):
    s=0
    for i in order:
        s=(s<<2)|i
    return s


def run(native):
    seen=Counter()
    modes=['FULL','FOCUSED','R00','R10','R01','R11']

    @lru_cache(maxsize=None)
    def pair(cap,entry,first,second):
        support=frozenset(x for g in (first,second) for path in g for x in path)
        state=entry
        sets=literal(entry,support)
        orders=[]; costs=[]
        for group in (first,second):
            pending=list(range(len(group)))
            selected=[]
            while pending:
                i=pending[0] if len(selected)%2==0 else max(
                    pending,key=lambda index:sum(sets[x] is not None for x in group[index]))
                path=group[i]
                misses,sets=update(sets,path,cap)
                expected,state=oracle.serve(state,path,cap)
                assert misses==expected and sets==literal(state,support)
                selected.append(i);costs.append(misses);pending.remove(i)
                seen['literal_focused_update_vs_leaf']+=1
            orders.append(selected)
        hits=sum(x in support for x in entry)
        ahead=max((i for i,x in enumerate(entry,1) if x in support),default=0)-hits
        if len(support)+ahead<=cap:
            assert sum(costs)==len(support)-hits
            seen['certified_literal_pairs']+=1
        seen['distinct_literal_pair_runs']+=1
        if native is not None:
            args=(f'{cap} {len(entry)} '+' '.join(map(str,entry))+' A '+oracle.group_wire(first)
                  +' B '+oracle.group_wire(second))
            for mode in ['FULL','FOCUSED']:
                record=native(f'X {mode} {args}')
                assert record['orders']==orders and record['costs']==costs,(mode,args,record,orders,costs)
                seen['native_continuation_trajectories']+=1
        return sum(costs)

    # The opposite scalar serialization gives a false extra miss.
    result=pair(2,(2,19),((19,7),),((),))
    assert result==1
    scalar_state=(2,19)
    scalar_cost=0
    for x in (7,19):
        scalar_cost+=x not in scalar_state
        scalar_state=(x,*(y for y in scalar_state if y!=x))[:2]
    assert scalar_cost==2 and scalar_state==(19,7)
    # Equal projected ranks, distinct outsider identities; absence, gap and repeated requests.
    for state in [(9,19),(6,19),(),(19,)]:
        pair(2,state,((41,),(19,),(2,)),((19,),(19,)))
    for case in chain(oracle.small_cases(),oracle.targeted_cases()):
        inc,minwork,_,eligible=oracle.candidate_info(case.entry,case.current,case.cap)
        reps={}
        for order,state in eligible:
            if state not in reps or (order!=inc,order)<(reps[state]!=inc,reps[state]):
                reps[state]=order
        history=case.history[-16:]
        future={s:sum(pair(case.cap,s,history[j],history[j+1])
                      for j in range(len(history)%2,len(history),2)) for s in reps}
        assert future=={s:oracle.future_sum(s,history,case.cap) for s in reps}
        winner=min(reps,key=lambda s:(future[s],reps[s]!=inc,reps[s]))
        den=max(1,len(history)//2)
        expected_scores=sorted((packed(o),future[s]) for s,o in reps.items())
        seen['synthetic_decisions']+=1
        seen['eligible_candidate_scores']+=len(expected_scores)
        if native is not None:
            for mode in modes:
                for absolute in [False,True]:
                    request=oracle.message(case,mode,inc,absolute)
                    d=native(request)
                    assert tuple(d['order'])==reps[winner] and tuple(d['incumbent'])==inc,(mode,case,d)
                    assert tuple(d['selected_exit'])==winner and d['immediate_blocks']==minwork,(mode,case,d)
                    if absolute:
                        assert d['future_blocks']==future[winner] and d['objective_num']==minwork*den+future[winner]
                        assert sorted(tuple(p) for p in d['candidate_scores'])==expected_scores,(mode,case,d,expected_scores)
                    seen['native_choice_score_checks']+=1
    return dict(seen)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--native',type=Path)
    parser.add_argument('--receipt',type=Path)
    options=parser.parse_args()
    now=time.monotonic();cpu=time.process_time()
    with (oracle.engine([str(options.native.resolve())]) if options.native else nullcontext()) as native:
        result=run(native)
    worker=resource.getrusage(resource.RUSAGE_CHILDREN)
    result.update(cpu_seconds=time.process_time()-cpu+worker.ru_utime+worker.ru_stime,
                  wall_seconds=time.monotonic()-now,status='PASS',
                  verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if options.native:
        result['binary_sha256']=hashlib.sha256(options.native.read_bytes()).hexdigest()
    if options.receipt:
        with options.receipt.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
