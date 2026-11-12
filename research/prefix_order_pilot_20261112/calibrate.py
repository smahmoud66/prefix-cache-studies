"""Export and fit public SGLang H100 component timings; no workload inputs."""
import json, sys, math
from pathlib import Path
import numpy as np
from scipy.optimize import nnls
ROOT=Path(__file__).resolve().parent
def fit():
    rows=json.loads((ROOT/'sources/profile_points.json').read_text())
    train=[z for z in rows if z['tokens'] not in (128,1024,4096,12288)]
    def x(z): return [1,z['tokens']/1024,(z['tokens']/1024)**2]
    X=np.array([x(z) for z in train]); y=np.array([z['ms'] for z in train])
    coeff=nnls(X/y[:,None], np.ones(len(y)))[0]
    for r in rows:
        r['fit_ms']=float(np.dot(x(r),coeff));r['relative_error']=(r['fit_ms']/r['ms']-1)
    hold=[abs(r['relative_error']) for r in rows if r not in train]
    o={'a_ms':float(coeff[0]),'b_ms_per_token':float(coeff[1]/1024),'c_ms_per_token2':float(coeff[2]/1024**2),
       'model':'Qwen3-8B BF16, one H100 80GB; sum of five GEMMs and one full-context attention operation per layer, 36 layers. Component model, not server TTFT.',
       'heldout_cold_lengths':[r['tokens'] for r in rows if r not in train],'heldout_max_abs_relative_error':max(hold),'points':rows}
    (ROOT/'calibration.json').write_text(json.dumps(o,indent=2)+'\n')
if __name__=='__main__':fit()
