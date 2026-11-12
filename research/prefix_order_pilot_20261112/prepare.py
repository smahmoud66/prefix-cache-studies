"""Build a source-only arrival panel. Holdout mode requires the protocol freeze."""
from pathlib import Path
import hashlib, heapq, json, struct, subprocess, sys
from array import array
R=Path(__file__).resolve().parent
N=5000; WARM=2000; MAXPATH=128
FI='39f75bbba1ce912546517802719ef7742d0db7fa53dcbc66681bba090aa5d1f7'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def intern(rows):
    d={};out=[]
    for t,L,pa,namespace,edges in rows:
        node=0;path=[]
        for edge in edges[:min(MAXPATH,max(0,(L-1)//512))]:
            key=(namespace,node,edge);node=d.setdefault(key,len(d)+1);path.append(node)
        out.append((t,L,pa,path))
    return out
def moon(n):
    src=R.parent/'commitment_20261108/inputs'/f'{n}.jsonl'
    a=sorted([(v['timestamp']*1000,i,v['input_length'],v['hash_ids']) for i,s in enumerate(src.open()) if (v:=json.loads(s))],key=lambda x:(x[0],x[1]))[:N]
    return intern([(t,L,-1,0,e) for t,i,L,e in a]),{'source_sha256':sha(src)}
def qwen(n):
    from itertools import islice
    src=R.parent/'exit_aware_opportunity/panel'/('A' if n=='qwenchat' else 'B');out=[]
    for s in islice(src.open(),N):
        phase,gate,ms,L,pa,count,*path=map(int,s.split());assert count==len(path)
        out.append((ms*1000,L,pa,path))
    return out,{'source_sha256':sha(src)}
def fi():
    assert (R/'freeze.json').exists()
    src=R/'sources/freeinference.lcp.zst'; assert sha(src)==FI
    rec=struct.Struct('<qqqqqIIIiiii'); assert rec.size==68
    heap=[];n=0;blocks=0
    with subprocess.Popen(['zstd','-qdc',str(src)],stdout=subprocess.PIPE) as proc:
        f=proc.stdout; h=f.read(8192);assert len(h)==8192
        magic,v,vs,header_n,header_b=struct.unpack_from('<QQqqq',h)
        assert magic==0x6c63700000000001 and v==vs==1 and struct.unpack_from('<Q',h,8184)[0]==magic and struct.unpack_from('<q',h,16+9*8)[0]==16
        while (b:=f.read(68)):
            ts,done,chat,parent,session_next,sess,user,nb,L,O,turn,typ=rec.unpack(b)
            assert ts<=done and nb>=0
            raw=f.read(nb*16);assert len(raw)==nb*16
            if len(heap)<N or (ts,n)<(-heap[0][0],-heap[0][1]):
                num=min(MAXPATH,max(0,(L-1)//512),nb//32)
                # Take IDs only; skip the packed next-access values entirely.
                ids=array('Q');ids.frombytes(raw[:num*32*16]); assert sys.byteorder=='little'
                edgebytes=ids[::2].tobytes()
                item=(-ts,-n,L,sess,user,chat,parent,edgebytes)
                if len(heap)<N:heapq.heappush(heap,item)
                else:heapq.heapreplace(heap,item)
            n+=1;blocks+=nb
        assert proc.wait()==0 and n==header_n==327548 and blocks==header_b
    selected=sorted(heap,key=lambda v:(-v[0],-v[1])); rows=[];last={};declared=0;seen={}
    for i,(negts,negidx,L,sess,user,chat,par,e) in enumerate(selected):
        # Requests from one session stay in input order. Also enforce any known
        # explicit parent (these sources are chains). Never impose a completion label.
        pa=last.get((user,sess),-1) if sess else -1
        if par>=0 and (user,par) in seen:
            explicit=seen[(user,par)];assert pa==explicit or (sess and selected[explicit][3]==sess and pa>=explicit);declared+=1
            if pa<0:pa=explicit
        if chat>=0:seen[(user,chat)]=i
        if sess:last[(user,sess)]=i
        rows.append((-negts+selected[0][0],L,pa,user,[e[j:j+256] for j in range(0,len(e),256)]))
    return intern(rows),dict(source_sha256=FI,full_requests=n,full_block_entries=blocks,explicit_links_in_panel=declared,selection='first 5000 by (arrival microseconds, source ordinal); sorted across entire file')
def panel(label):
    if label=='freeinference':rows,meta=fi()
    elif label.startswith('qwen'):rows,meta=qwen(label)
    else:rows,meta=moon(label)
    assert len(rows)==N and all(t>=0 and L>0 and p<i and len(path)<=min(MAXPATH,(L-1)//512) for i,(t,L,p,path) in enumerate(rows))
    assert all(a[0]<=b[0] for a,b in zip(rows,rows[1:]))
    out=R/'panels';out.mkdir(exist_ok=True)
    with (out/f'{label}.txt').open('x') as f:
        print(N,WARM,file=f)
        for t,L,p,path in rows:print(t,L,p,len(path),*path,file=f)
    meta.update(panel_sha256=sha(out/f'{label}.txt'),n=N,warm=WARM,measured=N-WARM)
    (out/f'{label}.json').write_text(json.dumps(meta,indent=2)+'\n')
if __name__=='__main__':
    for s in sys.argv[1:]:panel(s)
