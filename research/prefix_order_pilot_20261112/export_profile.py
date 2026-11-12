"""Use DuckDB with the two pinned public parquet files; latency is milliseconds."""
import json
from pathlib import Path
import duckdb
R=Path(__file__).resolve().parent/'sources'; c=duckdb.connect()
a=c.execute(f"""select isl,latency from '{R/'attention.parquet'}' where batch_size=1 and head_dim=128 and num_heads=32 and num_key_value_heads=8 and attn_dtype='bfloat16' and kv_cache_dtype='bfloat16' and step=0 and window_size=0 and kernel_source='fa3' order by isl""").fetchall()
g={(m,n,k):l for m,n,k,l in c.execute(f"""select m,n,k,latency from '{R/'gemm.parquet'}' where gemm_dtype='bfloat16' and kernel_source='sglang_torch_linear'""").fetchall()}
rows=[]
for m,at in a:
    shapes=[(6144,4096),(4096,4096),(12288,4096),(12288,4096),(4096,12288)]
    if not all((m,n,k) in g for n,k in shapes): continue
    ms=36*(at+sum(g[(m,n,k)] for n,k in shapes))
    rows.append(dict(tokens=m,attention_ms_layer=at,gemm_ms_layer=[g[(m,n,k)] for n,k in shapes],ms=ms))
assert len(rows)>=10
(R/'profile_points.json').write_text(json.dumps(rows,indent=2)+'\n')
