// Build against the frozen engine: the State, transition and continuation used
// by every policy here are literally the same as its audited implementation.
#define main frozen_exit_cache_entrypoint
#include "../exit_cache_20261108/engine.cpp"
#undef main
#include <cstring>
#include <deque>
#include <memory>

namespace matched {
enum class Method { K, Immediate, Reference, Optimized };

Method method_named(const std::string& name) {
    if (name == "K") return Method::K;
    if (name == "IMM") return Method::Immediate;
    if (name == "REF") return Method::Reference;
    if (name == "OPT") return Method::Optimized;
    throw std::runtime_error("unknown method");
}

bool historical(Method m) { return m == Method::Reference || m == Method::Optimized; }

struct Counters {
    int current = 0, future = 0, rollouts = 0;
    int candidate_states = 0, eligible_orders = 0, visited_actions = 0;
    int common_pairs = 0, form_scores = 0, memo_hits = 0, current_cache_entries = 0;
    int memo_entries = 0;
    size_t memo_bytes = 0, current_cache_bytes = 0;
};

struct HistoryItem {
    Group paths;
    unsigned bit = 0;
    int distinct = 0, pair_distinct = 0;
};

struct History {
    bool indexed;
    unsigned next_slot = 0;
    std::deque<HistoryItem> queue;
    std::vector<uint16_t> membership;

    explicit History(bool use_index) : indexed(use_index) {}

    void append(Group group, size_t id_count) {
        const unsigned bit = 1u << next_slot;
        next_slot = (next_slot + 1) % 16;
        if (queue.size() == 16) {
            if (indexed) {
                for (const Path& p : queue.front().paths)
                    for (int v : p) membership[v] &= ~bit;
            }
            queue.pop_front();
        }
        HistoryItem item{std::move(group), bit};
        if (indexed) {
            membership.resize(id_count);
            const unsigned prev = queue.empty() ? 0 : queue.back().bit;
            item.pair_distinct = queue.empty() ? 0 : queue.back().distinct;
            for (const Path& p : item.paths)
                for (int v : p) {
                    if (membership[v] & bit) continue;
                    ++item.distinct;
                    item.pair_distinct += !(membership[v] & prev);
                    membership[v] |= bit;
                }
        }
        queue.push_back(std::move(item));
    }

    size_t group_bytes = 0;   // Updated on delivery, outside the selection clock.
    static size_t group_storage(const Group& g) {
        size_t n = sizeof(HistoryItem) + g.capacity() * sizeof(Path);
        for (const Path& p : g) n += p.capacity() * sizeof(int);
        return n;
    }
    void commit(Group group, size_t id_count) {
        if (queue.size() == 16) group_bytes -= group_storage(queue.front().paths);
        group_bytes += group_storage(group);
        append(std::move(group), id_count);
    }

    size_t bytes() const { return group_bytes + membership.capacity() * sizeof(uint16_t); }
};

using Four = std::array<int,4>;

Order unpack(int code, int n) {
    Order result(n);
    for (int i = n - 1; i >= 0; --i) {
        result[i] = code & 3;
        code >>= 2;
    }
    return result;
}

int first(unsigned mask) { return __builtin_ctz(mask); }

struct Node {
    State state;
    int work = 0, code = 0;
    Four children{-1, -1, -1, -1};
};

// Reuse current-cohort prefix transitions between template trials, exact
// immediate search and co-optimal enumeration. No value survives the decision.
struct Current {
    Transition& t;
    const Group& q;
    Counters& stats;
    const int n, all;
    std::vector<Node> nodes;
    std::array<Four,4> lcp{};
    Four entry_hits{};
    int root_lower = 0;

    Current(Transition& trans, const Group& group, const State& entry, Counters& counts)
        : t(trans), q(group), stats(counts), n(static_cast<int>(q.size())), all((1<<n)-1) {
        constexpr int sizes[] = {1,2,5,16,65};
        nodes.reserve(sizes[n]); // sum of ordered partial permutations
        nodes.push_back(Node{entry});
        for (int i = 0; i < n; ++i) {
            lcp[i][i] = static_cast<int>(q[i].size());
            for (int j = 0; j < i; ++j) {
                int lo = 0, hi = std::min(q[i].size(), q[j].size());
                while (lo < hi) {
                    int mid = (lo+hi)/2;
                    if (q[i][mid] == q[j][mid]) lo = mid+1;
                    else hi = mid;
                }
                lcp[i][j] = lcp[j][i] = lo;
            }
        }
        entry_hits = hits(entry, all);
        root_lower = absent_union(all, entry_hits);
    }

    Four hits(const State& s, int mask) {
        ++t.epoch;
        for (int j = 0; j < s.size; ++j) t.mark[s.nodes[j]] = t.epoch;
        Four result{};
        for (int i = 0; i < n; ++i) if (mask & (1<<i)) {
            int lo = 0, hi = static_cast<int>(q[i].size());
            while (lo < hi) {
                int mid = (lo+hi)/2;
                if (t.mark[q[i][mid]] == t.epoch) lo = mid+1;
                else hi = mid;
            }
            result[i] = lo;
        }
        return result;
    }

    int absent_union(int mask, const Four& h) const {
        int result = 0;
        for (int i = 0; i < n; ++i) if (mask & (1<<i)) {
            int covered = h[i];
            for (int j = 0; j < i; ++j)
                if (mask & (1<<j)) covered = std::max(covered, lcp[i][j]);
            result += static_cast<int>(q[i].size()) - covered;
        }
        return result;
    }

    int advance(int parent, int i, int remaining) {
        int idx = nodes[parent].children[i];
        if (idx >= 0) return idx;
        idx = static_cast<int>(nodes.size());
        nodes.emplace_back();
        nodes[parent].children[i] = idx;
        Node& a = nodes[parent];
        Node& b = nodes[idx];
        b.work = a.work + t.step(a.state, q[i], b.state);
        b.code = (a.code<<2) | i;
        ++stats.current;
        stats.visited_actions += remaining == 0;
        return idx;
    }

    // Each common prefix node contributes once to demand sum for every path
    // sharing it. The last shared node is at the largest pairwise LCP.
    int pick_clpm(int mask, const Four& h) const {
        int best = -1;
        std::array<int,5> best_rank{};
        for (int i = 0; i < n; ++i) if (mask & (1<<i)) {
            int section = h[i] ? 0 : 1;
            if (section && !q[i].empty()) {
                for (int j = 0; j < i; ++j)
                    if ((mask & (1<<j)) && !h[j] && lcp[i][j]) section = 2;
            }
            int demand = q[i].size(), deepest = 0, others = 0;
            for (int j = 0; j < n; ++j) if (j != i && (mask & (1<<j))) {
                int depth = lcp[i][j];
                demand += depth;
                if (depth > deepest) { deepest = depth; others = 1; }
                else if (depth == deepest) ++others;
            }
            int shared = deepest ? 1 + others : 0;
            std::array<int,5> rank{section,-h[i],-demand,-shared,i};
            if (best < 0 || rank < best_rank) { best = i; best_rank = rank; }
        }
        return best;
    }

    void dfs_visit(int mask, int depth, Order& out) const {
        for (int i = 0; i < n; ++i) if ((mask & (1<<i)) && lcp[i][i] == depth) {
            out.push_back(i);
            mask ^= 1<<i;
        }
        struct Child { int mask, depth, first; double priority; };
        std::array<Child,4> children;
        int count = 0;
        while (mask) {
            int left = first(mask), child = 0, size = 0, cached = 0;
            int stem = lcp[left][left];
            for (int i = left; i < n; ++i) if ((mask & (1<<i)) && lcp[left][i] > depth) {
                int covered = depth;
                for (int j = left; j < i; ++j)
                    if (child & (1<<j)) covered = std::max(covered, lcp[i][j]);
                size += lcp[i][i] - covered;
                cached += std::max(0, entry_hits[i]-covered);
                child |= 1<<i;
                stem = std::min(stem, lcp[left][i]);
            }
            const double priority = 10000.0 * cached / size + .001 * __builtin_popcount(child);
            children[count++] = {child,stem,left,priority};
            mask ^= child;
        }
        std::sort(children.begin(), children.begin()+count, [](const Child& a, const Child& b) {
            return a.priority == b.priority ? a.first < b.first : a.priority > b.priority;
        });
        for (int j = 0; j < count; ++j) dfs_visit(children[j].mask, children[j].depth, out);
    }

    int trial(int mode) {
        int node = 0, mask = all;
        Order dfs;
        if (mode == 4) dfs_visit(all, 0, dfs);
        for (int pos = 0; mask; ++pos) {
            int i = first(mask);
            if (mode == 4) i = dfs[pos];
            else if ((mask & (mask-1)) && (mode >= 2 || (mode == 1 && pos%2))) {
                const Four h = node ? hits(nodes[node].state, mask) : entry_hits;
                if (mode == 3) i = pick_clpm(mask, h);
                else for (int j = i+1; j < n; ++j)
                    if ((mask & (1<<j)) && h[j] > h[i]) i = j;
            }
            mask ^= 1<<i;
            node = advance(node, i, mask);
        }
        return node;
    }

    void find_better(int node, int mask, int& best) {
        if (!mask) {
            if (nodes[node].work < nodes[best].work) best = node;
            return;
        }
        int bound = node ? nodes[node].work + absent_union(mask, hits(nodes[node].state, mask)) : root_lower;
        if (bound >= nodes[best].work) return;
        for (int i = 0; i < n; ++i) if (mask & (1<<i)) {
            int remaining = mask ^ (1<<i);
            find_better(advance(node, i, remaining), remaining, best);
            if (nodes[best].work == root_lower) break;
        }
    }

    int incumbent() {
        int best = trial(0);
        for (int mode = 1; mode <= 4 && nodes[best].work != root_lower; ++mode) {
            int other = trial(mode);
            if (nodes[other].work < nodes[best].work) best = other;
        }
        if (nodes[best].work != root_lower) find_better(0, all, best);
        return best;
    }

    static bool equal(const State& a, const State& b) {
        return a.size == b.size && std::memcmp(a.nodes.data(), b.nodes.data(), a.size*sizeof(int)) == 0;
    }

    void eligible(int node, int mask, int inc, std::vector<int>& reps) {
        if (nodes[node].work > nodes[inc].work) return;
        if (!mask) {
            if (nodes[node].work != nodes[inc].work) return;
            ++stats.eligible_orders;
            for (int& r : reps) if (equal(nodes[r].state, nodes[node].state)) {
                if (node == inc) r = node; // traversal itself is lexicographic
                return;
            }
            reps.push_back(node);
            return;
        }
        for (int i = 0; i < n; ++i) if (mask & (1<<i)) {
            int remaining = mask ^ (1<<i);
            eligible(advance(node, i, remaining), remaining, inc, reps);
        }
    }
};

struct Pair {
    const Group& a;
    const Group& b;
    unsigned mask;
    int distinct;
};

int rollout(Transition& t, State s, const Pair& p, Counters& stats) {
    ++stats.rollouts;
    int cost = t.continuation(s, p.a, stats.future);
    return cost + t.continuation(s, p.b, stats.future);
}

struct RankDifferences {
    Path ranks;
    unsigned groups = 0;
    RankDifferences(const Current& current, const std::vector<int>& reps, const History& history) {
        if (reps.size() < 2) return;
        const State& base = current.nodes[reps.front()].state;
        int longest = base.size;
        for (int r : reps) longest = std::max(longest, current.nodes[r].state.size);
        for (int k = 0; k < longest; ++k) {
            int first_id = k < base.size ? base.nodes[k] : 0;
            bool varies = false;
            unsigned support = history.membership[first_id];
            for (size_t j = 1; j < reps.size(); ++j) {
                const State& other = current.nodes[reps[j]].state;
                int id = k < other.size ? other.nodes[k] : 0;
                if (id != first_id) {
                    varies = true;
                    support |= history.membership[id];
                }
            }
            if (varies) { ranks.push_back(k); groups |= support; }
        }
    }
};

// A fixed pair only inspects nodes in its path union U. Keep the identity AND
// rank of each such retained node. In the prefix above the oldest U node let
// z count outsiders. If |U|+z fits, every U node survives until its first hit.
int closed_form(const State& s, const History& history, const Pair& p, int cap) {
    if (p.distinct > cap) return -1;
    int hits = 0, z = 0;
    for (int k = 0; k < s.size; ++k)
        if (history.membership[s.nodes[k]] & p.mask) {
            ++hits;
            z = k+1-hits;
        }
    return p.distinct + z <= cap ? p.distinct - hits : -1;
}

struct ClassScore { Path key; int score; };

void optimized_pair(Transition& t, const Current& cur, const std::vector<int>& reps,
                    const History& history, const Pair& p, const RankDifferences& diff,
                    bool absolute, std::vector<int>& sums, Counters& stats) {
    if (!(diff.groups & p.mask)) {
        ++stats.common_pairs;
        if (!absolute) return;
        const State& s = cur.nodes[reps.front()].state;
        int value = closed_form(s, history, p, t.cap);
        if (value < 0) value = rollout(t, s, p, stats);
        else ++stats.form_scores;
        for (int& v : sums) v += value;
        return;
    }
    std::vector<ClassScore> memo;
    Path key;
    size_t key_bytes = 0;
    for (size_t j = 0; j < reps.size(); ++j) {
        const State& s = cur.nodes[reps[j]].state;
        int value = closed_form(s, history, p, t.cap);
        if (value >= 0) {
            ++stats.form_scores;
        } else {
            key.clear();
            // Fixed ranks and all outsiders are equal across representatives.
            for (int k : diff.ranks) {
                if (k >= s.size) break;
                int v = s.nodes[k];
                if (history.membership[v] & p.mask) {
                    key.push_back(k);
                    key.push_back(v);
                }
            }
            for (const auto& item : memo) if (item.key == key) {
                value = item.score;
                ++stats.memo_hits;
                break;
            }
            if (value < 0) {
                value = rollout(t, s, p, stats);
                memo.push_back({key, value});
                key_bytes += memo.back().key.capacity()*sizeof(int);
            }
        }
        sums[j] += value;
    }
    stats.memo_entries = std::max(stats.memo_entries, static_cast<int>(memo.size()));
    stats.memo_bytes = std::max(stats.memo_bytes, key_bytes + memo.capacity()*sizeof(ClassScore)
                                + key.capacity()*sizeof(int));
}

struct Decision {
    Order order, inc;
    State exit;
    int immediate = 0, den = 1, future = -1;
    Counters stats;
};

Decision decide(Transition& t, const State& start, const Group& q, Method method,
                const History& hist, bool absolute) {
    Decision d;
    const int n = static_cast<int>(q.size());
    if (method == Method::K) {
        d.exit = start;
        int mask = (1<<n)-1;
        for (int j = 0; mask; ++j) {
            int i = t.choose(q, mask, j, d.exit);
            State next;
            d.immediate += t.step(d.exit, q[i], next);
            d.exit = next;
            d.order.push_back(i);
            mask ^= 1<<i;
            ++d.stats.current;
        }
        d.inc = d.order; // control has no exact-immediate incumbent calculation
        d.stats.visited_actions = 1;
        d.stats.candidate_states = 1;
        return d;
    }
    Current cur(t, q, start, d.stats);
    int inc = cur.incumbent();
    int selected = inc;
    int pairs = static_cast<int>(hist.queue.size()/2);
    d.den = std::max(1, pairs);
    if (historical(method) && pairs && (absolute || n > 1)) {
        std::vector<int> reps;
        cur.eligible(0, cur.all, inc, reps);
        d.stats.candidate_states = static_cast<int>(reps.size());
        const bool score = absolute || reps.size() > 1;
        if (score) {
            std::vector<int> sums(reps.size());
            const std::vector<int> empty;
            RankDifferences diff(cur, method == Method::Optimized ? reps : empty, hist);
            for (int end = static_cast<int>(hist.queue.size()); end >= 2; end -= 2) {
                const auto& a = hist.queue[end-2];
                const auto& b = hist.queue[end-1];
                Pair p{a.paths,b.paths,a.bit|b.bit,b.pair_distinct};
                if (method == Method::Reference) {
                    for (size_t j = 0; j < reps.size(); ++j)
                        sums[j] += rollout(t, cur.nodes[reps[j]].state, p, d.stats);
                } else {
                    optimized_pair(t, cur, reps, hist, p, diff, absolute, sums, d.stats);
                }
            }
            size_t win = 0;
            for (size_t j = 1; j < reps.size(); ++j) {
                bool preferred = reps[j] == inc ||
                    (reps[win] != inc && cur.nodes[reps[j]].code < cur.nodes[reps[win]].code);
                if (sums[j] < sums[win] || (sums[j] == sums[win] && preferred)) win = j;
            }
            selected = reps[win];
            if (absolute) d.future = sums[win];
        } else {
            d.stats.common_pairs = pairs;
        }
    } else {
        d.stats.candidate_states = 1;
        if (historical(method) && !pairs && absolute) d.future = 0;
        if (historical(method) && n == 1 && !absolute) d.stats.common_pairs = pairs;
    }
    d.order = unpack(cur.nodes[selected].code, n);
    d.inc = unpack(cur.nodes[inc].code, n);
    d.exit = cur.nodes[selected].state;
    d.immediate = cur.nodes[selected].work;
    d.stats.current_cache_entries = static_cast<int>(cur.nodes.size());
    d.stats.current_cache_bytes = cur.nodes.capacity() * sizeof(Node);
    return d;
}

struct Session {
    Method method;
    bool absolute;
    int cap;
    Names names;
    Transition t;
    State state;
    History hist;

    Session(Method m, bool abs, int capacity) : method(m), absolute(abs), cap(capacity),
            t(capacity,1), hist(m == Method::Optimized) {}

    void ensure_size() {
        t.mark.resize(names.original.size());
        // The frozen transition stamps scratch membership with ++epoch. One
        // decision uses < 8192 stamps: <= 24 exits * 8 pairs * 8 requests * 2
        // plus the <= 65 current-prefix nodes and five templates.
        if (t.epoch > ~0u - 8192u) {
            std::fill(t.mark.begin(), t.mark.end(), 0u);
            t.epoch = 0;
        }
        if (hist.indexed) hist.membership.resize(names.original.size());
    }
    void commit(Group q) {
        if (historical(method)) hist.commit(std::move(q), names.original.size());
    }
};

void write_decision(std::ostream& out, const Session& s, const Decision& d,
                    int64_t parse, int64_t cpu, int64_t update) {
    Path exit;
    for (int j = 0; j < d.exit.size; ++j) exit.push_back(s.names.original[d.exit.nodes[j]]);
    const auto& m = d.stats;
    int objective = d.future < 0 ? -1 : d.future+d.den*d.immediate;
    out << "{\"order\":" << array(d.order) << ",\"incumbent\":" << array(d.inc)
        << ",\"selected_exit\":" << array(exit) << ",\"immediate_blocks\":" << d.immediate
        << ",\"den\":" << d.den << ",\"future_blocks\":" << d.future
        << ",\"objective_num\":" << objective << ",\"current_transitions\":" << m.current
        << ",\"rollout_transitions\":" << m.future << ",\"rollouts\":" << m.rollouts
        << ",\"candidate_states\":" << m.candidate_states << ",\"eligible_orders\":" << m.eligible_orders
        << ",\"visited_actions\":" << m.visited_actions << ",\"common_pairs\":" << m.common_pairs
        << ",\"form_scores\":" << m.form_scores << ",\"memo_hits\":" << m.memo_hits
        << ",\"memo_entries\":" << m.memo_entries << ",\"memo_bytes\":" << m.memo_bytes
        << ",\"current_cache_entries\":" << m.current_cache_entries
        << ",\"current_cache_bytes\":" << m.current_cache_bytes
        << ",\"history_bytes\":" << s.hist.bytes() << ",\"history_entries\":" << s.hist.queue.size()
        << ",\"index_bytes\":" << s.hist.membership.capacity()*sizeof(uint16_t)
        << ",\"interned_nodes\":" << s.names.original.size()-1
        << ",\"parse_ns\":" << parse << ",\"cpu_ns\":" << cpu << ",\"update_ns\":" << update << "}";
}

void command(const std::string& line, std::unique_ptr<Session>& live, std::ostream& out) {
    auto begin = cpu_ns();
    std::istringstream raw(line);
    Input in{raw,{}};
    std::string op = in.word();
    std::unique_ptr<Session> direct;
    if (op == "R" || op == "D") {
        Method m = method_named(in.word());
        bool absolute = in.number(0,1);
        int cap = in.number(1,MAX_CAP);
        direct = std::make_unique<Session>(m,absolute,cap);
        if (op == "R") {
            in.finish();
            live = std::move(direct);
            out << "{\"ok\":true}";
            return;
        }
    }
    require(op == "D" || op == "W" || op == "G", "unknown opcode");
    Session* s = direct ? direct.get() : live.get();
    require(s != nullptr, "reset session first");
    in.names = std::move(s->names);
    Path initial;
    if (op == "D") {
        initial = in.state(s->cap);
        in.keyword("Q");
    }
    Group q = in.group(s->cap);
    if (op == "D") {
        in.keyword("H");
        int count = in.number(0,16);
        for (int j=0; j<count; ++j) {
            Group past = in.group(s->cap);
            if (historical(s->method)) s->hist.commit(std::move(past), in.names.original.size());
        }
        in.valid_state(initial);
        s->state = State(initial);
    }
    in.finish();
    s->names = std::move(in.names);
    s->ensure_size();
    auto ready = cpu_ns();
    if (op == "W") {
        int work = 0;
        for (const auto& p : q) {
            State next;
            work += s->t.step(s->state,p,next);
            s->state = next;
        }
        s->commit(std::move(q));
        out << "{\"immediate_blocks\":" << work << ",\"parse_ns\":" << ready-begin
            << ",\"update_ns\":" << cpu_ns()-ready << "}";
        return;
    }
    Decision d = decide(s->t,s->state,q,s->method,s->hist,s->absolute);
    auto chosen = cpu_ns();
    if (op == "G") {
        s->state = d.exit;
        s->commit(std::move(q));
    }
    auto done = cpu_ns();
    write_decision(out,*s,d,ready-begin,chosen-ready,done-chosen);
}
} // namespace matched

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    std::unique_ptr<matched::Session> live;
    std::string line;
    try {
        while (std::getline(std::cin,line)) {
            std::ostringstream reply;
            matched::command(line,live,reply);
            std::cout << reply.str() << '\n' << std::flush;
        }
    } catch (const std::exception& e) {
        std::cout << "{\"error\":\"" << e.what() << "\"}" << std::endl;
        return 1;
    }
    return 0;
}
