"""Generate the numerical appendix of the external validation report from the verified summary."""
import json
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parent
NAMES=['FCFS','K','IMM','OPT','RANK','RAND1729','RAND314159','RAND271828']


def tables(s):
    lines=[]
    put=lines.append
    put('### All policy trajectories')
    put('')
    put('Complete measured-episode prefill, in positions. Warm-up work is shared across policies within each row. Each episode contains 20,000 measured requests.')
    put('')
    put('| Traffic | Tokens/block × cache blocks | Warm-up | '+' | '.join(NAMES)+' |')
    put('|---|---|'+'---:|'*9)
    for k,t in s['cells'].items():
        w,b,c=k.split('_')
        put('| '+' | '.join([w,b+' × '+c,f"{t['OPT']['warm_prefill']:,}"]+[f"{t[m]['work']:,}" for m in NAMES])+' |')
    put('')
    put('### Costs and conditional break-even against each control')
    put('')
    put('ΔP is control work minus optimized work. ΔT is optimized minus control wall time in the local caller, averaged over the two full measured repetitions. A positive ΔP implies the serialized break-even β = ΔT/ΔP in microseconds per saved position. A negative ratio would indicate a local time advantage even at zero marginal prefill cost. A dash means no positive prefill saving. Each timing cell gives mean / p95 / p99 / maximum per cohort in µs, pooled over the two repetitions. RSS is the larger per-process high-water mark. Process CPU/wall include input parsing, warm-up and diagnostic output. The underlying summary preserves separate repetitions.')
    put('')
    for k,t in s['cells'].items():
        put('<details><summary>'+k.replace('_',' · ')+' — timing, work contrasts and memory</summary>')
        put('')
        put('| Policy | ΔP | ΔT (ms) | β (µs/position) | CPU (µs) | Wall (µs) | Process CPU / wall (s) | RSS (MiB) |')
        put('|---|---:|---:|---:|---|---|---:|---:|')
        for m in NAMES:
            a=t[m]; contrast=s['comparisons'][k][m]; ratio=contrast['break_even_ns_per_position']
            series=lambda label: ' / '.join(f"{a[label][stat]/1000:.1f}" for stat in ['mean','p95','p99','max'])
            beta='—' if ratio is None else f'{ratio/1000:.4f}'
            times=a['timing']
            vals=[m,f"{contrast['savings']:+,d}",f"{contrast['extra_decision_wall_ns']/1e6:+.2f}",beta,
                  series('cpu_ns'),series('wall_ns'),
                  f"{mean(i['process_cpu_s'] for i in times):.3f} / {mean(i['process_wall_s'] for i in times):.3f}",
                  f"{max(i['rss'] for i in times)/2**20:.2f}"]
            put('| '+' | '.join(vals)+' |')
        put('')
        put('</details>')
        put('')
    put('### Mechanism on the optimized trajectory')
    put('')
    put('A tied cohort has multiple immediately optimal orders. Distinct exits count full MRU states. Changes compare OPT with its deterministic immediate incumbent **from that same entry state**. Window effects compare the separate continuous OPT and IMM trajectories, so a later window can inherit earlier choices. The historical index grows with the IDs seen over the episode. Allocated bytes include spare vector capacity.')
    put('')
    put('| Traffic / block / slots | Tied cohorts / multiple exits | Distinct exits, sum / max | Changed orders (residency / recency only) | Replays / direct scores / memo hits | Index slots after warm → end (active at end) | Index / full history / pair memo peak (KiB) | ΔP by chronological window |')
    put('|---|---:|---:|---:|---:|---|---|---|')
    for k,t in s['cells'].items():
        a=t['OPT']; q=a['counters']; p=a['peaks']; h=a['change_type']
        vals=[k.replace('_',' / '),f"{q.get('multiple_orders',0):,} / {q.get('multiple_exits',0):,}",
              f"{q['exit_count']:,} / {max(map(int,a['exit_hist']))}",
              f"{q['changed']:,} ({h.get('resident',0):,} / {h.get('recency',0):,})",
              f"{q['rollouts']:,} / {q['direct']:,} / {q['memo_hits']:,}",
              f"{a['ids_after_warm']:,} → {p['index_slots']:,} ({a['active_final']:,})",
              ' / '.join(f'{p[x]/1024:.1f}' for x in ['index_bytes','history_bytes','memo_bytes']),
              ' / '.join(f'{x:+,d}' for x in s['comparisons'][k]['IMM']['window_savings'])]
        put('| '+' | '.join(vals)+' |')
    put('')
    put('Per-cohort orders, displacement, eligibility counts, and per-repetition resource records are available in the [raw replay outputs](runs/) and [numerical summary](summary.json). Counts describe the observed mechanism. They cannot identify how much of the episode effect was caused by changes in residency versus recency.')
    return '\n'.join(lines)
