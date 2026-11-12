// Included inside namespace factor, after the matched transition and profiling types.
// A resident tracked x has |Y_x| = rank(x)-1. The tracked identities preceding x
// identify Y_x intersect U. The remaining count is exactly |Y_x minus U|. Outsider
// identities are never requested in the pair. Gaps in the original ranks must survive.
struct FocusedSlots {
    int count;
    std::array<int, MAX_CAP> ids;
    std::array<int, MAX_CAP> ranks;
};

int focused_fallback(Transition& tr, const State& entry, const History& history,
                     const Pair& pair, Counters& stats, Extra& ex, Trajectory* debug=nullptr) {
    ++stats.rollouts;
    if (debug) debug->orders.resize(2);
    FocusedSlots buffers[2];
    FocusedSlots* active=&buffers[0];
    FocusedSlots* next=&buffers[1];
    active->count=0;
    ex.focused_scratch_bytes=std::max(ex.focused_scratch_bytes,sizeof(buffers));
    ex.focused_initial_rank_scans+=entry.size;
    for (int k=0; k<entry.size; ++k) {
        const int id=entry.nodes[k];
        if (history.membership[id] & pair.mask) {
            active->ids[active->count]=id;
            active->ranks[active->count++]=k+1;
        }
    }

    int cost=0;
    const Group* groups[2]={&pair.a,&pair.b};
    for (int h=0; h<2; ++h) {
        const Group& group=*groups[h];
        unsigned pending=(1u<<group.size())-1;
        for (int pos=0; pending; ++pos) {
            int selected=__builtin_ctz(pending);
            if ((pos%2) && (pending & (pending-1))) {
                // Every candidate path is in U, so focused membership gives hit prefixes.
                ++tr.epoch;
                ex.focused_entry_visits+=active->count;
                for (int j=0; j<active->count; ++j) tr.mark[active->ids[j]]=tr.epoch;
                int best=-1;
                for (unsigned choices=pending; choices; choices &= choices-1) {
                    const int i=__builtin_ctz(choices);
                    const Path& path=group[i];
                    int lo=0, hi=static_cast<int>(path.size());
                    while (lo<hi) {
                        const int mid=(lo+hi)/2;
                        if (tr.mark[path[mid]]==tr.epoch) lo=mid+1;
                        else hi=mid;
                    }
                    if (lo>best) { best=lo; selected=i; }
                }
            }

            const Path& path=group[selected];
            const int length=static_cast<int>(path.size());
            ++tr.epoch;
            next->count=length;
            for (int j=0; j<length; ++j) {
                tr.mark[path[j]]=tr.epoch;
                next->ids[j]=path[j];
                next->ranks[j]=j+1;
            }
            // Simultaneous entry charging. For each untouched resident, subtract
            // touched residents originally ahead, then prepend the complete path.
            int hits=0;
            ex.focused_entry_visits+=active->count;
            for (int j=0; j<active->count; ++j) {
                const int id=active->ids[j];
                if (tr.mark[id]==tr.epoch) {
                    ++hits;
                } else {
                    const int rank=active->ranks[j]+length-hits;
                    if (rank<=tr.cap) {
                        next->ids[next->count]=id;
                        next->ranks[next->count++]=rank;
                    }
                }
            }
            const int misses=length-hits;
            cost+=misses;
            if (debug) {
                debug->orders[h].push_back(selected);
                debug->costs.push_back(misses);
            }
            std::swap(active,next);
            pending ^= 1u<<selected;
            ++ex.focused_updates;
            ++stats.future;
        }
    }
    return cost;
}
