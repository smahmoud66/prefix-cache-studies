// All factorial cells use the archived current-order generator, transition and k-LPM rule.
#include "frozen_evaluator.hpp"
#include <optional>

namespace factor {
using namespace matched;
enum class Mode { Full, Certificate, Sharing, Complete, Focused };

Mode parse_mode(const std::string& name) {
    if (name == "FULL" || name == "R00") return Mode::Full;
    if (name == "R10") return Mode::Certificate;
    if (name == "R01") return Mode::Sharing;
    if (name == "R11") return Mode::Complete;
    if (name == "FOCUSED") return Mode::Focused;
    throw std::runtime_error("unknown mode");
}

bool certificate(Mode m) { return m==Mode::Certificate || m==Mode::Complete || m==Mode::Focused; }
bool sharing(Mode m) { return m==Mode::Sharing || m==Mode::Complete || m==Mode::Focused; }

struct Extra {
    int64_t hist_ns=0, common_gen_ns=0;
    int64_t cert_checks=0, cert_examined_slots=0, memo_lookups=0, memo_key_words=0;
    int64_t diff_slots=0, diff_key_visits=0, common_elided=0, single_exit_shortcut=0;
    int64_t focused_initial_rank_scans=0, focused_updates=0, focused_entry_visits=0;
    size_t focused_scratch_bytes=0, differing_rank_bytes=0;
    std::vector<std::pair<int,int>> all_scores;
};

struct Trajectory {
    std::vector<Order> orders{2};
    std::vector<int> costs;
};

#include "focused_kernel.inc"

// FULL pays for historical paths only. R01 needs membership but never uses pair cardinality.
struct Store : History {
    Mode mode;
    explicit Store(Mode m): History(sharing(m)||certificate(m)), mode(m) {}
    static size_t occurrences(const Group& g) {
        size_t n=0;
        for (const auto& path:g) n+=path.size();
        return n;
    }
    size_t push(Group group, size_t cardinality) {
        size_t visits=0;
        if (indexed) {
            visits=occurrences(group);
            if (queue.size()==16) visits+=occurrences(queue.front().paths);
        }
        if (mode!=Mode::Sharing) {
            commit(std::move(group),cardinality);
            return visits;
        }
        const unsigned bit=1u<<next_slot;
        next_slot=(next_slot+1)%16;
        if (queue.size()==16) {
            for (const auto& p:queue.front().paths)
                for (int v:p) membership[v]&=~bit;
            group_bytes-=group_storage(queue.front().paths);
            queue.pop_front();
        }
        membership.resize(cardinality);
        for (const auto& p:group)
            for (int v:p) membership[v]|=bit;
        group_bytes+=group_storage(group);
        queue.push_back(HistoryItem{std::move(group),bit});
        return visits;
    }
};

struct Live {
    Mode mode;
    bool absolute;
    int cap;
    Names names;
    Transition trans;
    State state;
    Store history;
    Live(Mode m, bool abs, int c):mode(m),absolute(abs),cap(c),trans(c,1),history(m) {}
    void ensure_size() {
        trans.mark.resize(names.original.size());
        if (trans.epoch > ~0u-8192u) {
            std::fill(trans.mark.begin(),trans.mark.end(),0u);
            trans.epoch=0;
        }
        if (history.indexed) history.membership.resize(names.original.size());
    }
};

int certify(const Live& s, const State& state, const Pair& p, Counters& c, Extra& e) {
    if (!certificate(s.mode)) return -1;
    ++e.cert_checks;
    if (p.distinct<=s.cap) e.cert_examined_slots+=state.size;
    int count=closed_form(state,s.history,p,s.cap);
    if (count>=0) ++c.form_scores;
    return count;
}

int simulate(Live& s, const State& state, const Pair& p, Counters& c, Extra& e) {
    if (s.mode==Mode::Focused)
        return focused_fallback(s.trans,state,s.history,p,c,e);
    return rollout(s.trans,state,p,c);
}

void score_pair(Live& s, const Current& cur, const std::vector<int>& reps, const Pair& p,
                const RankDifferences* diff, std::vector<int>& sums, Counters& c, Extra& e) {
    if (diff && !(diff->groups&p.mask)) {
        ++c.common_pairs;
        if (!s.absolute) {
            ++e.common_elided;
            return;
        }
        const State& state=cur.nodes[reps.front()].state;
        int count=certify(s,state,p,c,e);
        if (count<0) count=simulate(s,state,p,c,e);
        for (int& total:sums) total+=count;
        return;
    }

    std::vector<ClassScore> memo;
    Path key;
    size_t words_bytes=0;
    for (size_t i=0;i<reps.size();++i) {
        const State& state=cur.nodes[reps[i]].state;
        int count=certify(s,state,p,c,e);
        if (count<0 && diff) {
            key.clear();
            size_t inspected=0;
            for (int k:diff->ranks) {
                if (k>=state.size) break;
                ++inspected;
                const int v=state.nodes[k];
                if (s.history.membership[v]&p.mask) {
                    key.push_back(k);
                    key.push_back(v);
                }
            }
            ++e.memo_lookups;
            e.diff_key_visits+=inspected;
            e.memo_key_words+=key.size();
            for (const auto& item:memo)
                if (item.key==key) {
                    ++c.memo_hits;
                    count=item.score;
                    break;
                }
            if (count<0) {
                count=simulate(s,state,p,c,e);
                memo.push_back({key,count});
                words_bytes+=memo.back().key.capacity()*sizeof(int);
            }
        } else if (count<0) {
            count=simulate(s,state,p,c,e);
        }
        sums[i]+=count;
    }
    c.memo_entries=std::max(c.memo_entries,int(memo.size()));
    c.memo_bytes=std::max(c.memo_bytes,words_bytes+memo.capacity()*sizeof(ClassScore)+key.capacity()*sizeof(int));
}

Decision select(Live& s,const Group& q,Extra& e) {
    const auto begin=cpu_ns();
    Decision d;
    Current cur(s.trans,q,s.state,d.stats);
    const int inc=cur.incumbent();
    int selected=inc;
    int pairs=int(s.history.queue.size()/2);
    d.den=std::max(1,pairs);
    std::vector<int> reps;
    if (s.absolute || (pairs && q.size()>1))
        cur.eligible(0,cur.all,inc,reps);
    else reps.push_back(inc);
    d.stats.candidate_states=reps.size();
    auto before_hist=cpu_ns();
    e.common_gen_ns=before_hist-begin;
    if (s.absolute || (pairs && reps.size()>1)) {
        std::vector<int> sums(reps.size());
        std::optional<RankDifferences> diff;
        if (pairs && sharing(s.mode)) {
            diff.emplace(cur,reps,s.history);
            e.differing_rank_bytes=diff->ranks.capacity()*sizeof(int);
            // RankDifferences compares each existing/padded rank for every exit if E>1.
            if (reps.size()>1) {
                int max_len=0;
                for (int r:reps) max_len=std::max(max_len,cur.nodes[r].state.size);
                e.diff_slots=int64_t(max_len)*reps.size();
            }
        }
        for (int end=int(s.history.queue.size());end>=2;end-=2) {
            const auto& a=s.history.queue[end-2];
            const auto& b=s.history.queue[end-1];
            Pair p{a.paths,b.paths,a.bit|b.bit,b.pair_distinct};
            score_pair(s,cur,reps,p,diff ? &*diff : nullptr,sums,d.stats,e);
        }
        size_t winner=0;
        for (size_t j=0;j<reps.size();++j) {
            if (s.absolute) e.all_scores.emplace_back(cur.nodes[reps[j]].code,sums[j]);
            bool preferred=reps[j]==inc || (reps[winner]!=inc && cur.nodes[reps[j]].code<cur.nodes[reps[winner]].code);
            if (sums[j]<sums[winner] || (sums[j]==sums[winner] && preferred)) winner=j;
        }
        selected=reps[winner];
        if (s.absolute) d.future=sums[winner];
    } else if (pairs && reps.size()==1) {
        e.single_exit_shortcut=pairs;
    }
    e.hist_ns=cpu_ns()-before_hist;
    d.order=unpack(cur.nodes[selected].code,int(q.size()));
    d.inc=unpack(cur.nodes[inc].code,int(q.size()));
    d.exit=cur.nodes[selected].state;
    d.immediate=cur.nodes[selected].work;
    d.stats.current_cache_entries=cur.nodes.size();
    d.stats.current_cache_bytes=cur.nodes.capacity()*sizeof(Node);
    return d;
}

void trace_pair(Input& in,std::ostream& out) {
    Mode mode=parse_mode(in.word());
    require(mode==Mode::Full || mode==Mode::Focused,"X requires FULL or FOCUSED");
    const int cap=in.number(1,MAX_CAP);
    const auto raw_state=in.state(cap);
    in.keyword("A");
    Group a=in.group(cap);
    in.keyword("B");
    Group b=in.group(cap);
    in.finish();
    in.valid_state(raw_state);
    State state(raw_state);
    Transition tr(cap,in.names.original.size());
    Trajectory trajectory;
    if (mode==Mode::Focused) {
        Store hist(mode);
        hist.push(std::move(a),in.names.original.size());
        hist.push(std::move(b),in.names.original.size());
        const auto& h=hist.queue;
        Pair p{h[0].paths,h[1].paths,h[0].bit|h[1].bit,h[1].pair_distinct};
        Counters c;
        Extra e;
        focused_fallback(tr,state,hist,p,c,e,&trajectory);
    } else {
        const Group* groups[]={&a,&b};
        for (unsigned h=0;h<2;++h) {
            const Group& group=*groups[h];
            unsigned mask=(1u<<group.size())-1;
            for (int slot=0;mask;++slot) {
                int i=tr.choose(group,mask,slot,state);
                State next;
                trajectory.costs.push_back(tr.step(state,group[i],next));
                trajectory.orders[h].push_back(i);
                state=next;
                mask^=1u<<i;
            }
        }
    }
    out<<"{\"orders\":["<<array(trajectory.orders[0])<<','<<array(trajectory.orders[1])
       <<"],\"costs\":"<<array(trajectory.costs)<<"}";
}

void command(const std::string& line,std::unique_ptr<Live>& live,std::ostream& out) {
    const auto begin=cpu_ns();
    std::istringstream raw(line);
    Input in{raw,{}};
    std::string op=in.word();
    if (op=="X") { trace_pair(in,out); return; }
    std::unique_ptr<Live> standalone;
    if (op=="D" || op=="R") {
        Mode mode=parse_mode(in.word());
        const int absolute=in.number(0,1);
        const int cap=in.number(1,MAX_CAP);
        standalone=std::make_unique<Live>(mode,absolute,cap);
        if (op=="R") {
            in.finish();
            live=std::move(standalone);
            out<<"{\"ok\":true}";
            return;
        }
    }
    require(op=="G" || op=="W" || op=="D","invalid operation");
    Live* s=standalone ? standalone.get() : live.get();
    require(s,"missing session");
    in.names=std::move(s->names);
    Path initial;
    if (standalone) {
        initial=in.state(s->cap);
        in.keyword("Q");
    }
    Group group=in.group(s->cap);
    if (standalone) {
        in.keyword("H");
        int count=in.number(0,16);
        for (int j=0;j<count;++j) {
            Group past=in.group(s->cap);
            s->history.push(std::move(past),in.names.original.size());
        }
        in.valid_state(initial);
        s->state=State(initial);
    }
    in.finish();
    s->names=std::move(in.names);
    s->ensure_size();
    const auto ready=cpu_ns();
    if (op=="W") {
        int work=0;
        for (const Path& path:group) {
            State next;
            work+=s->trans.step(s->state,path,next);
            s->state=next;
        }
        s->history.push(std::move(group),s->names.original.size());
        auto finish=cpu_ns();
        out<<"{\"immediate_blocks\":"<<work<<",\"parse_ns\":"<<ready-begin
           <<",\"update_ns\":"<<finish-ready<<"}";
        return;
    }
    Extra extra;
    Decision d=select(*s,group,extra);
    const auto chosen=cpu_ns();
    size_t index_visits=0;
    if (op=="G") {
        s->state=d.exit;
        index_visits=s->history.push(std::move(group),s->names.original.size());
    }
    const auto done=cpu_ns();
    Path exit;
    for (int i=0;i<d.exit.size;++i) exit.push_back(s->names.original[d.exit.nodes[i]]);
    const auto& c=d.stats;
    out<<"{\"order\":"<<array(d.order)<<",\"incumbent\":"<<array(d.inc)
       <<",\"selected_exit\":"<<array(exit)<<",\"immediate_blocks\":"<<d.immediate
       <<",\"den\":"<<d.den<<",\"future_blocks\":"<<d.future
       <<",\"objective_num\":"<<(s->absolute ? d.immediate*d.den+d.future:-1)
       <<",\"candidate_scores\":[";
    for (size_t j=0;j<extra.all_scores.size();++j) {
        if (j) out<<',';
        out<<'['<<extra.all_scores[j].first<<','<<extra.all_scores[j].second<<']';
    }
    out<<"],\"current_transitions\":"<<c.current<<",\"rollout_transitions\":"<<c.future
       <<",\"rollouts\":"<<c.rollouts<<",\"candidate_states\":"<<c.candidate_states
       <<",\"eligible_orders\":"<<c.eligible_orders<<",\"common_pairs\":"<<c.common_pairs
       <<",\"common_elided\":"<<extra.common_elided<<",\"single_exit_shortcut\":"<<extra.single_exit_shortcut
       <<",\"cert_checks\":"<<extra.cert_checks<<",\"cert_examined_slots\":"<<extra.cert_examined_slots
       <<",\"form_scores\":"<<c.form_scores<<",\"memo_lookups\":"<<extra.memo_lookups
       <<",\"memo_key_words\":"<<extra.memo_key_words<<",\"memo_hits\":"<<c.memo_hits
       <<",\"memo_entries\":"<<c.memo_entries<<",\"memo_bytes\":"<<c.memo_bytes
       <<",\"diff_slots\":"<<extra.diff_slots<<",\"diff_key_visits\":"<<extra.diff_key_visits
       <<",\"differing_rank_bytes\":"<<extra.differing_rank_bytes<<",\"index_visits\":"<<index_visits
       <<",\"focused_initial_rank_scans\":"<<extra.focused_initial_rank_scans
       <<",\"focused_updates\":"<<extra.focused_updates<<",\"focused_entry_visits\":"<<extra.focused_entry_visits
       <<",\"focused_scratch_bytes\":"<<extra.focused_scratch_bytes
       <<",\"current_cache_entries\":"<<c.current_cache_entries<<",\"current_cache_bytes\":"<<c.current_cache_bytes
       <<",\"history_bytes\":"<<s->history.bytes()<<",\"index_bytes\":"<<s->history.membership.capacity()*sizeof(uint16_t)
       <<",\"history_entries\":"<<s->history.queue.size()<<",\"interned_nodes\":"<<s->names.original.size()-1
       <<",\"parse_ns\":"<<ready-begin<<",\"cpu_ns\":"<<chosen-ready<<",\"update_ns\":"<<done-chosen
       <<",\"hist_ns\":"<<extra.hist_ns<<",\"common_gen_ns\":"<<extra.common_gen_ns<<"}";
}
} // namespace factor

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    std::unique_ptr<factor::Live> session;
    std::string line;
    try {
        while (std::getline(std::cin,line)) {
            std::ostringstream out;
            factor::command(line,session,out);
            std::cout<<out.str()<<'\n'<<std::flush;
        }
    } catch (const std::exception& e) {
        std::cout<<"{\"error\":\""<<e.what()<<"\"}"<<std::endl;
        return 1;
    }
}
