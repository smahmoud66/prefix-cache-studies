"""Build causal input frames and an offline wait ledger. Does not invoke any policy."""
import hashlib
import json
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PANEL = ROOT / 'panel'


def groups(rows, end=None):
    pending = []
    for row in rows:
        if pending and row[0] > pending[0][0] + 1000:
            yield pending, pending[0][0] + 1000
            pending = []
        pending.append(row)
        if len(pending) == 4:
            yield pending, row[0]
            pending = []
    if pending:
        deadline = pending[0][0] + 1000
        yield pending, min(deadline, end) if end is not None else deadline


def read_rows(path):
    with path.open() as fh:
        for row in fh:
            ts, raw_length, *ids = row.split()
            ms = Decimal(ts) * 1000
            assert ms == int(ms)
            yield int(ms), int(raw_length), ids


def build(workload, block):
    rows = list(read_rows(PANEL / f'{workload}_{block}.rows'))
    assert len(rows) == 21000
    assert all(r[0] <= s[0] for r,s in zip(rows,rows[1:]))
    info = []
    wire = PANEL / f'{workload}_{block}.episode'
    with wire.open('x') as out:
        start = 1
        for phase, grouped in [('W', groups(rows[:1000], rows[1000][0])), ('G', groups(rows[1000:]))]:
            for cohort, flush in grouped:
                fields = [phase, str(len(cohort))]
                for _, tokens, path in cohort:
                    assert len(path) == min(65536 // block, (tokens - 1) // block)
                    fields.extend([str(tokens),str(len(path)),*path])
                print(' '.join(fields), file=out)
                info.append(dict(phase=phase, first_row=start, arrivals_ms=[r[0] for r in cohort],
                                 wait_ms=[flush-r[0] for r in cohort], flush_ms=flush,
                                 tokens=sum(r[1] for r in cohort)))
                start += len(cohort)
    return info


if __name__ == '__main__':
    start = time.process_time()
    counts = {}
    for workload in ['A','B']:
        fine = build(workload,16)
        coarse = build(workload,512)
        assert fine == coarse
        counts[workload] = {phase: sum(row['phase'] == phase for row in fine) for phase in ['W','G']}
        (PANEL / f'{workload}_gate.json').write_text(json.dumps(coarse,separators=(',',':')))
    (ROOT / 'group_receipt.json').write_text(json.dumps(dict(counts=counts,cpu_s=time.process_time()-start),indent=2))
