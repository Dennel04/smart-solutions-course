#pragma once
#include <cstdint>
#include <cstring>

namespace normaltls {
inline bool utcValid(bool synchronized, int64_t utc) {
  return synchronized && utc >= 1704067200LL && utc < 2114380800LL;
}
template<class Date> bool epoch(const Date& d, int64_t& out) {
  const auto leap = [](int y) { return y%4==0 && (y%100!=0 || y%400==0); };
  const int days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (d.year<1970 || d.year>9999 || d.mon<1 || d.mon>12 || d.day<1 ||
      d.day>days[d.mon-1]+(d.mon==2 && leap(d.year)) ||
      d.hour<0 || d.hour>23 || d.min<0 || d.min>59 || d.sec<0 || d.sec>59) return false;
  int64_t n=0;
  for (int y=1970;y<d.year;++y) n+=365+leap(y);
  for (int m=1;m<d.mon;++m) n+=days[m-1]+(m==2 && leap(d.year));
  out=(((n+d.day-1)*24+d.hour)*60+d.min)*60+d.sec;
  return true;
}
template<class Cert> struct Check {
  Check(Cert* r,int64_t u,uint32_t f): roots(r),utc(u),invalid(f) {}
  Cert* roots;
  int64_t utc;
  uint32_t invalid, depths=0;
  bool anchor=false;
};
template<class Cert> int certificate(void* ctx, Cert* cert, int depth, uint32_t* flags) {
  auto& c=*static_cast<Check<Cert>*>(ctx);
  if (!cert || !flags || depth<0 || depth>=8) return -1;
  c.depths|=1U<<depth;
  int64_t from=0,to=0;
  if (!epoch(cert->valid_from,from) || !epoch(cert->valid_to,to) ||
      from>to || c.utc<from || c.utc>to) *flags|=c.invalid;
  // Inspect the verifier-selected path, including the exact trust anchor.
  for (Cert* root=c.roots;root;root=root->next)
    if (cert->raw.p && root->raw.p && cert->raw.len==root->raw.len &&
        std::memcmp(cert->raw.p,root->raw.p,cert->raw.len)==0) c.anchor=true;
  return 0;  // Never clear an existing verification flag.
}
template<class Cert,class Verify>
bool verifyChain(Cert* peer,Cert* roots,const char* host,int64_t utc,
                 uint32_t invalid,Verify verify) {
  if (!peer || !roots || !host || !*host || !invalid || !utcValid(true,utc)) return false;
  Check<Cert> c{roots,utc,invalid};
  uint32_t flags=0;
  const int rc=verify(peer,roots,host,&flags,certificate<Cert>,&c);
  return rc==0 && flags==0 && c.anchor && (c.depths&1U) && c.depths>=3 &&
         (c.depths&(c.depths+1))==0;
}
// HTTPClient sees success only after all checks, before it writes any header.
template<class Clock,class Connect,class Verify,class Close>
int connectVerified(Clock clock,Connect connect,Verify verify,Close close) {
  if (!clock()) { close(); return 0; }
  if (connect()!=1) { close(); return 0; }
  if (!clock() || !verify()) { close(); return 0; }
  return 1;
}
}  // namespace normaltls
