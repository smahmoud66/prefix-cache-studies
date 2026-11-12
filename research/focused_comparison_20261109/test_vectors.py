"""Apply the archived, independent stamped-leaf oracle to every reported candidate."""
import itertools
import json
import os
from pathlib import Path
import resource
import sys
import time
sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'exact_tie_20261108'))
import test_exact as leaf

def packed(order):
    value=0
    for i in order: value=value*4+i
    return value

def verify_fixture(query,case):
    cap,group,entry,past=case.cap,case.current,case.entry,case.history
    inc,cost,_,actions=leaf.candidate_info(entry,group,cap)
    reps={}
    for order,state in actions:
        if state not in reps or order==inc: reps[state]=order
    future={s:leaf.future_sum(s,past,cap) for s in reps}
    order,state=min(actions,key=lambda a:(future[a[1]],a[0]!=inc,a[0]))
    targets=sorted([packed(o),future[s]] for s,o in reps.items())
    for m in ('FULL','R00','FOCUSED','R10','R01','R11'):
        for absolute in [False,True]:
            rec=query(leaf.message(case,m,inc,absolute))
            assert (tuple(rec['incumbent']),tuple(rec['order']),tuple(rec['selected_exit']),rec['immediate_blocks'])==(inc,order,state,cost),(case,m,rec)
            if absolute:
                assert sorted(rec['candidate_scores'])==targets,(case,m,targets,rec)
                assert rec['objective_num']==max(1,len(past[-16:])//2)*cost+future[state]
            else: assert not rec.get('candidate_scores')
    return len(targets)

if __name__=='__main__':
    wall=time.monotonic();tick=time.process_time()
    n=nv=0
    with leaf.engine([str(HERE/'evaluator')]) as query:
        for case in itertools.chain(leaf.small_cases(),leaf.targeted_cases()):
            nv+=verify_fixture(query,case); n+=1
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    print(json.dumps(dict(status='PASS',binary_sha256=leaf.digest(HERE/'evaluator'),leaf_oracle_sha256=leaf.digest(Path(leaf.__file__)),
                          fixtures=n,unique_exit_scores_across_fixtures=nv,method_names=6,
                          absolute_decision_checks=12*n,python_cpu_s=time.process_time()-tick,
                          child_cpu_s=child.ru_stime+child.ru_utime,wall_s=time.monotonic()-wall),indent=2))
