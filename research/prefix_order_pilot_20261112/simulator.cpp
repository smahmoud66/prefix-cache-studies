#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace std;
void ck(bool b,const char*s){if(!b)throw runtime_error(s);}
using V=vector<int>; using D=vector<double>; using S=V;
struct Req {long long raw;int L,pa;V p;};
vector<Req> r;int n,nw,M,C,MAXL; double A,B,H,working_set,ws_eval; V parentNode,depth,bmark,tmark,rankb,nextpos; int bc=0,tc=0;
D arr,fs,fe; S warm; double basework;
double mean(const D& a){return accumulate(a.begin(),a.end(),0.)/a.size();}
double quant(D a,double p){sort(a.begin(),a.end());return a.at(max(0,(int)ceil(p*a.size())-1));}
int plen(int i){return min(C,(int)r[i].p.size());}
double cost(int i,int hits){int u=r[i].L-512*hits;ck(u>0,"compulsory token");return A+u*(B+H*r[i].L);}
int mark(const S&s){++bc;for(int v:s)bmark[v]=bc;return bc;}
int hits(int i){int j=0,q=plen(i);while(j<q&&bmark[r[i].p[j]]==bc)++j;return j;}
void advance(S&s,int i){auto&p=r[i].p;int q=plen(i);if(!q)return;
 ++tc;for(int j=0;j<q;++j)tmark[p[j]]=tc;
 S v;v.reserve(min(C,q+(int)s.size()));v.insert(v.end(),p.begin(),p.begin()+q);
 for(int x:s){if((int)v.size()>=C)break;if(tmark[x]!=tc)v.push_back(x);}s.swap(v);
}
int bad(const S&base,const S&alt){mark(base);for(int j=0;j<(int)base.size();++j)rankb[base[j]]=j;
 int maxrank=-1,safe=0;for(int x:alt){int k=bmark[x]==bc?rankb[x]:INT32_MAX;if(k!=INT32_MAX&&maxrank<k)++safe;maxrank=max(maxrank,k);}return (int)base.size()-safe;}
void load(string f){
 ifstream in(f);ck(bool(in>>n>>nw)&&n>nw&&nw>=1000,"input header");r.resize(n);M=0;MAXL=0;
 for(int i=0;i<n;i++){int q;auto&z=r[i];in>>z.raw>>z.L>>z.pa>>q;ck(in&&z.L>0&&q>=0&&q<=128&&q*512<z.L&&z.pa<i&&(!i||z.raw>=r[i-1].raw),"input row");z.p.resize(q);MAXL=max(MAXL,z.L);for(int &x:z.p){in>>x;ck(in&&x>0,"node");M=max(M,x);}}
 string tail;ck(!(in>>tail),"extra row");bmark.assign(M+1,0);tmark.assign(M+1,0);rankb.resize(M+1);parentNode.assign(M+1,-1);depth.resize(M+1);
 V freq(M+1);int count=0;D pre,ev;
 for(int i=0;i<n;i++){int pr=0,level=0;for(int x:r[i].p){if(parentNode[x]==-1)parentNode[x]=pr;ck(parentNode[x]==pr,"prefix identity");depth[x]=++level;pr=x;if(!freq[x]++)++count;}if(i>=1000)for(int x:r[i-1000].p)if(!--freq[x])--count;
 if(i>=999)(i<nw?pre:ev).push_back(count);}
 working_set=quant(pre,.5);ws_eval=quant(ev,.5);
}
struct Fenwick{V z;Fenwick(int k):z(k+1){}void add(int p,int v){for(;p<(int)z.size();p+=p&-p)z[p]+=v;}int sum(int p){int v=0;for(;p;p-=p&-p)v+=z[p];return v;}};
double reuse(){int mx=0;for(int i=0;i<n;i++)mx+=plen(i);Fenwick f(mx+1);V last(M+1);D dist;int k=0,distinct=0;for(int i=0;i<n;i++)for(int j=0;j<plen(i);j++){int v=r[i].p[j];int t=last[v];if(t){if(i>=nw)dist.push_back(distinct-f.sum(t));f.add(t,-1);}else distinct++;f.add(++k,1);last[v]=k;}return dist.empty()?1e9:quant(dist,.5)/C;}
void baseline(double util){
 warm.clear();for(int i=0;i<nw;i++)advance(warm,i);
 S s=warm;D times(n);basework=0;for(int i=nw;i<n;i++){mark(s);times[i]=cost(i,hits(i));basework+=times[i];advance(s,i);}
 double span=r.back().raw-r[nw].raw;ck(span>0,"arrival span");double scale=basework/(util*span);
 arr.resize(n);fs.resize(n);fe.resize(n);double t=0;for(int i=nw;i<n;i++){arr[i]=(r[i].raw-r[nw].raw)*scale;fs[i]=max(t,arr[i]);t=fe[i]=fs[i]+times[i];}
}
struct Stat {double work=0,waitOver=0;long long u=0,steps=0;int vio=0,veto=0,changed=0,maxraw=0,maxseen=0,proposed=0; D tt,del;V order;D starts,locked;uint64_t h=1469598103934665603ULL;
 void add(int id,int hit,double start,double end,double lock,double W){int tokens=r[id].L-512*hit;work+=cost(id,hit);u+=tokens;steps+=(tokens+4095)/4096;tt.push_back(end-arr[id]);del.push_back(start-fs[id]);starts.push_back(start);locked.push_back(lock);order.push_back(id);double ov=start-fs[id]-W;vio+=ov>1e-5;waitOver=max(waitOver,ov);h=(h^(unsigned)id)*1099511628211ULL;ck(start+1e-6>=arr[id],"pre-arrival");}
 void write(){ck((int)tt.size()==n-nw,"missing");V v=order;sort(v.begin(),v.end());for(int j=0;j<(int)v.size();j++)ck(v[j]==nw+j,"membership");V at(n,-1);for(int j=0;j<(int)v.size();j++){int id=order[j];ck(r[id].pa<nw||at[r[id].pa]>=0,"precedence");at[id]=j;}
 cout<<"{\"work_ms\":"<<work<<",\"tokens\":"<<u<<",\"chunks\":"<<steps<<",\"n\":"<<tt.size()<<",\"median_ttft_ms\":"<<quant(tt,.5)<<",\"p99_ttft_ms\":"<<quant(tt,.99)<<",\"violations\":"<<vio<<",\"max_lag_ms\":"<<*max_element(del.begin(),del.end())<<",\"proposed_groups\":"<<proposed<<",\"reordered_groups\":"<<changed<<",\"vetoed_groups\":"<<veto<<",\"max_ready\":"<<maxseen<<",\"max_backlog\":"<<maxraw<<",\"order_digest\":\""<<hex<<h<<dec<<"\"}";}
};
V seq(int i,int e){V v(e-i);iota(v.begin(),v.end(),i);return v;}
int arrived(double t,int i){return upper_bound(arr.begin()+i,arr.end(),t+1e-8)-arr.begin();}
void features(int d,double rd){
 V cnt(M+1),used;double both=0,all=0,sd=0;int high=0,maxraw=0,full=0;D rawdepth;
 for(int i=nw;i<n;i++){int a=arrived(fs[i],i),e=min(a,i+d);int k=e-i;high=max(high,k);maxraw=max(maxraw,a-i);sd+=k;full+=k==d;rawdepth.push_back(a-i);
 for(int j=i;j<e;j++)for(int l=0;l<plen(j);l++){int v=r[j].p[l];if(!cnt[v]++)used.push_back(v);}
 for(int x:used){all+=cnt[x];if(cnt[x]>=2)both+=cnt[x];cnt[x]=0;}used.clear();}
 cout<<"{\"queue_sharing\":"<<(all?both/all:0)<<",\"reuse_over_capacity\":"<<rd<<",\"mean_ready\":"<<sd/(n-nw)<<",\"max_ready\":"<<high<<",\"max_backlog\":"<<maxraw<<",\"p99_backlog\":"<<quant(rawdepth,.99)<<",\"cap_reached_fraction\":"<<double(full)/(n-nw)<<",\"capacity_blocks\":"<<C<<",\"calibration_wss\":"<<working_set<<",\"measured_wss\":"<<ws_eval<<",\"realized_rho\":"<<C/max(1.,ws_eval)<<",\"fcfs_service_ms\":"<<basework<<"}";
}
struct Plan{V ids,hits;D st,en;S exit;double work=0;};
Plan plan(int i,int e,const S&entry,double t,double W,int mode){
 Plan p;p.exit=entry;V left=seq(i,e);int step=0;vector<char>served(e-i);
 while(!left.empty()){
   int oldest=left[0],best=oldest,bh=-1;mark(p.exit);
   if(mode!=0&&!(mode>=2&&mode<=4&&step%mode==0)){
     for(int id:left){int pa=r[id].pa;if(pa>=i&&!served[pa-i])continue;
       if(mode==5){if(lexicographical_compare(r[id].p.begin(),r[id].p.begin()+plen(id),r[best].p.begin(),r[best].p.begin()+plen(best)))best=id;}
       else {int h=hits(id);if(h>bh){bh=h;best=id;}}
     }
   }
   if(best!=oldest&&t+cost(best,hits(best))>fs[oldest]+W+1e-8)best=oldest;
   int h=hits(best);double dur=cost(best,h);p.work+=dur;p.st.push_back(t);t+=dur;p.en.push_back(t);p.ids.push_back(best);p.hits.push_back(h);advance(p.exit,best);
   served[best-i]=1;left.erase(find(left.begin(),left.end(),best));++step;
 }return p;
}
double futurecost(S s,int from){double z=0;for(int i=from;i<min(n,from+16);i++){mark(s);z+=cost(i,hits(i));advance(s,i);}return z;}
bool certified(const Plan&p,const S&shadow,double W,int e){
 for(size_t j=0;j<p.ids.size();j++)if(p.st[j]>fs[p.ids[j]]+W+1e-7)return false;
 if(e==n)return true;
 double debt=bad(shadow,p.exit)*512.*(B+H*MAXL);
 return max(0.,p.en.back()-fe[e-1])+debt<=W+1e-8;
}
Stat run(int mode,int d,double W){
 S s=warm,s0=warm;Stat a;double t=0;
 for(int i=nw;i<n;){t=max(t,arr[i]);int avail=arrived(t,i),e=min(avail,i+d);ck(e>i,"empty queue");a.maxraw=max(a.maxraw,avail-i);a.maxseen=max(a.maxseen,e-i);
 if(e==i+1||mode==0){
   if(mode==0)e=i+1;mark(s);int h=hits(i);double fin=t+cost(i,h);a.add(i,h,t,fin,t,W);advance(s,i);if(mode)advance(s0,i);t=fin;i=e;continue;
 }
 for(int j=i;j<e;j++)advance(s0,j);
 Plan orig=plan(i,e,s,t,W,0), chosen;
 if(mode==6){
   chosen=orig;double sb=orig.work+futurecost(orig.exit,e);
   for(int m:{1,2,4,5}){Plan x=plan(i,e,s,t,W,m);if(x.ids==chosen.ids||!certified(x,s0,W,e))continue;double sc=x.work+futurecost(x.exit,e);if(sc+1e-7<sb){sb=sc;chosen=std::move(x);}}
 }else chosen=plan(i,e,s,t,W,mode);
 if(chosen.ids!=orig.ids){a.proposed++;if(!certified(chosen,s0,W,e)){a.veto++;chosen=std::move(orig);}else a.changed++;}
 for(size_t j=0;j<chosen.ids.size();j++)a.add(chosen.ids[j],chosen.hits[j],chosen.st[j],chosen.en[j],t,W);
 t=chosen.en.back();s=std::move(chosen.exit);i=e;
 }
 ck(a.vio==0,"certified waiting guard failed");return a;
}
Stat offline(const Stat&orig,bool inf,double W,int d){
 Stat z;S s=warm;V nx(M+1,INT32_MAX);vector<V> links;
 if(!inf){links.resize(orig.order.size());
 for(int j=(int)orig.order.size()-1;j>=0;j--){int id=orig.order[j];for(int k=0;k<plen(id);k++){int v=r[id].p[k];links[j].push_back(nx[v]);nx[v]=j;}}}
 vector<char> seen(M+1);for(int x:warm)seen[x]=1;
 double t=0;
 for(int j=0;j<(int)orig.order.size();j++){int id=orig.order[j];t=max({t,orig.locked[j],arr[id]});int q=plen(id),hit=0;int pending=arrived(t,nw)-nw-j;z.maxraw=max(z.maxraw,pending);z.maxseen=max(z.maxseen,min(d,pending));
   if(inf){for(int k=0;k<q;k++){int v=r[id].p[k];hit+=seen[v];seen[v]=1;}}
   else{
    mark(s);hit=hits(id);++tc;V next,old;next.reserve(C);for(int k=0;k<q;k++){int v=r[id].p[k];nx[v]=links[j][k];next.push_back(v);tmark[v]=tc;}old.reserve(s.size());for(int x:s)if(tmark[x]!=tc)old.push_back(x);
    int free=C-q;
    if((int)old.size()>free){
     if(free){auto cmp=[&](int x,int y){return nx[x]<nx[y]||(nx[x]==nx[y]&&(depth[x]<depth[y]||(depth[x]==depth[y]&&x<y)));};
      nth_element(old.begin(),old.begin()+free,old.end(),cmp);}
     old.resize(free);
    }
    next.insert(next.end(),old.begin(),old.end());s.swap(next);
    if(j%97==0){mark(s);for(int x:s)ck(!parentNode[x]||bmark[parentNode[x]]==bc,"oracle prefix closure");}
   }
   double end=t+cost(id,hit);z.add(id,hit,t,end,orig.locked[j],W);t=end;
 }return z;
}
void fixtures(){
 S x={1,2,3,4},y={1,3,2,4};M=8;bmark.assign(9,0);rankb.resize(9);
 ck(bad(x,x)==0&&bad(x,y)==1&&bad(x,S{5,6,7,8})==4,"rank certificate example");
 // Random small complete continuations: excess misses must never exceed certificate.
 uint32_t st=17;auto rng=[&](){st=st*1664525U+1013904223U;return st;};
 for(int j=0;j<4000;j++){C=1+rng()%5;V first={1,2,3,4,5,6,7,8},second=first;
 for(int l=7;l>0;l--){swap(first[l],first[rng()%(l+1)]);swap(second[l],second[rng()%(l+1)]);}
 first.resize(C);second.resize(C);int bound=bad(first,second),loss=0;
 for(int k=0;k<16;k++){int h=1+rng()%C;V p;while((int)p.size()<h){int v=1+((rng()>>12)%8);if(find(p.begin(),p.end(),v)==p.end())p.push_back(v);}
 auto step=[&](S&s){int miss=0;S a=p;for(int v:p)miss+=find(s.begin(),s.end(),v)==s.end();for(int v:s)if(find(p.begin(),p.end(),v)==p.end())a.push_back(v);a.resize(C);s=std::move(a);return miss;};
 int m1=step(first),m2=step(second);loss+=max(0,m2-m1);ck(loss<=bound,"debt safety");}}
 cout<<"4000 cache-pair suffix fixtures passed\n";
}
int main(int argc,char**argv){try{
 if(argc==2&&string(argv[1])=="fixtures"){fixtures();return 0;}
 ck(argc==9,"args: panel phase a b c k out seed-unused");load(argv[1]);string phase=argv[2];A=stod(argv[3]);B=stod(argv[4]);H=stod(argv[5]);int onlyk=stoi(argv[6]);ofstream out(argv[7]);ck(bool(out),"output");ofstream witness;if(string(argv[8])!="-"){witness.open(argv[8],ios::binary);ck(bool(witness),"witness");}auto*stream=cout.rdbuf(out.rdbuf());cout<<setprecision(15);
 bool feat=phase=="features";ck(feat||phase=="scores","phase");
 for(double rho:{.1,.25,.5,1.}){C=max(1,(int)floor(working_set*rho+.5));double rd=feat?reuse():0;
 for(double u:{.6,.8,.95}){baseline(u);for(int d:{4,16,64}){
   if(feat){cout<<"{\"rho\":"<<rho<<",\"u\":"<<u<<",\"d\":"<<d<<",\"features\":";features(d,rd);cout<<"}\n";continue;}
   for(double W:{500.,2000.}){cout<<"{\"rho\":"<<rho<<",\"u\":"<<u<<",\"d\":"<<d<<",\"W\":"<<(int)W<<",\"policies\":{";bool first=true;
    for(auto [name,m]:vector<pair<string,int>>{{"FCFS",0},{"LPM",1},{"K2",2},{"K4",4},{"DFS",5},{"LOOK",6}}){if((m==2||m==4)&&onlyk&&onlyk!=m)continue;
      if(!first)cout<<",";first=false;Stat s=run(m,d,W);cout<<"\""<<name<<"\":";s.write();
      if(witness.is_open()&&W==500){witness<<rho<<" "<<u<<" "<<d<<" "<<name<<" "<<s.order.size()<<"\n";for(size_t j=0;j<s.order.size();j++){int32_t id=s.order[j];witness.write((char*)&id,4);witness.write((char*)&s.starts[j],8);}}
      auto joint=offline(s,false,W,d),infinite=offline(s,true,W,d);
      ck(infinite.u<=s.u&&infinite.u<=joint.u,"infinite on matched order");
      cout<<",\"MIN_"<<name<<"\":";joint.write();cout<<",\"INF_"<<name<<"\":";infinite.write();
    }cout<<"}}\n";
   }
 }}}
 cout.rdbuf(stream);return 0;
 }catch(exception const&err){cerr<<err.what()<<"\n";return 1;}}
