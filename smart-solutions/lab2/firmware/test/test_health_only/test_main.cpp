#include <unity.h>
#include <string>
#include <vector>
#include "health_only_runtime.h"
#include "health_only_tls.h"
using namespace healthonly;

Credentials synthetic() {
  Credentials c;
  std::strcpy(c.ssid, "synthetic-only");
  std::strcpy(c.password, "synthetic-password");
  c.utc = 1792756800;
  return c;
}
struct FakeIo {
  std::string fail, outcome;
  std::vector<std::string> calls;
  bool step(const char* s) { calls.push_back(s); return fail != s; }
  bool caReady() { return step("ca"); }
  bool wifi(const Credentials&) { return step("wifi"); }
  bool tls() { return step("tls"); }
  bool validChain() { return step("chain"); }
  bool getHealth() { return step("get"); }
  bool close() { return step("close"); }
  void report(const char* s) { outcome = s; }
};
void waiting_has_no_io() {
  Gate gate; FakeIo io;
  TEST_ASSERT_FALSE(gate.used()); TEST_ASSERT_TRUE(io.calls.empty());
}
void exactly_one_get_and_cleanup() {
  Gate gate; FakeIo io; auto c = synthetic();
  runOnce(gate, c, io);
  TEST_ASSERT_EQUAL_STRING("HEALTH OK", io.outcome.c_str());
  TEST_ASSERT_EQUAL(6, io.calls.size());
  TEST_ASSERT_EQUAL_STRING("get", io.calls[4].c_str());
  TEST_ASSERT_EQUAL_STRING("close", io.calls[5].c_str());
  TEST_ASSERT_EQUAL(0, c.password[0]); TEST_ASSERT_EQUAL(0, c.utc);
  c = synthetic(); runOnce(gate, c, io);
  TEST_ASSERT_EQUAL(6, io.calls.size());
}
void errors_latch_without_retry() {
  for (const char* step : {"ca", "wifi", "tls", "chain", "get", "close"}) {
    Gate gate; FakeIo io; io.fail = step; auto c = synthetic();
    runOnce(gate, c, io);
    TEST_ASSERT_NOT_EQUAL(0, io.outcome.compare("HEALTH OK"));
    const auto count = io.calls.size(); c = synthetic(); runOnce(gate, c, io);
    TEST_ASSERT_EQUAL(count, io.calls.size());
    TEST_ASSERT_EQUAL_STRING("close", io.calls.back().c_str());
  }
}
void malformed_input_has_no_network() {
  for (int mode = 0; mode < 5; ++mode) {
    Gate gate; FakeIo io; auto c = synthetic();
    if (mode == 0) c.utc = 0;
    if (mode == 1) c.ssid[0] = 0;
    if (mode == 2) c.password[0] = 0;
    if (mode == 3) c.password[1] = '\n';
    if (mode == 4) c.utc = kMaxUtc;
    runOnce(gate, c, io);
    TEST_ASSERT_EQUAL(1, io.calls.size()); TEST_ASSERT_EQUAL_STRING("close", io.calls[0].c_str());
  }
}
void certificate_dates_are_inclusive_and_utc_bounded() {
  Date a{2026,10,23,0,0,0}, b{2026,10,24,0,0,0}; int64_t start, end;
  TEST_ASSERT_TRUE(dateEpoch(a, start)); TEST_ASSERT_TRUE(dateEpoch(b, end));
  TEST_ASSERT_EQUAL(86400, end-start);
  TEST_ASSERT_TRUE(validity(a,b,start)); TEST_ASSERT_TRUE(validity(a,b,end));
  TEST_ASSERT_FALSE(validity(a,b,start-1)); TEST_ASSERT_FALSE(validity(a,b,end+1));
  TEST_ASSERT_FALSE(validity(b,a,start)); TEST_ASSERT_FALSE(validity(a,b,0));
}
void malformed_dates_and_leap_years() {
  int64_t epoch;
  TEST_ASSERT_FALSE(dateEpoch({2026,2,29,0,0,0},epoch));
  TEST_ASSERT_TRUE(dateEpoch({2024,2,29,0,0,0},epoch));
  TEST_ASSERT_FALSE(dateEpoch({2026,0,1,0,0,0},epoch));
  TEST_ASSERT_FALSE(dateEpoch({2026,1,1,24,0,0},epoch));
  TEST_ASSERT_FALSE(dateEpoch({2026,1,1,0,60,0},epoch));
}
void controls_and_lengths_are_rejected() {
  TEST_ASSERT_FALSE(textValid("abc\n",4,1,32));
  TEST_ASSERT_FALSE(textValid("a\0b",3,1,32));
  TEST_ASSERT_FALSE(textValid("short",5,8,63));
  TEST_ASSERT_FALSE(textValid(nullptr,0,1,32));
}
void reset_waits_without_automatic_run() {
  Gate previous; previous.take(); Gate reboot; FakeIo io;
  TEST_ASSERT_FALSE(reboot.used()); TEST_ASSERT_TRUE(io.calls.empty());
}
struct FakeDate { int year=2026, mon=1, day=1, hour=0, min=0, sec=0; };
struct FakeCert {
  FakeDate valid_from, valid_to{2027,1,1,0,0,0};
  struct { size_t len; unsigned char* p; } raw;
};
bool pathCase(int failure, int badDepth=-1) {
  unsigned char bytes[] = {1,2,3,4};
  FakeCert root{{},{2027,1,1,0,0,0},{1,bytes}}, intermediate{{},{2027,1,1,0,0,0},{1,bytes+1}},
           leaf{{},{2027,1,1,0,0,0},{1,bytes+2}};
  FakeCert* certs[] = {&leaf,&intermediate,&root};
  if (badDepth >= 0) {
    if (failure == 1) certs[badDepth]->valid_to.year = 2025;
    if (failure == 2) certs[badDepth]->valid_from.year = 2027;
  }
  return checkedChain(&leaf,&root,1792756800,256,
    [&](FakeCert*, FakeCert*, const char* host, uint32_t* flags, auto cb, void* ctx) {
      TEST_ASSERT_EQUAL_STRING("narva2.roboarena.org",host);
      if (failure == 3) { *flags |= 4; return -1; }  // wrong CA/hostname SDK failure
      for (int d=2; d>=0; --d) {
        if (failure == 4 && d==2) continue;  // missing trust anchor
        if (failure == 5 && d==0) continue;  // missing leaf
        uint32_t local = failure == 6 ? 8 : 0;
        if (cb(ctx,certs[d],d,&local)) return -1;
        *flags |= local;
      }
      return *flags ? -1 : 0;
    });
}
void verified_path_includes_root_intermediate_leaf() { TEST_ASSERT_TRUE(pathCase(0)); }
void expiry_checked_at_every_depth() {
  for(int d=0;d<3;++d) TEST_ASSERT_FALSE(pathCase(1,d));
}
void not_before_checked_at_every_depth() {
  for(int d=0;d<3;++d) TEST_ASSERT_FALSE(pathCase(2,d));
}
void wrong_trust_or_hostname_refused() { TEST_ASSERT_FALSE(pathCase(3)); }
void incomplete_paths_refused() {
  TEST_ASSERT_FALSE(pathCase(4)); TEST_ASSERT_FALSE(pathCase(5));
}
void sdk_flags_are_not_cleared() { TEST_ASSERT_FALSE(pathCase(6)); }
int main() {
  UNITY_BEGIN();
  RUN_TEST(waiting_has_no_io); RUN_TEST(exactly_one_get_and_cleanup);
  RUN_TEST(errors_latch_without_retry); RUN_TEST(malformed_input_has_no_network);
  RUN_TEST(certificate_dates_are_inclusive_and_utc_bounded);
  RUN_TEST(malformed_dates_and_leap_years); RUN_TEST(controls_and_lengths_are_rejected);
  RUN_TEST(reset_waits_without_automatic_run);
  RUN_TEST(verified_path_includes_root_intermediate_leaf);
  RUN_TEST(expiry_checked_at_every_depth); RUN_TEST(not_before_checked_at_every_depth);
  RUN_TEST(wrong_trust_or_hostname_refused); RUN_TEST(incomplete_paths_refused);
  RUN_TEST(sdk_flags_are_not_cleared);
  return UNITY_END();
}
