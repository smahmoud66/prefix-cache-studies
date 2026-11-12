#!/usr/bin/env python3
"""Create source uploads and review PDFs; compile only what a reader extracts."""
import argparse,gzip,io,os,shutil,subprocess,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAMP=1794484800
PAPERS={'evaluator':('exact-prefix-cache-continuations-v3.1-arxiv',['main.tex']),
        'ordering':('request-ordering-waiting-limit-arxiv',['main.tex','heldout.pdf'])}
def build(out):
    out.mkdir(parents=True,exist_ok=True)
    for study,(name,files) in PAPERS.items():
        ar=out/(name+'.tar.gz')
        with ar.open('wb') as raw,gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as gz,tarfile.open(fileobj=gz,mode='w',format=tarfile.USTAR_FORMAT) as pack:
            for f in files:
                b=(ROOT/'papers'/study/f).read_bytes();i=tarfile.TarInfo(f)
                i.size=len(b);i.mode=0o644;i.mtime=STAMP;pack.addfile(i,io.BytesIO(b))
        with tempfile.TemporaryDirectory(prefix='arxiv-build-') as tmp:
            here=Path(tmp)
            with tarfile.open(ar) as pack:
                assert pack.getnames()==files
                for member in pack:
                    assert member.isfile() and member.name in files
                    (here/member.name).write_bytes(pack.extractfile(member).read())
            env={k:v for k,v in os.environ.items() if k not in ('TEXINPUTS','BIBINPUTS','BSTINPUTS','TEXMFHOME','TEXMFOUTPUT')}
            env.update(TEXMFHOME=str(here/'empty-texmf'),SOURCE_DATE_EPOCH=str(STAMP),FORCE_SOURCE_DATE='1',TZ='UTC')
            for _ in range(2):
                r=subprocess.run(['pdflatex','-no-shell-escape','-halt-on-error','-interaction=nonstopmode','main.tex'],cwd=here,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                if r.returncode: raise RuntimeError(r.stdout[-3500:])
            log=(here/'main.log').read_text()
            for m in ('undefined references','Rerun to get cross-references','Missing character:'):
                if m in log:raise RuntimeError(m)
            shutil.copyfile(here/'main.pdf',out/(name+'.pdf'))
            print(ar.name, 'and',name+'.pdf')
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--out',type=Path,required=True)
    build(a.parse_args().out.resolve())
