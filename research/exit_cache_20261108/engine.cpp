// C++17. Stateless, single-threaded scoring under the parent prefix-leaf LRU.
#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <ctime>
#include <iostream>
#include <map>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <vector>

using Path = std::vector<int>;
using Group = std::vector<Path>;
using Groups = std::vector<Group>;
using Order = std::vector<int>;
constexpr int MAX_CAP = 128;

void require(bool ok, const char* why) {
    if (!ok) throw std::runtime_error(why);
}

std::int64_t cpu_ns() {
    timespec t;
    require(clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t) == 0, "CPU clock unavailable");
    return static_cast<std::int64_t>(t.tv_sec) * 1000000000 + t.tv_nsec;
}

// Node identities are interned independently for this line, from only the supplied input.
struct Names {
    std::unordered_map<int, int> local;
    Path original{0};
    Path parent{-1};

    int intern(int raw) {
        require(raw > 0, "nonpositive node");
        auto [it, added] = local.emplace(raw, static_cast<int>(original.size()));
        if (added) {
            original.push_back(raw);
            parent.push_back(-1);
        }
        return it->second;
    }
};

struct Input {
    std::istream& in;
    Names names;

    std::string word() {
        std::string s;
        require(static_cast<bool>(in >> s), "missing field");
        return s;
    }
    void keyword(const char* key) { require(word() == key, "unexpected field"); }
    int number(int lo, int hi) {
        int v;
        require(static_cast<bool>(in >> v) && lo <= v && v <= hi, "integer out of range");
        return v;
    }
    void finish() { std::string s; require(!(in >> s), "trailing fields"); }
    int node() { return names.intern(number(1, INT32_MAX)); }

    Path state(int cap) {
        Path s(number(0, cap));
        for (int& v : s) v = node();
        require(std::set<int>(s.begin(), s.end()).size() == s.size(), "duplicate state node");
        return s;
    }

    Group group(int cap) {
        Group g(number(1, 4));
        for (auto& path : g) {
            path.resize(number(0, cap));
            int prev = 0;
            for (int& v : path) {
                v = node();
                int& parent = names.parent[v];
                require(parent < 0 || parent == prev, "inconsistent prefix identity");
                parent = prev;
                prev = v;
            }
        }
        return g;
    }

    Order order(int n) {
        Order o(n);
        for (int& i : o) i = number(0, n - 1);
        require(std::set<int>(o.begin(), o.end()).size() == o.size(), "invalid permutation");
        return o;
    }

    void valid_state(const Path& state) const {
        std::set<int> earlier;
        for (int v : state) {
            const int p = names.parent[v];
            // Nodes absent from all disclosed paths have an unknown parent.
            require(p <= 0 || earlier.count(p), "initial state violates prefix closure/recency");
            earlier.insert(v);
        }
    }
};

// States list nodes from highest to lowest retention priority. Same-tick nodes
// came from one path, so shallow-to-deep exactly reverses deepest-first eviction.
struct State {
    std::array<int, MAX_CAP> nodes{};
    int size = 0;
    State() = default;
    explicit State(const Path& ids) : size(static_cast<int>(ids.size())) {
        std::copy(ids.begin(), ids.end(), nodes.begin());
    }
    Path key() const { return Path(nodes.begin(), nodes.begin() + size); }
};

struct Transition {
    int cap;
    std::vector<unsigned> mark;
    unsigned epoch = 0;
    Transition(int c, int n) : cap(c), mark(n) {}

    int step(const State& from, const Path& path, State& to) {
        ++epoch;
        to.size = static_cast<int>(path.size());
        std::copy(path.begin(), path.end(), to.nodes.begin());
        for (int v : path) mark[v] = epoch;
        int matches = 0;
        for (int j = 0; j < from.size; ++j) {
            const int v = from.nodes[j];
            if (mark[v] == epoch) ++matches;
            else if (to.size < cap) to.nodes[to.size++] = v;
        }
        return static_cast<int>(path.size()) - matches;
    }

    int choose(const Group& g, unsigned pending, int pos, const State& state) {
        if ((pos % 2) == 0 || !(pending & (pending - 1))) return __builtin_ctz(pending);
        ++epoch;
        for (int j = 0; j < state.size; ++j) mark[state.nodes[j]] = epoch;
        int best_i = -1, best_hits = -1;
        for (int i = 0; i < static_cast<int>(g.size()); ++i) {
            if (!(pending & (1u << i))) continue;
            const auto& p = g[i];
            // Prefix closure makes membership monotone along this path.
            int lo = 0, hi = static_cast<int>(p.size());
            while (lo < hi) {
                const int mid = (lo + hi) / 2;
                if (mark[p[mid]] == epoch) lo = mid + 1;
                else hi = mid;
            }
            if (lo > best_hits) { best_hits = lo; best_i = i; }
        }
        return best_i;
    }

    int continuation(State& state, const Group& group, int& nstep) {
        unsigned pending = (1u << group.size()) - 1;
        int misses = 0;
        for (int pos = 0; pending; ++pos) {
            int i = choose(group, pending, pos, state);
            State next;
            misses += step(state, group[i], next);
            ++nstep;
            pending ^= 1u << i;
            state = next;
        }
        return misses;
    }
};

struct Action {
    int misses;
    Order order;
    Path exit;
};

bool prefer(const Order& left, const Order& right, const Order& inc) {
    if ((left == inc) != (right == inc)) return left == inc;
    return left < right;
}

struct Space {
    std::vector<Action> actions;
    // Map full exit -> least-cost action, breaking ties by incumbent then arrival.
    std::map<Path, int> representatives;
    std::set<Path> resident_sets;
    int min_cost = INT32_MAX;
    int current_steps = 0;

    Space(Transition& t, const State& start, const Group& q, const Order& inc) {
        Order prefix;
        auto enumerate = [&](auto& recurse, const State& s, unsigned pending, int m) -> void {
            if (!pending) {
                Path k = s.key();
                const int index = static_cast<int>(actions.size());
                actions.push_back({m, prefix, k});
                min_cost = std::min(min_cost, m);
                auto [rep, added] = representatives.emplace(k, index);
                if (!added) {
                    const auto& earlier = actions[rep->second];
                    if (m < earlier.misses || (m == earlier.misses && prefer(prefix, earlier.order, inc)))
                        rep->second = index;
                } else {
                    std::sort(k.begin(), k.end());
                    resident_sets.insert(k);
                }
                return;
            }
            for (int i = 0; i < static_cast<int>(q.size()); ++i) {
                if (!(pending & (1u << i))) continue;
                State next;
                int delta = t.step(s, q[i], next);
                ++current_steps;
                prefix.push_back(i);
                recurse(recurse, next, pending ^ (1u << i), m + delta);
                prefix.pop_back();
            }
        };
        enumerate(enumerate, start, (1u << q.size()) - 1, 0);
        require(at(inc).misses == min_cost, "supplied incumbent is not immediate optimal");
    }

    const Action& at(const Order& order) const {
        for (const Action& a : actions) if (a.order == order) return a;
        throw std::runtime_error("missing action");
    }
};

using Samples = std::vector<std::vector<const Group*>>;

Samples samples(const Groups& history, const std::string& mode) {
    Samples s;
    if (mode == "H0") return s;
    for (int end = static_cast<int>(history.size()); end >= 2 && s.size() < 8; end -= 2) {
        s.push_back({&history[end - 2]});
        if (mode != "H1") s.back().push_back(&history[end - 1]);
    }
    return s;
}

int future_sum(Transition& t, const Path& exit, const Samples& draws, int& steps, int& rolls) {
    int sum = 0;
    for (const auto& seq : draws) {
        State s(exit);
        ++rolls;
        for (const auto* g : seq) sum += t.continuation(s, *g, steps);
    }
    return sum;
}

struct Scores {
    int steps = 0, rolls = 0, denominator = 1, best = -1, advantage = 0;
    std::int64_t rollout_ns = 0;
    std::map<Path, int> future;

    Scores(Transition& t, const Space& a, const Samples& draws, const Order& inc,
           bool tie_only, bool need_absolute) {
        denominator = std::max(1, static_cast<int>(draws.size()));
        std::vector<int> eligible;
        for (const auto& [_, idx] : a.representatives)
            if (!tie_only || a.actions[idx].misses == a.min_cost) eligible.push_back(idx);

        // With one eligible exit, its rollout value is an additive constant for
        // every eligible action. Offline diagnostics additionally need absolute costs.
        if (!draws.empty() && (eligible.size() > 1 || need_absolute)) {
            const auto begin = cpu_ns();
            for (int i : eligible) {
                const auto& key = a.actions[i].exit;
                future.emplace(key, future_sum(t, key, draws, steps, rolls));
            }
            rollout_ns = cpu_ns() - begin;
        }
        int value = INT32_MAX;
        for (int i : eligible) {
            const auto& action = a.actions[i];
            int v = score(action);
            if (v < value || (v == value && prefer(action.order, a.actions[best].order, inc))) {
                value = v;
                best = i;
            }
        }
        advantage = score(a.at(inc)) - value;
    }

    int score(const Action& a) const {
        return a.misses * denominator + (future.empty() ? 0 : future.at(a.exit));
    }
};

std::string array(const Path& v) {
    std::ostringstream os;
    os << '[';
    for (size_t j = 0; j < v.size(); ++j) {
        if (j) os << ',';
        os << v[j];
    }
    os << ']';
    return os.str();
}

void online(std::istream& raw, std::ostream& out) {
    Input in{raw, {}};
    in.keyword("D");
    const std::string mode = in.word();
    require(mode == "H2" || mode == "H1" || mode == "TIE" || mode == "H0", "invalid online mode");
    const int cap = in.number(1, MAX_CAP);
    const Path start = in.state(cap);
    in.keyword("Q");
    const Group current = in.group(cap);
    in.keyword("I");
    const Order inc = in.order(static_cast<int>(current.size()));
    in.keyword("H");
    Groups history(in.number(0, 16));
    for (Group& g : history) g = in.group(cap);
    in.finish();
    in.valid_state(start);
    const auto begin = cpu_ns();
    Transition t(cap, static_cast<int>(in.names.original.size()));
    const Space a(t, State(start), current, inc);
    const Scores v(t, a, samples(history, mode), inc, mode == "TIE", false);
    const Action& selected = a.actions[v.best];
    const auto elapsed = cpu_ns() - begin;
    Path original_exit;
    for (int u : selected.exit) original_exit.push_back(in.names.original[u]);
    out << "{\"order\":" << array(selected.order) << ",\"incumbent\":" << array(inc)
        << ",\"selected_exit\":" << array(original_exit)
        << ",\"immediate_blocks\":" << selected.misses << ",\"min_blocks\":" << a.min_cost
        << ",\"excess_blocks\":" << selected.misses - a.min_cost
        << ",\"adv_num_blocks\":" << v.advantage << ",\"den\":" << v.denominator
        << ",\"distinct_full\":" << a.representatives.size()
        << ",\"distinct_sets\":" << a.resident_sets.size() << ",\"legal\":" << a.actions.size()
        << ",\"current_transitions\":" << a.current_steps << ",\"rollout_transitions\":" << v.steps
        << ",\"rollouts\":" << v.rolls << ",\"cpu_ns\":" << elapsed
        << ",\"rollout_cpu_ns\":" << v.rollout_ns << "}";
}

// The offline message exclusively accepts previously fixed actions and two supplied
// actual cohorts. Neither this command nor its fields is accepted by --online.
void hindsight(std::istream& raw, std::ostream& out) {
    Input in{raw, {}};
    in.keyword("X");
    const int cap = in.number(1, MAX_CAP);
    const Path start = in.state(cap);
    in.keyword("Q");
    const Group q = in.group(cap);
    in.keyword("I");
    const Order inc = in.order(static_cast<int>(q.size()));
    in.keyword("A");
    const Order fixed = in.order(static_cast<int>(q.size()));
    in.keyword("F");
    in.number(2, 2);
    const Group first = in.group(cap), second = in.group(cap);
    in.finish();
    in.valid_state(start);
    const auto begin = cpu_ns();
    Transition t(cap, static_cast<int>(in.names.original.size()));
    const Space a(t, State(start), q, inc);
    const Scores v(t, a, {{&first, &second}}, inc, false, true);
    const Action& best = a.actions[v.best];
    const int fixed_cost = v.score(a.at(fixed));
    out << "{\"best_order\":" << array(best.order) << ",\"best_blocks\":" << v.score(best)
        << ",\"selected_blocks\":" << fixed_cost << ",\"incumbent_blocks\":" << v.score(a.at(inc))
        << ",\"selected_optimal\":" << (fixed_cost == v.score(best) ? "true" : "false")
        << ",\"legal\":" << a.actions.size() << ",\"current_transitions\":" << a.current_steps
        << ",\"rollout_transitions\":" << v.steps << ",\"cpu_ns\":" << cpu_ns() - begin << "}";
}

using Dated = std::map<int, int>;

// Independent reference for artificial trie node IDs. Tests generate the whole
// tree with parent(v)=(v-1)/3, and use actual touch stamps and explicit leaf eviction.
int test_parent(int v) { return (v - 1) / 3; }
Path test_path(int v, int cap) {
    Path p;
    for (; v; v = test_parent(v)) p.push_back(v);
    std::reverse(p.begin(), p.end());
    if (static_cast<int>(p.size()) > cap) p.resize(cap);
    return p;
}

int slow_step(Dated& state, const Path& p, int cap, int stamp) {
    int m = 0;
    for (int v : p) {
        m += !state.count(v);
        state[v] = stamp;
    }
    while (static_cast<int>(state.size()) > cap) {
        std::set<int> excluded(p.begin(), p.end());
        for (const auto& [v, _] : state) excluded.insert(test_parent(v));
        std::tuple<int, int, int> worst{INT32_MAX, 0, 0};
        for (const auto& [v, last] : state)
            if (!excluded.count(v))
                worst = std::min(worst, {last, -static_cast<int>(test_path(v, cap).size()), v});
        const int evict = std::get<2>(worst);
        require(evict > 0, "slow reference found no evictable leaf");
        state.erase(evict);
    }
    return m;
}

Path canonical(const Dated& s, int cap) {
    Path key;
    for (const auto& [v, _] : s) key.push_back(v);
    std::sort(key.begin(), key.end(), [&](int u, int v) {
        return std::make_tuple(-s.at(u), test_path(u, cap).size(), u)
             < std::make_tuple(-s.at(v), test_path(v, cap).size(), v);
    });
    return key;
}

void checks() {
    // Two reachable states with the same resident set and different LRU orders.
    Transition t(2, 20);
    State left(Path{1, 2}), right(Path{2, 1}), nl, nr;
    require(t.step(left, {3}, nl) == 1 && t.step(right, {3}, nr) == 1, "singleton miss");
    require(nl.key() == Path({3, 1}) && nr.key() == Path({3, 2}), "recency matters");
    State later;
    require(t.step(nl, {1}, later) == 0 && t.step(nr, {1}, later) == 1, "different future cost");

    // Reviewer example: history [a/x] then [a/z], initial a/z, current b/t and a/x.
    Group current{{3, 4}, {1, 5}};
    Order incumbent{1, 0}, alternative{0, 1};
    Groups hist{{{1, 5}}, {{1, 2}}};
    Space a(t, State(Path{1, 2}), current, incumbent);
    require(a.min_cost == 3 && a.at(alternative).misses == 4, "fixture immediate cost");
    Scores h2(t, a, samples(hist, "H2"), incumbent, false, true);
    require(h2.score(a.at(incumbent)) == 6 && h2.score(a.at(alternative)) == 5
            && a.actions[h2.best].order == alternative && h2.advantage == 1, "two-step sacrifice");
    Scores h1(t, a, samples(hist, "H1"), incumbent, false, true);
    require(h1.score(a.at(incumbent)) == 5 && h1.score(a.at(alternative)) == 4, "one-step cost");
    Scores tie(t, a, samples(hist, "TIE"), incumbent, true, false);
    require(a.actions[tie.best].order == incumbent && tie.rolls == 0, "tie-only restriction");
    for (const auto& s : {samples(hist,"H0"), samples({hist.front()}, "H2"), Samples{}}) {
        Scores none(t, a, s, incumbent, false, false);
        require(a.actions[none.best].order == incumbent && none.advantage == 0 && none.rolls == 0,
                "no-history and H0 fallback");
    }

    // The incumbent can win an exact tie despite its nonlexicographic order.
    Space tied(t, State(), Group{{1}, {2}}, incumbent);
    Scores h0(t, tied, {}, incumbent, false, false);
    require(tied.representatives.size() == 2 && tied.resident_sets.size() == 1
            && tied.actions[h0.best].order == incumbent, "recency-only and incumbent tie");
    // Identical full exit; least immediate cost retained before rollout.
    Transition one(1, 20);
    const Order ab_inc{0, 2, 1};
    Space same(one, State(), Group{{1}, {2}, {1}}, ab_inc);
    require(same.actions.size() == 6 && same.representatives.size() == 2, "full-state collapse");
    require(same.at({0, 1, 2}).exit == same.at({1, 0, 2}).exit
            && same.at({0, 1, 2}).misses == 3 && same.at({1, 0, 2}).misses == 2
            && same.actions[same.representatives.at({1})].order == Order({1, 0, 2}),
            "least immediate and lexicographic representative");

    Groups odd(5);
    for (int i = 0; i < 5; ++i) odd[i] = {{i + 1}};
    const auto two = samples(odd, "H2"), single = samples(odd, "H1");
    require(two == Samples{{&odd[3], &odd[4]}, {&odd[1], &odd[2]}}
            && single == Samples{{&odd[3]}, {&odd[1]}}, "backward pair alignment");

    std::mt19937 rng(87221);
    for (int cap = 1; cap <= 12; ++cap) {
        Transition trans(cap, 301);
        Dated s;
        State fast;
        for (int tick = 1; tick <= 120; ++tick) {
            Group q;
            for (int i = 0; i < 4; ++i) q.push_back(test_path(rng() % 301, cap));
            unsigned pending = 1 + rng() % 15;
            int best = -1, best_h = -1;
            for (int i = 0; i < 4; ++i) {
                if (!(pending & (1u << i))) continue;
                int h = 0;
                for (int v : q[i]) if (s.count(v)) ++h;
                if (h > best_h) { best_h = h; best = i; }
            }
            require(trans.choose(q, pending, 1, fast) == best, "k-LPM odd slot");
            require(trans.choose(q, pending, 0, fast) == __builtin_ctz(pending), "k-LPM even slot");
            State next;
            const auto& p = q[tick % 4];
            require(trans.step(fast, p, next) == slow_step(s, p, cap, tick), "slow-reference misses");
            require(next.key() == canonical(s, cap) && next.size <= cap, "slow-reference complete state");
            fast = next;
        }
    }

    auto online_rejects = [](const std::string& line) {
        std::istringstream in(line);
        std::ostringstream out;
        try { online(in, out); return false; }
        catch (const std::runtime_error&) { return true; }
    };
    require(online_rejects("X 2 0 Q 1 0 I 0 A 0 F 2 1 0 1 0")
            && online_rejects("D H2 2 0 Q 1 0 I 0 H 0 F 2 1 0 1 0"), "online rejects future fields");
    require(online_rejects("D H0 2 1 2 Q 1 2 1 2 I 0 H 0"), "missing ancestor");
    require(online_rejects("D H0 2 2 2 1 Q 1 2 1 2 I 0 H 0"), "reversed ancestor recency");
    std::istringstream diag("X 2 2 1 2 Q 2 2 3 4 2 1 5 I 1 0 A 0 1 F 2 1 2 1 5 1 2 1 2");
    std::ostringstream result;
    hindsight(diag, result);
    require(result.str().find("\"best_blocks\":5,\"selected_blocks\":5,\"incumbent_blocks\":6") !=
            std::string::npos, "post-dispatch diagnostic");
}

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    try {
        require(argc == 2, "choose --online, --hindsight, or --self-test");
        std::string role = argv[1];
        if (role == "--self-test") {
            checks();
            std::cout << "PASS\n";
            return 0;
        }
        require(role == "--online" || role == "--hindsight", "unknown role");
        std::string line;
        while (std::getline(std::cin, line)) {
            std::istringstream in(line);
            std::ostringstream out;
            if (role == "--online") online(in, out);
            else hindsight(in, out);
            std::cout << out.str() << '\n' << std::flush;
        }
    } catch (const std::exception& e) {
        std::cout << "{\"error\":\"" << e.what() << "\"}" << std::endl;
        return 1;
    }
    return 0;
}
