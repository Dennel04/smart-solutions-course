#include <unity.h>
#include <cstring>
#include "normal_tls.h"
#include "pressure_model.h"

struct Date { int year=2026,mon=1,day=1,hour=0,min=0,sec=0; };
struct Cert {
  Date valid_from, valid_to{2027,1,1,0,0,0};
  struct { size_t len; unsigned char* p; } raw;
  Cert* next=nullptr;
};

bool path(int mode,int depth=-1) {
  unsigned char bytes[]={1,2,3};
  Cert root{{},{2027,1,1,0,0,0},{1,bytes}}, mid{{},{2027,1,1,0,0,0},{1,bytes+1}},
       leaf{{},{2027,1,1,0,0,0},{1,bytes+2}};
  Cert* chain[]={&leaf,&mid,&root};
  if (mode==1) chain[depth]->valid_to.year=2025;
  if (mode==2) chain[depth]->valid_from.year=2027;
  return normaltls::verifyChain(&leaf,&root,"synthetic.invalid",1792756800,256,
    [&](Cert*,Cert*,const char* host,uint32_t* flags,auto cb,void* ctx) {
      TEST_ASSERT_EQUAL_STRING("synthetic.invalid",host);
      if (mode==3 || mode==4) { *flags=8; return -1; } // SDK CA/hostname refusal
      for (int i=2;i>=0;--i) {
        if (mode==5 && i==2) continue;
        uint32_t f=mode==6?16:0;
        if (cb(ctx,chain[i],i,&f)) return -1;
        *flags|=f;
      }
      return *flags?-1:0;
    });
}

void clock_requires_sync_and_valid_epoch() {
  TEST_ASSERT_FALSE(normaltls::utcValid(false,1792756800));
  TEST_ASSERT_FALSE(normaltls::utcValid(true,0));
  TEST_ASSERT_FALSE(normaltls::utcValid(true,2114380800LL));
  TEST_ASSERT_TRUE(normaltls::utcValid(true,1792756800));
}
void valid_chain_includes_anchor() { TEST_ASSERT_TRUE(path(0)); }
void expired_certificates_refused_at_each_depth() {
  for (int i=0;i<3;++i) TEST_ASSERT_FALSE(path(1,i));
}
void future_certificates_refused_at_each_depth() {
  for (int i=0;i<3;++i) TEST_ASSERT_FALSE(path(2,i));
}
void wrong_ca_or_hostname_refused() {
  TEST_ASSERT_FALSE(path(3)); TEST_ASSERT_FALSE(path(4));
}
void missing_anchor_and_existing_flags_refused() {
  TEST_ASSERT_FALSE(path(5)); TEST_ASSERT_FALSE(path(6));
}
void invalid_clock_prevents_connection_and_bearer() {
  int connections=0,writes=0,closed=0;
  int result=normaltls::connectVerified([]{return false;},[&]{++connections;return 1;},
    []{return true;},[&]{++closed;});
  if (result) ++writes;
  TEST_ASSERT_EQUAL(0,connections); TEST_ASSERT_EQUAL(0,writes); TEST_ASSERT_EQUAL(1,closed);
}
void invalid_certificate_prevents_bearer() {
  int writes=0,closed=0;
  int result=normaltls::connectVerified([]{return true;},[]{return 1;},
    []{return path(1,0);},[&]{++closed;});
  if (result) ++writes;
  TEST_ASSERT_EQUAL(0,writes); TEST_ASSERT_EQUAL(1,closed);
}
void clock_lost_during_handshake_refuses_http() {
  int clocks=0,closed=0;
  TEST_ASSERT_EQUAL(0,normaltls::connectVerified([&]{return ++clocks==1;},[]{return 1;},
    []{return true;},[&]{++closed;}));
  TEST_ASSERT_EQUAL(1,closed);
}
void confirmed_chain_allows_http() {
  TEST_ASSERT_EQUAL(1,normaltls::connectVerified([]{return true;},[]{return 1;},
    []{return path(0);},[]{}));
}
void old_calibration_does_not_confirm_sensor() {
  pressure::Calibration c;
  c.calibrated=true;c.voltsPerCount=0.001f;c.kpaPerVolt=100;
  const auto r=pressure::convertSensorReading(1234,c,false);
  TEST_ASSERT_EQUAL_STRING("sensor_not_confirmed",r.status);
  TEST_ASSERT_FALSE(r.voltageAvailable); TEST_ASSERT_FALSE(r.pressureAvailable);
  TEST_ASSERT_TRUE(pressure::convertSensorReading(1234,c,true).ok());
}
void confirmation_without_calibration_stays_uncalibrated() {
  const auto r=pressure::convertSensorReading(1234,pressure::Calibration{},true);
  TEST_ASSERT_EQUAL_STRING("not_calibrated",r.status);
  TEST_ASSERT_FALSE(r.pressureAvailable);
}
int main() {
  UNITY_BEGIN();
  RUN_TEST(clock_requires_sync_and_valid_epoch); RUN_TEST(valid_chain_includes_anchor);
  RUN_TEST(expired_certificates_refused_at_each_depth); RUN_TEST(future_certificates_refused_at_each_depth);
  RUN_TEST(wrong_ca_or_hostname_refused); RUN_TEST(missing_anchor_and_existing_flags_refused);
  RUN_TEST(invalid_clock_prevents_connection_and_bearer); RUN_TEST(invalid_certificate_prevents_bearer);
  RUN_TEST(clock_lost_during_handshake_refuses_http); RUN_TEST(confirmed_chain_allows_http);
  RUN_TEST(old_calibration_does_not_confirm_sensor); RUN_TEST(confirmation_without_calibration_stays_uncalibrated);
  return UNITY_END();
}
