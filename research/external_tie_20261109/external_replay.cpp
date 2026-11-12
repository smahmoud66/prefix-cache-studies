// Offline streaming interface to an online policy. Each dispatch receives only the
// present cohort, cache, and allowed completed history. Numeric I/O is outside timing.
#include "frozen_evaluator.hpp"
#include <chrono>
#include <sys/resource.h>

using namespace matched;
using Clock = std::chrono::steady_clock;
enum class Policy { FCFS, K, IMM, OPT, RAND, RANK, CHECK };

Policy mode(const std::string& arg) {
    static const std::map<std::string,Policy> modes{
        {"FCFS",Policy::FCFS},{"K",Policy::K},{"IMM",Policy::IMM},{"OPT",Policy::OPT},
        {"RAND",Policy::RAND},{"RANK",Policy::RANK},{"CHECK",Policy::CHECK}};
    return modes.at(arg);
}

struct RankHistory {
    std::deque<Group> recent;
    std::vector<unsigned> counts;
    size_t group_bytes = 0;

    void commit(Group g, size_t size) {
        counts.resize(size);
        if (recent.size() == 16) {
            for (const Path& p : recent.front())
                for (int id : p) --counts[id];
            group_bytes -= History::group_storage(recent.front());
            recent.pop_front();
        }
        for (const Path& p : g) for (int id : p) ++counts[id];
        group_bytes += History::group_storage(g);
        recent.push_back(std::move(g));
    }
    std::int64_t score(const State& state, int cap) const {
        std::int64_t value = 0;
        for (int rank = 0; rank < state.size; ++rank)
            value += std::int64_t(counts[state.nodes[rank]]) * (cap-rank);
        return value;
    }
    // Incomplete startup history drops the oldest group, just as the rollout pairs do.
    void unpaired(bool restore) {
        if (recent.size()%2)
            for (const auto& p : recent.front()) for (int v : p) {
                if (restore) ++counts[v]; else --counts[v];
            }
    }
};

struct Frame {
    Group raw;
    std::int64_t tails = 0;
    bool warm = false;
};

Frame parse(const std::string& line, int cap, int block) {
    Frame frame;
    std::istringstream stream(line);
    char stage;
    int n;
    require(bool(stream >> stage >> n) && (stage=='W'||stage=='G') && n>=1 && n<=4,
            "invalid stage or cohort width");
    frame.warm = stage=='W';
    for (int i=0;i<n;++i) {
        int tokens, length;
        require(bool(stream >> tokens >> length) && tokens>0 && length>=0
                && length<=(tokens-1)/block && length>=std::min(cap,(tokens-1)/block),
                "length disagrees with available certified full blocks");
        Path path;
        path.reserve(std::min(cap,length));
        for (int j=0;j<length;++j) {
            int id;
            require(bool(stream >> id) && id>0, "invalid node");
            if (j<cap) path.push_back(id);
        }
        frame.tails += tokens - std::int64_t(block)*path.size();
        frame.raw.push_back(std::move(path));
    }
    std::string spare;
    require(!(stream>>spare),"unexpected field");
    return frame;
}

Decision fifo(Transition& tr,const State& start,const Group& q) {
    Decision d;
    d.exit=start;
    for (size_t i=0; i<q.size(); ++i) {
        State next;
        d.immediate+=tr.step(d.exit,q[i],next);
        d.exit=next;
        d.order.push_back(i);
        ++d.stats.current;
    }
    d.inc=d.order;
    return d;
}

Decision control(Transition& tr, const State& state, const Group& q, Policy m,
                 RankHistory& history, std::mt19937_64& rng) {
    Decision d;
    Current cur(tr,q,state,d.stats);
    int inc = cur.incumbent();
    std::vector<int> reps;
    cur.eligible(0,cur.all,inc,reps);
    d.stats.candidate_states=reps.size();
    int selected;
    if(m==Policy::RAND) {
        // Deterministic rejection sampler for an exactly uniform distinct-exit draw.
        const std::uint64_t n=reps.size(), threshold=(std::uint64_t(0)-n)%n;
        std::uint64_t x;
        do {x=rng();} while (x<threshold);
        selected=reps[x%n];
    } else {
        history.unpaired(false);
        selected=inc;
        std::int64_t best=history.score(cur.nodes[inc].state,tr.cap);
        for (int r : reps) {
            std::int64_t score=history.score(cur.nodes[r].state,tr.cap);
            bool preferred = r==inc || (selected!=inc && cur.nodes[r].code<cur.nodes[selected].code);
            if (score>best || (score==best && preferred)) {
                best=score; selected=r;
            }
        }
        history.unpaired(true);
    }
    d.order=unpack(cur.nodes[selected].code,cur.n);
    d.inc=unpack(cur.nodes[inc].code,cur.n);
    d.exit=cur.nodes[selected].state;
    d.immediate=cur.nodes[selected].work;
    d.stats.current_cache_entries=cur.nodes.size();
    d.stats.current_cache_bytes=cur.nodes.capacity()*sizeof(Node);
    return d;
}

std::string order_text(const Order& order) {
    std::string out;
    for (int id : order) out.push_back('0'+id);
    return out;
}

void replay(Policy m,int cap,int block,std::uint64_t seed,int limit) {
    require(cap>0 && cap<=MAX_CAP && block>0 && limit>0,"invalid capacity, block or limit");
    Transition tr(cap,1);
    Names names;
    State state;
    History hist(m==Policy::OPT || m==Policy::CHECK);
    RankHistory rank;
    std::mt19937_64 rng(seed);
    int seq=0;
    std::string line;
    std::cout << "stage\ti\tn\twork\tblocks\torder\tinc\tchanged\tchange_type\texits\teligible"
        "\trollouts\tdirect\tmemo_hits\tcommon\tmemo_bytes\tindex_slots\tindex_bytes\thistory_bytes\tids"
        "\tcpu_ns\twall_ns\tchoice_cpu_ns\n";
    while (seq<limit && std::getline(std::cin,line)) {
        Frame f=parse(line,cap,block);
        require(!f.warm || !seq,"warm-up after evaluation");
        const int n=f.raw.size();
        auto wall=Clock::now();
        auto cpu=cpu_ns();
        for (auto& p : f.raw) {
            int prev=0;
            for (int& id : p) {
                id=names.intern(id);
                require(names.parent[id]<0 || names.parent[id]==prev,"inconsistent node parent");
                names.parent[id]=prev;
                prev=id;
            }
        }
        tr.mark.resize(names.original.size());
        if(tr.epoch>~0u-16384u) {
            std::fill(tr.mark.begin(),tr.mark.end(),0u);
            tr.epoch=0;
        }
        if(hist.indexed) hist.membership.resize(names.original.size());
        if (m==Policy::RANK) rank.counts.resize(names.original.size());
        auto choose_time=cpu_ns();
        Decision d;
        if(f.warm || m==Policy::FCFS) d=fifo(tr,state,f.raw);
        else if(m==Policy::K || m==Policy::IMM || m==Policy::OPT || m==Policy::CHECK) {
            auto method=m==Policy::K ? Method::K : m==Policy::IMM ? Method::Immediate : Method::Optimized;
            d=decide(tr,state,f.raw,method,hist,m==Policy::CHECK);
        } else d=control(tr,state,f.raw,m,rank,rng);
        if(m==Policy::CHECK && !f.warm) {
            auto ref=decide(tr,state,f.raw,Method::Reference,hist,true);
            auto timed_rule=decide(tr,state,f.raw,Method::Optimized,hist,false);
            auto equal_decision=[&](const Decision& other) {
                return other.order==d.order && other.inc==d.inc && other.immediate==d.immediate
                    && Current::equal(other.exit,d.exit);
            };
            require(equal_decision(ref) && equal_decision(timed_rule)
                    && ref.den==d.den && ref.future==d.future,
                    "reference vs optimized integration mismatch");
        }
        auto choose_done=cpu_ns();
        std::swap(state,d.exit); // d.exit now holds same-entry state for optional offline diagnostics.
        if(hist.indexed) hist.commit(std::move(f.raw),names.original.size());
        if(m==Policy::RANK) rank.commit(std::move(f.raw),names.original.size());
        auto elapsed=cpu_ns()-cpu;
        auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-wall).count();
        int exits=d.stats.candidate_states, eligible=d.stats.eligible_orders;
        const bool enumerate=!f.warm && (hist.indexed || m==Policy::RAND || m==Policy::RANK);
        if (!enumerate) {exits=-1;eligible=-1;}
        const Group& q=hist.indexed ? hist.queue.back().paths : m==Policy::RANK ? rank.recent.back() : f.raw;
        if(enumerate && !eligible) {
            if(n==1) {exits=1;eligible=1;}
            else {
                // Startup with <2 completed groups: policy returned the incumbent.
                Counters c;
                Current cur(tr,q,d.exit,c);
                std::vector<int> reps;
                cur.eligible(0,cur.all,cur.incumbent(),reps);
                exits=reps.size();eligible=c.eligible_orders;
            }
        }
        bool changed=enumerate && d.inc!=d.order;
        std::string kind=enumerate ? "none" : "na";
        if(changed) {
            State incumbent=d.exit;
            for(int j : d.inc) {
                State next;
                tr.step(incumbent,q[j],next);
                incumbent=next;
            }
            require(!Current::equal(incumbent,state),"selected duplicate incumbent exit");
            Path a=incumbent.key(), b=state.key();
            std::sort(a.begin(),a.end());
            std::sort(b.begin(),b.end());
            kind=a==b ? "recency" : "resident";
        }
        const size_t slots=m==Policy::RANK ? rank.counts.size() : hist.membership.size();
        const size_t bytes=m==Policy::RANK ? rank.counts.capacity()*sizeof(unsigned)
                                            : hist.membership.capacity()*sizeof(uint16_t);
        const size_t history_bytes=m==Policy::RANK ? bytes+rank.group_bytes : hist.bytes();
        std::cout<<(f.warm?'W':'G')<<'\t'<<seq<<'\t'<<n<<'\t'<<f.tails+std::int64_t(block)*d.immediate<<'\t'
                 <<d.immediate<<'\t'<<order_text(d.order)<<'\t'<<order_text(d.inc)<<'\t'<<changed<<'\t'
                 <<kind<<'\t'<<exits<<'\t'<<eligible<<'\t'<<d.stats.rollouts<<'\t'<<d.stats.form_scores
                 <<'\t'<<d.stats.memo_hits<<'\t'<<d.stats.common_pairs<<'\t'<<d.stats.memo_bytes<<'\t'
                 <<slots<<'\t'<<bytes<<'\t'<<history_bytes<<'\t'<<names.original.size()-1<<'\t'<<elapsed
                 <<'\t'<<ns<<'\t'<<choose_done-choose_time<<'\n';
        if(!f.warm) ++seq;
    }
    std::int64_t active=0;
    if(hist.indexed) for(auto bits : hist.membership) active+=bits!=0;
    if(m==Policy::RANK) for(auto count : rank.counts) active+=count!=0;
    rusage usage{};
    require(getrusage(RUSAGE_SELF,&usage)==0,"process accounting unavailable");
    std::cerr << "completed_measured_cohorts=" << seq << " final_active_history_identities="
              << active << " process_peak_rss_bytes="
#ifdef __APPLE__
              << usage.ru_maxrss
#else
              << 1024LL*usage.ru_maxrss
#endif
              << '\n';
}

int main(int argc,char** argv) {
    try {
        require(argc==5 || argc==6,"expected MODE CAP BLOCK SEED [LIMIT]");
        std::ios::sync_with_stdio(false);
        std::cin.tie(nullptr);
        replay(mode(argv[1]),std::stoi(argv[2]),std::stoi(argv[3]),std::stoull(argv[4]),
               argc==6 ? std::stoi(argv[5]) : INT32_MAX);
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
