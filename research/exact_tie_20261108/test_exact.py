"""Independent equivalence checks on finite synthetic tries (no trace input)."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from itertools import permutations, product
import json
from pathlib import Path
import random
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'exit_cache_20261108'
BASE = HERE.parent / 'commitment_20261108'
sys.path.insert(0, str(BASE))
import study as frozen


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_equal(actual, expected, context):
    if actual != expected:
        raise AssertionError(f'{context}\nexpected={expected!r}\nactual={actual!r}')


@dataclass(frozen=True)
class Case:
    family: str
    cap: int
    entry: tuple
    current: tuple
    history: tuple


def paths_and_tree():
    # Deliberately include non-monotone IDs and a chain with 128 cacheable blocks.
    roots = ((19,), (2,), (41,), (9,), (6,))
    short = roots + ((19, 7), (19, 3), (19, 7, 10), (2, 8), (2, 8, 15), (2, 14))
    chain = tuple(range(400, 528))
    paths = ((),) + short + (chain, chain[:-1] + (700,), chain[:32], chain[:31] + (701,))
    tree = frozen.Trie()
    parents = {v: p[j-1] if j else 0 for p in paths for j, v in enumerate(p)}
    depth = {v: j+1 for p in paths for j, v in enumerate(p)}
    tree.parent = parents
    tree.depth = depth
    return paths, tree


PATHS, TREE = paths_and_tree()


@lru_cache(maxsize=65536)
def serve(state, path, cap):
    """Reconstruct distinct old timestamps, assign the whole path the next stamp,
    and repeatedly find the oldest unprotected leaf. No native tuple update."""
    present = {node: -rank-1 for rank, node in enumerate(state)}
    hits = 0
    for node in path:
        if node not in present:
            break
        hits += 1
    present.update(dict.fromkeys(path, 0))
    while len(present) > cap:
        internal = {TREE.parent[node] for node in present}
        victim = min((v for v in present if v not in internal and v not in path),
                     key=lambda v: (present[v], -TREE.depth[v], v))
        del present[victim]
    ordered = tuple(sorted(present, key=lambda v: (-present[v], TREE.depth[v], -v)))
    return len(path)-hits, ordered


def play(entry, group, cap, order):
    cost = 0
    for i in order:
        delta, entry = serve(entry, group[i], cap)
        cost += delta
    return cost, entry


@lru_cache(maxsize=32768)
def klpm(entry, group, cap):
    order = []
    remaining = list(range(len(group)))
    cost = 0
    while remaining:
        if len(order) % 2 == 0:
            i = remaining[0]
        else:
            # Count consecutive resident nodes, resolving equal counts by arrival.
            def matched(i):
                for k, v in enumerate(group[i]):
                    if v not in entry:
                        return k
                return len(group[i])
            i = max(remaining, key=matched)
        delta, entry = serve(entry, group[i], cap)
        order.append(i)
        remaining.remove(i)
        cost += delta
    return tuple(order), cost, entry


@lru_cache(maxsize=16384)
def candidate_info(entry, group, cap):
    reqs = [frozen.Request(i, i, 512*len(p)+1, p) for i, p in enumerate(group)]
    cohort = frozen.Cohort(reqs, TREE, cap, False, 0)
    incumbent_cost, incumbent, final = cohort.schedule({v: -i-1 for i, v in enumerate(entry)}, 'search_LRU')
    inc_exit = tuple(sorted(final, key=lambda v: (-final[v], TREE.depth[v], -v)))
    legal = [(p, *play(entry, group, cap, p)) for p in permutations(range(len(group)))]
    min_cost = min(c for _, c, _ in legal)
    check_equal(incumbent_cost, min_cost, 'frozen immediate cost versus exhaustive leaf oracle')
    check_equal(play(entry, group, cap, incumbent), (min_cost, inc_exit), 'frozen immediate exit')
    eligible = [(p, s) for p, c, s in legal if c == min_cost]
    return incumbent, min_cost, inc_exit, eligible


def future_sum(entry, past, cap):
    # The last 16 completed cohorts enter oldest-to-newest. Drop its oldest
    # leftover singleton. Each fresh pair independently restarts at entry.
    window = past[-16:]
    total = 0
    for left in range(len(window) % 2, len(window), 2):
        _, first, after = klpm(entry, window[left], cap)
        _, second, _ = klpm(after, window[left+1], cap)
        total += first+second
    return total


def group_wire(group):
    return ' '.join(str(v) for row in ((len(group),), *((len(p), *p) for p in group)) for v in row)


def message(case, method, inc, absolute):
    status = f'{case.cap} {len(case.entry)} ' + ' '.join(map(str, case.entry))
    head = 'D TIE' if method == 'old' else f'D {method} {int(absolute)}'
    middle = f' I {" ".join(map(str, inc))}' if method == 'old' else ''
    return (f'{head} {status} Q {group_wire(case.current)}{middle} H {len(case.history)} '
            + ' '.join(map(group_wire, case.history)))


@contextmanager
def engine(args):
    with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          text=True, encoding='ascii', bufsize=1) as proc:
        def query(line):
            proc.stdin.write(line+'\n')
            proc.stdin.flush()
            answer = proc.stdout.readline()
            if not answer:
                raise RuntimeError(f'{args} exited unexpectedly on {line}')
            obj = json.loads(answer)
            if 'error' in obj:
                raise RuntimeError(f'{line}: {obj}')
            return obj
        try:
            yield query
        finally:
            proc.stdin.close()
            proc.wait(timeout=4)
            if proc.returncode:
                raise RuntimeError(f'{args} exited with {proc.returncode}')


def reachable(alphabet, cap):
    seen = {()}
    pending = deque([()])
    while pending:
        state = pending.popleft()
        for p in alphabet:
            _, after = serve(state, p, cap)
            if after not in seen:
                seen.add(after)
                pending.append(after)
    return sorted(seen)


def small_cases():
    # All reachable states in each small trie, all ordered current tuples
    # of size 1..2 and every history of 0..2 singleton cohorts on that alphabet.
    for cap in (1, 2):
        alphabet = ((), (19,), (2,)) if cap == 1 else ((), (19,), (19, 7), (2,))
        past = [hist for n in range(3) for hist in product(((p,) for p in alphabet), repeat=n)]
        for state in reachable(alphabet, cap):
            for n in (1, 2):
                for current in product(alphabet, repeat=n):
                    for hist in past:
                        yield Case(f'exhaustive_C{cap}', cap, state, current, hist)


def targeted_cases():
    a, b, c = (19,), (2,), (41,)
    # Empty, partial, odd, maximal history; duplicates and useful nonincumbent ties.
    yield Case('duplicate_lex', 1, (), (a,b,a), ((a,), (a,)))
    yield Case('mru', 2, (), (a,b), ((c,), (a,)))
    yield Case('adaptive', 2, (), (a,b), ((c,a,b), (c,)))
    yield Case('prefix_pressure', 3, (19,7,10), ((19,7), (19,3), (2,8), ()),
               (((2,8), (19,7), (19,), (19,3)), ((19,7,10), (), (2,8))))
    # Frozen parent fixtures. In turn the first attaining portfolio trial is
    # FCFS, k-LPM, LPM, cLPM, or DFS. The last case strictly beats all five.
    for label,cap,entry,g in (
        ('FCFS',3,(6,19,9),((19,3),(2,),(2,14),(19,7,10))),
        ('kLPM',4,(41,2,8,15),((19,),(19,7),(2,8),(19,7,10))),
        ('LPM',3,(2,8,19),((19,7),(),(19,3),(2,8))),
        ('cLPM',4,(19,2,41,3),((19,7,10),(19,3),(2,8),(2,))),
        ('DFS',3,(19,2,14),((19,),(19,3),(19,7),(2,8))),
        ('strict_search',4,(19,7,41,2),((2,8,15),(),(2,),(19,7,10))),
    ):
        yield Case('incumbent_'+label,cap,entry,g,())
    history = tuple(((b if j % 3 == 0 else a,), (a if j % 3 == 0 else b,))[j % 2]
                    for j in range(16))
    for n in range(17):
        yield Case('window', 1, (2,), (a,b,a,b), history[:n])
    for cap in (32,128):
        p, q = PATHS[-4][:cap], PATHS[-3][:cap]
        group = (p, PATHS[-1], q, (19,7,10))
        yield Case('long_path', cap, p, group, (tuple(reversed(group)), group)*8)
    # Larger current/cohort widths, tied requests and past cohorts where k-LPM
    # can adapt. Fixed seed; generate reachable caches from actual services.
    rng = random.Random(20261108)
    for j in range(270):
        cap = (1,2,3,4,6)[j%5]
        alphabet = list(dict.fromkeys(p[:cap] for p in PATHS[:-4]))
        history = tuple(tuple(rng.choice(alphabet) for _ in range(rng.randrange(1,5)))
                        for _ in range(j % 17))
        entry = ()
        for g in history:  # jointly realized history and entry under FCFS warm-up
            _, entry = play(entry, g, cap, range(len(g)))
        current = tuple(rng.choice(alphabet) for _ in range(1+j%4))
        yield Case('seeded_joint', cap, entry, current, history)


def check_projection():
    counts = Counter()
    alphabet = ((), (19,), (2,), (41,), (19,7), (19,3))
    groups = {n: tuple(product(alphabet, repeat=n)) for n in (1,2,3)}
    for cap in (2,3):
        states = reachable(alphabet,cap)
        for n1,n2 in ((1,1),(1,2),(2,1),(2,2),(3,1)):
            for first,second in product(groups[n1],groups[n2]):
                tracked = {v for g in (first,second) for p in g for v in p}
                class_scores = {}
                for s in states:
                    pair_score = future_sum(s,(first,second),cap)
                    key = tuple((i,v) for i,v in enumerate(s,1) if v in tracked)
                    if key in class_scores:
                        check_equal(pair_score,class_scores[key],f'projection collision: {(s,first,second)}')
                        counts['reused_key'] += 1
                    class_scores[key] = pair_score
                    gaps = key[-1][0]-len(key) if key else 0
                    if len(tracked)+gaps <= cap:
                        check_equal(pair_score,len(tracked)-len(key),f'direct score: {(s,first,second)}')
                        counts['direct_certificate'] += 1
                    counts['state_pair_inputs'] += 1
    return counts


def check_live(native):
    """Exercise the same incremental R/W/G interface as the frozen timing."""
    measured = 0
    for mode in ('K','IMM','REF','OPT'):
        for absolute in ((False,True) if mode in ('REF','OPT') else (False,)):
            for cap,warm_count in ((2,0),(3,19)):
                native(f'R {mode} {int(absolute)} {cap}')
                rng = random.Random(435+cap)
                alphabet = tuple(dict.fromkeys(p[:cap] for p in PATHS[:-4]))
                state = ()
                history = deque(maxlen=16)
                for j in range(55):
                    q = tuple(rng.choice(alphabet) for _ in range(1+j%4))
                    if j < warm_count:
                        row = native('W '+group_wire(q))
                        misses,state = play(state,q,cap,range(len(q)))
                        check_equal(row['immediate_blocks'],misses,'FCFS warm start')
                    else:
                        row = native('G '+group_wire(q))
                        if mode == 'K':
                            order,misses,state = klpm(state,q,cap)
                        else:
                            inc,misses,inc_exit,eligible = candidate_info(state,q,cap)
                            order,state = inc,inc_exit
                            if mode in ('REF','OPT'):
                                past = tuple(history)
                                value = {s:future_sum(s,past,cap) for _,s in eligible}
                                order,state = min(eligible,key=lambda a: (value[a[1]],a[0]!=inc,a[0]))
                                den = max(1,len(past)//2)
                                check_equal((tuple(row['incumbent']),row['den']),(inc,den),'live incumbent')
                                if absolute:
                                    check_equal((row['future_blocks'],row['objective_num']),
                                                (value[state],misses*den+value[state]),'live objective')
                        check_equal((tuple(row['order']),row['immediate_blocks'],tuple(row['selected_exit'])),
                                    (order,misses,state),f'live {mode} C{cap} group {j}')
                        measured += 1
                    history.append(q)
    return measured


def check_case(case, old, native, seen):
    q, state, hist, cap = case.current, case.entry, case.history, case.cap
    incumbent, min_cost, inc_exit, eligible = candidate_info(state, q, cap)
    future = {exit: future_sum(exit, hist, cap) for _, exit in eligible}
    best = min(future.values())
    winning = [(p,s) for p,s in eligible if future[s] == best]
    order, exit = min(winning, key=lambda choice: (choice[0] != incumbent, choice[0]))
    den = max(1, min(len(hist),16)//2)
    if case.family == 'duplicate_lex':
        check_equal((order, len(winning)), ((1,0,2),2), 'fixed lexicographic counterexample')
    if case.family == 'mru':
        check_equal((incumbent, order, best, future[inc_exit]), ((0,1),(1,0),1,2),
                    'fixed equal-residency counterexample')
    if case.family == 'adaptive':
        check_equal((future[(19,2)], future[(2,19)]), (3,3), 'k-LPM adaptive continuation')
        check_equal([klpm(s,hist[0],cap)[0] for s in ((19,2),(2,19))],
                    [(0,1,2),(0,2,1)], 'adaptive history service orders')
    fixed_incumbents = {'FCFS': (0,1,2,3), 'kLPM': (0,2,1,3), 'LPM': (3,0,2,1),
                        'cLPM': (1,2,0,3), 'DFS': (3,0,1,2), 'strict_search': (1,2,3,0)}
    if case.family.startswith('incumbent_'):
        check_equal(incumbent,fixed_incumbents[case.family.removeprefix('incumbent_')],case.family)
    if case.family.startswith('exhaustive'):
        cold = ()
        for g in hist:
            _, cold = play(cold, g, cap, range(len(g)))
        if cold == state:
            seen['exhaustive_joint_from_cold'] += 1
    seen[case.family] += 1
    seen['multiple_immediate_optima'] += len(eligible)>1
    seen['nonlex_inc_retained'] += order == incumbent and order != min(p for p,_ in winning)
    seen['noninc_lex_ties'] += order != incumbent and len(winning)>1
    seen['differing_sets'] += len({frozenset(s) for s in future})>1
    seen['equal_set_differing_mru'] += len(future)>len({frozenset(s) for s in future})
    seen['same_full_exit_distinct_actions'] += len(future)<len(eligible)
    seen['incumbent_strictly_worse'] += future[inc_exit]>best
    seen['cases'] += 1
    expected = (order, incumbent, exit, min_cost, den)
    old_row = old(message(case,'old',incumbent,False))
    def core(row):
        return tuple(row['order']),tuple(row['incumbent']),tuple(row['selected_exit']),row['immediate_blocks'],row['den']
    check_equal(core(old_row), expected, f'frozen tie order/exit/work/pair count: {case}')
    check_equal(old_row['adv_num_blocks'], future[inc_exit]-best, f'frozen advantage: {case}')
    if native is None:
        return
    for method in ('IMM','K','REF','OPT'):
        modes = (False,True) if method in ('REF','OPT') else (False,)
        for absolute in modes:
            row = native(message(case,method,incumbent,absolute))
            if method == 'IMM':
                got = (tuple(row['order']),tuple(row['selected_exit']),row['immediate_blocks'])
                check_equal(got, (incumbent,inc_exit,min_cost), f'{method}: {case}')
            elif method == 'K':
                got = (tuple(row['order']),row['immediate_blocks'],tuple(row['selected_exit']))
                check_equal(got, klpm(state,q,cap), f'{method}: {case}')
            else:
                check_equal(core(row), expected, f'{method} absolute={absolute}: {case}')
                if absolute:
                    check_equal((row['future_blocks'],row['objective_num']), (best, min_cost*den+best),
                                f'{method} absolute integer objective: {case}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-only', action='store_true',
                        help='verify witnesses and independent oracle before the new binary exists')
    args = parser.parse_args()
    started = time.perf_counter()
    frozen_hashes = json.loads((OLD/'freeze.json').read_text())['files']
    for name in ('runner.py','engine','engine.cpp'):
        check_equal(digest(OLD/name), frozen_hashes[name], 'frozen source hash '+name)
    check_equal(digest(BASE/'study.py'), json.loads((OLD/'online_receipt.json').read_text())['parent_study_sha256'],
                'parent simulator hash')
    counts = Counter()
    projections = check_projection()
    with ExitStack() as stack:
        old = stack.enter_context(engine([str(OLD/'engine'),'--online']))
        native = None if args.frozen_only else stack.enter_context(engine([str(HERE/'evaluator')]))
        for generate in (small_cases,targeted_cases):
            for case in generate():
                check_case(case,old,native,counts)
        live = check_live(native) if native is not None else 0
    for coverage in ('nonlex_inc_retained','noninc_lex_ties','differing_sets','equal_set_differing_mru',
                     'incumbent_strictly_worse','exhaustive_joint_from_cold','same_full_exit_distinct_actions'):
        if not counts[coverage]:
            raise AssertionError('uncovered '+coverage)
    self_time = resource.getrusage(resource.RUSAGE_SELF)
    child_time = resource.getrusage(resource.RUSAGE_CHILDREN)
    print(json.dumps(dict(status='PASS', frozen_only=args.frozen_only, counts=counts, projection=projections,
                          incremental_decisions=live,
                          python_cpu_s=self_time.ru_utime+self_time.ru_stime,
                          child_cpu_s=child_time.ru_utime+child_time.ru_stime,
                          wall_s=time.perf_counter()-started,
                          evaluator_sha256=None if args.frozen_only else digest(HERE/'evaluator')), sort_keys=True))


if __name__ == '__main__':
    main()
