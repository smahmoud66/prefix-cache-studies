"""Single frozen correctness replay followed by three matched native timing repetitions."""
from collections import deque, defaultdict
from dataclasses import dataclass
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import signal
import statistics
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PREV = HERE.parent / 'exit_cache_20261108'
sys.path.insert(0, str(PREV))
import runner as old
base = old.base
MODES = ('K','IMM','REF','OPT')
ORIGINAL = dict(K='kLPM', IMM='search_LRU', REF='TIE', OPT='TIE')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_stages():
    bins = {}
    for name in ('development','online'):
        assert sha(PREV/(name+'.jsonl')) == json.loads((PREV/(name+'_receipt.json')).read_text())['raw_sha256']
        with (PREV/(name+'.jsonl')).open() as f:
            for line in f:
                rec=json.loads(line)
                bins[name,rec['workload'],rec['bin']]=rec
    return bins


@dataclass
class Episode:
    key: tuple
    cap: int
    trie: object
    initial: dict
    tick: int
    warm_groups: list
    groups: list
    warm_msgs: list
    msgs: list
    tail_tokens: list
    n: int
    expected: dict
    warm_misses: int


def prepare():
    start=time.perf_counter();cpu=time.process_time()
    old_bins=read_stages()
    old_record_cpu=time.process_time()-cpu
    input_cpu=gate_cpu=encode_cpu=truth_warm_cpu=0.0
    episodes={}
    for trace in ('conversation','toolagent'):
        tick0=time.process_time()
        rows=base.read_trace(trace)
        input_cpu+=time.process_time()-tick0
        for key,old_bin in old_bins.items():
            stage,tr,bid=key
            if tr!=trace:continue
            tick0=time.process_time()
            raw_warm,raw_groups,_=old.read_bin(trace,rows,bid)
            tree=base.Trie()
            warm=[old.materialize(g,tree) for g in raw_warm]
            groups=[old.materialize(g,tree) for g in raw_groups]
            gate_cpu+=time.process_time()-tick0
            assert [[r.line for r in g] for g in groups]==old_bin['groups']
            for cap in (128,32):
                def msg(g):
                    return old.cohort_wire([r.path[:cap] for r in g])
                tick0=time.process_time()
                state={};tick=0;warm_misses=0;warm_positions=0
                for g in warm:
                    for req in g:
                        q=base.Cohort((req,),tree,cap,False,tick)
                        state,m=q.step(state,0,1)
                        warm_misses+=m;warm_positions+=req.tokens-512*(len(q.paths[0])-m)
                        tick+=1
                truth_warm_cpu+=time.process_time()-tick0
                tick0=time.process_time()
                previous=old_bin['capacities'][str(cap)]
                assert warm_positions==previous['warm_prefill']
                episodes[key,cap]=Episode(key,cap,tree,state,tick,warm,groups,
                    ['W '+msg(g)+'\n' for g in warm],['G '+msg(g)+'\n' for g in groups],
                    [sum(r.tokens-512*min(len(r.path),cap) for r in g) for g in groups],
                    old_bin['n'],previous['runs'],warm_misses)
                encode_cpu+=time.process_time()-tick0
    # Only immutable input metadata, pre-framed demand and old verification records are shared.
    return episodes,dict(seconds=time.perf_counter()-start,cpu=time.process_time()-cpu,
                         archived_records_cpu=old_record_cpu,input_parse_sha_cpu=input_cpu,group_and_id_cpu=gate_cpu,warm_truth_cpu=truth_warm_cpu,encode_both_caps_cpu=encode_cpu,encoded_group_bytes=sum(sum(map(len,e.msgs+e.warm_msgs)) for e in episodes.values()))


class Native:
    def __init__(self):
        self.proc=subprocess.Popen([str(HERE/'evaluator')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   text=True,encoding='ascii',bufsize=1)

    def call(self,text):
        self.proc.stdin.write(text)
        self.proc.stdin.flush()
        line=self.proc.stdout.readline()
        if not line:
            raise RuntimeError('Unexpected end of native response')
        rec=json.loads(line)
        if 'error' in rec:raise RuntimeError(rec['error'])
        return rec

    def begin(self,ep,mode,absolute):
        self.call(f'R {mode} {int(absolute)} {ep.cap}\n')
        misses=0
        for msg in ep.warm_msgs:
            misses+=self.call(msg)['immediate_blocks']
        assert misses==ep.warm_misses

    def close(self):
        self.proc.stdin.close()
        _,status,usage=os.wait4(self.proc.pid,0)
        self.proc.returncode=os.waitstatus_to_exitcode(status)
        self.proc.stdout.close()
        if self.proc.returncode:raise RuntimeError(f'Native exit {self.proc.returncode}')
        return dict(cpu=usage.ru_utime+usage.ru_stime,rss=usage.ru_maxrss)


def selected_truth(ep,mode):
    state=ep.initial.copy();tick=ep.tick
    history=deque(ep.warm_groups,maxlen=16);out=[]
    old_run=ep.expected[ORIGINAL[mode]]
    assert len(ep.groups)==len(old_run['cohorts'])==len(ep.tail_tokens)
    for g,saved,tails in zip(ep.groups,old_run['cohorts'],ep.tail_tokens):
        q=base.Cohort(g,ep.trie,ep.cap,False,tick)
        order=saved['order']
        misses,_,state=q.roll(state,'DFS',order)
        assert saved['prefill']==tails+512*misses
        tick+=len(g)
        future=0;m=len(history)//2
        if mode=='REF':
            hist=list(history)
            for j in range(0,2*m,2):
                hypothetical=state;clock=tick
                for past in hist[len(hist)-2-j:len(hist)-j]:
                    hq=base.Cohort(past,ep.trie,ep.cap,False,clock)
                    cost,_,hypothetical=hq.roll(hypothetical,'kLPM')
                    future+=cost;clock+=len(past)
        out.append(dict(order=order,state=old.canonical(state,ep.trie),miss=misses,work=saved['prefill'],
                        den=max(1,m),value=max(1,m)*misses+future,future=future,
                        incumbent=saved.get('incumbent'),adv=saved.get('adv_num_blocks')))
        history.append(g)
    assert sum(v['work'] for v in out)==old_run['prefill']
    return out


def signature(rec):
    return (tuple(rec['order']),tuple(rec['selected_exit']),rec['immediate_blocks'])


def verify(episodes,log):
    expected={};counts=defaultdict(int)
    native=Native()
    try:
        for (key,cap),ep in episodes.items():
            references={mode:selected_truth(ep,mode) for mode in ('K','IMM','REF')}
            for mode in MODES:
                native.begin(ep,mode,True)
                truth=references['REF' if mode=='OPT' else mode]
                sequence=[]
                assert len(ep.msgs)==len(truth)
                for i,(msg,target) in enumerate(zip(ep.msgs,truth)):
                    result=native.call(msg)
                    where=key,cap,mode,i
                    assert result['order']==target['order'],('order',where,result['order'],target['order'])
                    assert result['selected_exit']==target['state'],('state',where)
                    assert result['immediate_blocks']==target['miss'],('work',where)
                    if mode in ('REF','OPT'):
                        assert result['incumbent']==target['incumbent'],('incumbent',where)
                        assert (result['den'],result['future_blocks'],result['objective_num'])==(
                               target['den'],target['future'],target['value']),('historical objective',where)
                    sequence.append(signature(result))
                    if mode=='OPT':
                        log.write(json.dumps([*key,cap,i,target['order'],target['state'],target['work'],
                                 target['incumbent'],target['den'],target['value']],separators=(',',':'))+'\n')
                counts[f'{key[0]}_{mode}_cohorts']+=len(sequence)
                expected[key,cap,mode]=sequence
                if mode=='OPT':assert sequence==expected[key,cap,'REF']
    finally:
        resource_info=native.close()
    return expected,dict(counts),resource_info


def timed_cell(keys,episodes,references,mode,rep,raw):
    cpu0=time.process_time();wall0=time.perf_counter()
    native=Native();records=0;work=0;setup_ns=0
    try:
        for key,cap in keys:
            ep=episodes[key,cap]
            start=time.perf_counter_ns();native.begin(ep,mode,False)
            setup_ns+=time.perf_counter_ns()-start
            for i,msg in enumerate(ep.msgs):
                start=time.perf_counter_ns();cpu_start=time.process_time_ns()
                result=native.call(msg)
                wrapper_ns=time.process_time_ns()-cpu_start
                wall_ns=time.perf_counter_ns()-start
                assert signature(result)==references[key,cap,mode][i],('timed decision mismatch',rep,mode,key,cap,i)
                assert result['immediate_blocks']>=0
                positions=ep.tail_tokens[i]+512*result['immediate_blocks']
                work+=positions;records+=1
                # Logging/validation are outside the individual decision clock and included in cell CPU.
                counters={k:v for k,v in result.items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
                raw.write(json.dumps(dict(rep=rep,mode=mode,trace=key[1],bin=key[2],cap=cap,j=i,
                    work=positions,wall_ns=wall_ns,wrapper_cpu_ns=wrapper_ns,**counters),separators=(',',':'))+'\n')
    finally:
        usage=native.close()
    return dict(rep=rep,mode=mode,trace=keys[0][0][1],cap=keys[0][1],cohorts=records,work=work,
                cpu_wrapper_all=time.process_time()-cpu0,cpu_child_all=usage['cpu'],
                wall_all=time.perf_counter()-wall0,reset_warm_wall=setup_ns/1e9,child_peak_rss=usage['rss'])


def resident_bytes(x):
    return x if sys.platform=='darwin' else 1024*x


def main():
    freeze=json.loads((HERE/'freeze.json').read_text())
    for name,val in freeze['hashes'].items():assert sha(HERE/name)==val,name
    def timeout(*_):raise TimeoutError('Frozen benchmark numerical time ceiling')
    signal.signal(signal.SIGALRM,timeout)
    # 1 wrapper and 1 active single-thread native process; leave 600 CPU-s for tests/analysis.
    signal.alarm(1450)
    start=time.perf_counter();cpu=time.process_time()
    lock=HERE/'benchmark.lock'
    with lock.open('x') as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n')
    cells=[]
    try:
        eps,prep=prepare()
        c=time.process_time();w=time.perf_counter()
        with gzip.open(HERE/'equivalence.jsonl.gz','xt',compresslevel=1) as f:
            expected,counts,vcpu=verify(eps,f)
        verification=dict(cpu_wrapper=time.process_time()-c,wall=time.perf_counter()-w,**vcpu,counts=counts)
        (HERE/'equivalence_receipt.json').write_text(json.dumps(verification,indent=2)+'\n')
        rng=random.Random(20261108)
        with gzip.open(HERE/'timings.jsonl.gz','xt',compresslevel=1) as raw:
            for rep in range(1,4):
                groups=[(trace,cap) for trace in ('conversation','toolagent') for cap in (128,32)]
                rng.shuffle(groups)
                for trace,cap in groups:
                    keys=sorted(k for k in eps if k[0][:2]==('online',trace) and k[1]==cap)
                    assert len(keys)==28
                    modes=list(MODES);rng.shuffle(modes)
                    for mode in modes:
                        cell=timed_cell(keys,eps,expected,mode,rep,raw)
                        cell['child_peak_rss_bytes']=resident_bytes(cell.pop('child_peak_rss'))
                        cells.append(cell)
                print('Completed fixed repetition',rep,flush=True)
        ch=resource.getrusage(resource.RUSAGE_CHILDREN); su=resource.getrusage(resource.RUSAGE_SELF)
        result=dict(status='COMPLETE',preparation=prep,verification=verification,cells=cells,
                    wall_seconds=time.perf_counter()-start,wrapper_cpu=time.process_time()-cpu,
                    child_cpu=ch.ru_utime+ch.ru_stime,wrapper_peak_rss_bytes=resident_bytes(su.ru_maxrss),
                    child_peak_rss_bytes=resident_bytes(ch.ru_maxrss),peak_note='maximum across native processes, distinct from wrapper',
                    raw_hashes={k:sha(HERE/k) for k in ('equivalence.jsonl.gz','timings.jsonl.gz')})
        (HERE/'benchmark_receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    except BaseException as exc:
        (HERE/'benchmark_failure.json').write_text(json.dumps(dict(error=repr(exc),completed_cells=cells))+'\n')
        raise
    finally:
        signal.alarm(0)


if __name__=='__main__':
    main()
