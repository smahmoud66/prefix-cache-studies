"""Verify release objects and inventory source fields only; no policy simulation."""
import json
from collections import Counter
from pathlib import Path
from adapter import ROOT, HASH, KEYS, REV, digest

def describe(label):
    source = ROOT / "source" / f"qwen_trace{label}_blksz_16.jsonl"
    if digest(source) != HASH[label]:
        raise ValueError("LFS hash mismatch")
    n, tokens, aligned, negative_dt = 0, 0, 0, 0
    first, last = None, None
    shortest, longest = 10**20, 0
    boundaries = {}
    with source.open() as stream:
        for line in stream:
            item = json.loads(line)
            n += 1
            if set(item) != KEYS:
                raise ValueError("undocumented schema")
            t, length = item["timestamp"], item["input_length"]
            if length <= 0 or len(item["hash_ids"]) != (length + 15) // 16:
                raise ValueError("undocumented hash count")
            if last is not None and t < last:
                negative_dt += 1
            first = t if first is None else first
            last = t
            tokens += length
            aligned += length % 16 == 0
            shortest, longest = min(shortest,length), max(longest,length)
            if n in (1,1000,1001,21000):
                boundaries[n] = t
    return dict(sha256=HASH[label], bytes=source.stat().st_size, rows=n, first=first,
                last=last, total_input_positions=tokens, min_input_length=shortest,
                max_input_length=longest, aligned_16=aligned, partial_final_16=n-aligned,
                chronology_inversions=negative_dt, panel_row_timestamps_seconds=boundaries)

if __name__ == "__main__":
    print(json.dumps(dict(repository="alibaba-edu/qwen-bailian-usagetraces-anon", revision=REV,
                          fields=sorted(KEYS), files={label:describe(label) for label in HASH}),indent=2))
