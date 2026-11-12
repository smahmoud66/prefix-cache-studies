"""Prepare the frozen 512-token panel. No policy effects are read or computed here."""
import sys,json,hashlib
from pathlib import Path
from itertools import islice
ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT.parent/'exit_cache_20261108'))
import runner as old

def sha(f):
    with f.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
def write(name, rows):
    with (ROOT/'panel'/name).open('x') as f:
        for phase,group,ms,tok,parent,path in rows:
            print(phase,group,ms,tok,parent,len(path),*path,file=f)
def main():
    (ROOT/'panel').mkdir()
    sources={}
    for trace in ('conversation','toolagent'):
        src=old.PARENT/'inputs'/f'{trace}.jsonl'
        sources[str(src.relative_to(ROOT.parent))]=sha(src)
        rows=old.base.read_trace(trace)
        for bid in old.SPLIT['traces'][trace]['new_eval']:
            tree=old.base.Trie()
            warm,groups,_=old.read_bin(trace,rows,bid)
            prepared=[]
            for phase,sets in [(0,warm),(1,groups)]:
                for j,g in enumerate(sets):
                    for r in old.materialize(g,tree):
                        prepared.append((phase,j,r.arrival,r.tokens,-1,r.path[:128]))
            write(f'{trace}-{bid}',prepared)
    ext=ROOT.parent/'external_tie_20261109'
    for name in 'AB':
        src=ext/'source'/f'qwen_trace{name}_blksz_16.jsonl'
        paths=ext/'panel'/f'{name}_512.rows'
        gates=ext/'panel'/f'{name}_gate.json'
        for f in (src,paths,gates):sources[str(f.relative_to(ROOT.parent))]=sha(f)
        receipt=json.loads((ext/'panel'/f'{name}_adapter_receipt.json').read_text())
        assert sha(paths)==receipt['outputs']['512'] and sha(src)==receipt['raw_sha256']
        gs=json.loads(gates.read_text())
        fields=[(g['phase']=='G',i,t) for i,g in enumerate(gs) for t in g['arrivals_ms']]
        seen={}; prepared=[]
        with src.open() as raw,paths.open() as rows:
            for i,((meas,j,ms),r,line) in enumerate(zip(fields,islice(raw,21000),rows,strict=True)):
                obj=json.loads(r); ts,L,*ids=line.split()
                assert round(float(ts)*1000)==ms and int(L)==obj['input_length']
                parent=seen.get(obj['parent_chat_id'],-1)
                assert obj['parent_chat_id']==-1 or parent>=0
                assert obj['chat_id'] not in seen
                if name=='B':assert parent==-1
                seen[obj['chat_id']]=i
                prepared.append((int(meas),j,ms,int(L),parent,list(map(int,ids))))
        write(name,prepared)
    (ROOT/'inputs.json').write_text(json.dumps(dict(sources=sources,panels={p.name:sha(p) for p in sorted((ROOT/'panel').iterdir())}),indent=2))
if __name__=='__main__':main()
