"""Readable appendix: all frozen cells, alongside the machine-readable summary."""
import json
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parent
LABELS={'FULL':'FULL = RANK-00','FOCUSED':'FOCUSED','R10':'RANK-10','R01':'RANK-01','R11':'RANK-11'}
METHODS=('FULL','FOCUSED','R10','R01','R11')


def render(s):
    lines=['# Matched measurements by interface, traffic and capacity','',
       'Each row uses all 28 previously evaluated Mooncake bins for that traffic type at that capacity. Three fresh native processes supply the three timing repetitions. Each process resets and applies common FCFS warm-up at each bin. The absolute interface returns the preferred representative and exact historical sum for every distinct immediately optimal exit. The decision interface returns the selected order and actual complete exit. The checks against archived dispatches and the validated score vectors occur outside the individual caller-wall interval. The two interfaces are summarized separately.',
       '',
       'Native CPU includes current request parsing and identity ingestion, candidate enumeration, history scoring and live index/state updates. Historical CPU is the scoring and ranking interval inside native CPU. Candidate CPU is the common candidate construction interval. Caller wall includes IPC, formatting, response and JSON decoding. Read timing totals below as seconds per workload pass averaged over the three repetitions, and mean and tail latencies as microseconds per cohort over the same three runs. Fractions and speed ratios describe these finite measurements.', '']
    for k,section in s['cells'].items():
        tr,cap,interface=k.split('_')
        rows=section['methods']
        d=rows['R11']
        lines.extend([f'## {tr} · {cap} blocks · {interface}', '',
                      f"{d['cohorts_per_rep']:,} measured cohorts per repetition. Every policy returned {d['prefill_per_rep']:,} prefill positions.",'',
                      '| Evaluator | Historical CPU, s / µs mean | Candidate CPU, µs mean | Native CPU, s / µs mean / p95 / p99 / max | Caller wall, s / µs mean / p95 / p99 / max | Native process peak RSS, MiB |',
                      '|---|---:|---:|---|---|---:|'])
        for m in METHODS:
            v=rows[m];times=v['timing']
            def stat(metric):
                z=times[metric]
                return f"{z['summed_s']/3:.4f} / "+' / '.join(f'{z[i]:.1f}' for i in ('mean_us','p95_us','p99_us','max_us'))
            hist=times['history_cpu']
            lines.append(f"| {LABELS[m]} | {hist['summed_s']/3:.4f} / {hist['mean_us']:.2f} | {times['generation_cpu']['mean_us']:.2f} | {stat('native_cpu')} | {stat('caller_wall')} | {v['peak_native_rss_bytes']/2**20:.2f} |")
        lines.extend(['','Counters below are totals for **one** measured pass and matched across all three repetitions. Direct successes count tests actually applied, including a once-scored common term when absolute scores are requested. Memo hits and lookups exclude direct answers. A full-witness continuation propagates complete states; the compact focused kernel records a projected-state update per replayed request. Index visits charge work to add or remove observed path occurrences, excluding the common warm-up here. Higher-level process totals include warm-up. Component bytes are capacities or high-water estimates; their maxima can occur on different cohorts.','',
                      '| Evaluator | Pair replays / request transitions | Cert. checks / successes / inspected slots | Memo lookups / hits | Common pairs elided | Rank-difference slots / key slots examined / key words | History index visits | Focused conversion slots / projected updates / projected visits | History / memo / focused scratch peak bytes |',
                      '|---|---|---|---|---:|---|---:|---|---|'])
        for m in METHODS:
            v=rows[m]; c=v['counters_per_rep'];p=v['max_components']
            def vals(values,keys):
                return ' / '.join(f'{values[z]:,}' for z in keys.split())
            stats=[LABELS[m],vals(c,'rollouts rollout_transitions'),vals(c,'cert_checks form_scores cert_examined_slots'),
                   vals(c,'memo_lookups memo_hits'),vals(c,'common_elided'),
                   vals(c,'diff_slots diff_key_visits memo_key_words'),vals(c,'index_visits'),
                   vals(c,'focused_initial_rank_scans focused_updates focused_entry_visits'),
                   vals(p,'history_bytes memo_bytes focused_scratch_bytes')]
            lines.append('| '+' | '.join(stats)+' |')
        lines.extend(['','Each comparison uses baseline minus RANK-11 in µs/cohort and baseline divided by RANK-11 for the time ratio. Larger ratios favor RANK-11. The factorial contrast is the overlap between the sum of standalone savings and their combined saving.', '',
                      '| Comparator | History CPU Δ / ratio | Native CPU Δ / ratio | Caller wall Δ / ratio |','|---|---:|---:|---:|'])
        for m in ('FOCUSED','R01','R10','FULL'):
            b=section['paired'][m]; txt=[]
            for metric in ('history_cpu','native_cpu','caller_wall'):
                a=b[metric]
                txt.append(f"{a['paired_mean_saved_us']:+.2f} / {a['baseline_over_R11']:.3f}×")
            lines.append('| '+' | '.join([LABELS[m]]+txt)+' |')
        lines.extend(['','FOCUSED minus RANK-11, paired within each fresh-process repetition. Differences below are milliseconds over the complete measured set of cohorts. Ratios compare FOCUSED to RANK-11.', '',
                      '| Repetition | History CPU Δ ms / ratio | Native CPU Δ ms / ratio | Caller wall Δ ms / ratio |','|---|---:|---:|---:|'])
        primary=section['paired']['FOCUSED']
        for i in range(3):
            txt=[]
            for metric in ('history_cpu','native_cpu','caller_wall'):
                pair=primary[metric]['paired_repetitions'][i]
                txt.append(f"{pair['saved_s']*1000:+.3f} / {pair['ratio']:.3f}×")
            lines.append('| '+' | '.join([str(i+1)]+txt)+' |')
        factor=section['factorial_interaction']
        lines.extend(['',f"Factorial contrast T00 − T10 − T01 + T11 in µs/cohort was {factor['history_cpu']['mean_us']:+.2f} historical CPU, {factor['native_cpu']['mean_us']:+.2f} native CPU and {factor['caller_wall']['mean_us']:+.2f} caller wall.",''])
    lines.extend(['Source data, separate repetition totals and all component high-water marks are in [summary.json](summary.json). The [cell receipts](timing_receipts.jsonl) include whole-process CPU, peak resident memory, elapsed time and raw-record hashes. The [frozen schedule and source digests](freeze.json) and [verification receipt](verification_receipt.json) identify the exact comparisons.'])
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    (ROOT/'measurement_tables.md').write_text(render(json.loads((ROOT/'summary.json').read_text())))
