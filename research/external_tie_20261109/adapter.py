"""Build trace-relative timestamp, input length, reusable cumulative prefix-node IDs."""
import argparse
import hashlib
import itertools
import json
import resource
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REV = "5f7439c51ec248a0c585f7d90a41a6f57773b912"
HASH = {"A": "07cedc9ed8aff301994ac68ed4aede8123b7603673575eeba9dd677de663db17",
        "B": "68e3f98e2d601d60d0abf4b89bc8a3654372abab7b1cde6373a13d0054379d59"}
KEYS = {"chat_id", "parent_chat_id", "timestamp", "input_length", "output_length",
        "type", "turn", "hash_ids"}
CAP_TOKENS = 65536


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Lineages:
    """One per file. Only links known when this row arrives can justify sharing."""
    def __init__(self):
        self.by_chat = {}
        self.counts = Counter()

    def get(self, chat, parent):
        if chat in self.by_chat:
            self.counts["repeated_chat"] += 1
            known = self.by_chat[chat]
            if parent != -1 and parent in self.by_chat and self.by_chat[parent] != known:
                raise ValueError("conflicting repeated chat lineage")
            return known
        if parent == -1:
            self.counts["root"] += 1
            lineage = chat
        elif parent in self.by_chat:
            self.counts["prior_parent"] += 1
            lineage = self.by_chat[parent]
        else:
            self.counts["missing_parent"] += 1
            lineage = chat
        if chat < 0:
            raise ValueError("unexpected negative chat ID")
        self.by_chat[chat] = lineage
        return lineage


class Prefixes:
    """IDs are interned by full parent/edge equality, independent per file and block size."""
    def __init__(self, block):
        self.block = block
        self.ids = {}

    def project(self, lineage, length, blocks):
        if length <= 0 or len(blocks) != (length + 15) // 16:
            raise ValueError("uncertified source block count")
        stride = self.block // 16
        q = min((length - 1) // self.block, CAP_TOKENS // self.block)
        parent = -(lineage + 1)
        nodes = []
        for lo in range(0, q * stride, stride):
            edge = blocks[lo] if stride == 1 else tuple(blocks[lo:lo + stride])
            key = (parent, edge)
            node = self.ids.get(key)
            if node is None:
                node = len(self.ids) + 1
                self.ids[key] = node
            nodes.append(node)
            parent = node
        return nodes


def fixtures():
    lin = Lineages()
    assert [lin.get(a, b) for a, b in [(0,-1),(1,0),(2,-1),(3,144),(144,-1),(1,0)]] == [0,0,2,3,144,0]
    for size in (16, 512):
        stride = size // 16
        code = Prefixes(size)
        blocks = [3] * stride + [7] * stride + [2]
        full = code.project(0, 2 * size + 1, blocks)
        repeat = code.project(0, 2 * size + 1, blocks)
        other = code.project(0, 2 * size + 1, [4] * stride + blocks[stride:])
        shorter = code.project(0, size + 1, blocks[:stride+1])
        assert len(full) == 2 and full == repeat and shorter == full[:1]
        assert full[1] != other[1] and full[0] != other[0]
        assert code.project(0, 2 * size, blocks[:-1]) == full[:1]
        assert code.project(0, 1, [3]) == [] and code.project(0, size, blocks[:stride]) == []
        assert code.project(2, 2 * size + 1, blocks) != full
        assert len(code.project(0, 65553, [3] * 4098)) == 65536 // size
    print("adapter fixtures passed")


def build(label, n):
    source = ROOT / "source" / f"qwen_trace{label}_blksz_16.jsonl"
    if digest(source) != HASH[label]:
        raise ValueError("source SHA mismatch")
    dest = ROOT / "panel"
    dest.mkdir(exist_ok=True)
    cpu, wall = time.process_time(), time.perf_counter()
    output = {s: dest / f"{label}_{s}.rows" for s in (16, 512)}
    lineage = Lineages()
    prefixes = {s: Prefixes(s) for s in output}
    last = -1
    count = 0
    modalities = Counter()
    with output[16].open("x") as raw, output[512].open("x") as coarse, source.open() as src:
        for line in itertools.islice(src, n):
            item = json.loads(line)
            if set(item) != KEYS or item["timestamp"] < last:
                raise ValueError("schema or chronology mismatch")
            last = item["timestamp"]
            group = lineage.get(item["chat_id"], item["parent_chat_id"])
            modalities[item["type"]] += 1
            for size, stream in ((16, raw), (512, coarse)):
                nodes = prefixes[size].project(group, item["input_length"], item["hash_ids"])
                print(last, item["input_length"], *nodes, file=stream)
            count += 1
    if n != count:
        raise ValueError("unexpected end of file")
    receipt = dict(revision=REV, raw_sha256=HASH[label], rows=count, last_seconds=last,
                   lineages=lineage.counts, modalities=modalities, outputs={s:digest(f) for s,f in output.items()},
                   derived_nodes={s:len(p.ids) for s,p in prefixes.items()},
                   cpu_seconds=time.process_time()-cpu, wall_seconds=time.perf_counter()-wall,
                   peak_rss_platform_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (dest / f"{label}_adapter_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("fixture", "A", "B"))
    parser.add_argument("--rows", type=int, default=21000)
    args = parser.parse_args()
    if args.mode == "fixture":
        fixtures()
    else:
        build(args.mode, args.rows)
