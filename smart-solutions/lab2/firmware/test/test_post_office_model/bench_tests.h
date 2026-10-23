#pragma once
#include "bench_runtime.h"
#include "build_mode.h"

struct FakeBenchIo {
  // Synthetic fixtures only. No production key, device NVS or network access.
  const char* credentials = "synthetic-stored-credentials";
  const char* active = "synthetic-active-claim";
  const char* pending = "synthetic-pending-result";
  bool calibrated = true;  // bench must ignore an old saved calibration too
  bool apOk = true;
  int displays = 0, aps = 0, servers = 0, failures = 0, serves = 0;
  int pages = 0, reads = 0, samples = 0, denied = 0, missing = 0;
  void displayAndSerial() { ++displays; }
  bool protectedAp() { ++aps; return apOk; }
  void startFailed() { ++failures; }
  void localServer() { ++servers; }
  void serveLocal() { ++serves; }
  void page() { ++pages; }
  void settings() { ++reads; }
  void state() { ++reads; }
  void pressureSettings() { ++reads; }
  void pressureTest() { ++samples; }
  void blocked() { ++denied; }
  void notFound() { ++missing; }
  // Intentionally NO methods for NVS, HTTP clients, serial results or motion.
};

void test_bench_is_default_without_build_flag() {
  TEST_ASSERT_EQUAL_INT(1, BENCH_MODE);
}
void test_bench_starts_only_local_services_with_stored_jobs() {
  FakeBenchIo io;
  TEST_ASSERT_TRUE(bench::start(io));
  for (int i = 0; i < 100; ++i) bench::tick(true, io);
  TEST_ASSERT_EQUAL_INT(1, io.displays);
  TEST_ASSERT_EQUAL_INT(1, io.aps);
  TEST_ASSERT_EQUAL_INT(1, io.servers);
  TEST_ASSERT_EQUAL_INT(100, io.serves);
  TEST_ASSERT_EQUAL_STRING("synthetic-stored-credentials", io.credentials);
  TEST_ASSERT_EQUAL_STRING("synthetic-active-claim", io.active);
  TEST_ASSERT_EQUAL_STRING("synthetic-pending-result", io.pending);
  TEST_ASSERT_TRUE(io.calibrated);
}
void test_bench_ap_failure_has_no_unprotected_or_sta_fallback() {
  FakeBenchIo io;
  io.apOk = false;
  const bool ready = bench::start(io);
  TEST_ASSERT_FALSE(ready);
  bench::tick(ready, io);
  TEST_ASSERT_EQUAL_INT(1, io.failures);
  TEST_ASSERT_EQUAL_INT(0, io.servers);
  TEST_ASSERT_EQUAL_INT(0, io.serves);
}
void test_bench_get_endpoints_are_read_only() {
  FakeBenchIo io;
  for (const char* path : {"/", "/settings", "/state", "/pressure/settings"})
    bench::request(true, false, path, io);
  TEST_ASSERT_EQUAL_INT(1, io.pages);
  TEST_ASSERT_EQUAL_INT(3, io.reads);
  TEST_ASSERT_EQUAL_INT(0, io.samples);
  TEST_ASSERT_EQUAL_INT(0, io.denied);
}
void test_bench_blocks_save_health_jobs_and_serial_routes() {
  FakeBenchIo io;
  for (const char* path : {"/settings", "/pressure/settings", "/test/post-office",
                           "/api/atom/poll", "/api/atom/result", "/serial",
                           "/enable", "/pump", "/"}) {
    bench::request(false, true, path, io);
  }
  TEST_ASSERT_EQUAL_INT(9, io.denied);
  TEST_ASSERT_EQUAL_INT(0, io.samples);
  TEST_ASSERT_EQUAL_INT(0, io.reads);
  TEST_ASSERT_EQUAL_STRING("synthetic-active-claim", io.active);
  TEST_ASSERT_EQUAL_STRING("synthetic-pending-result", io.pending);
}
void test_bench_unknown_and_non_post_methods_cannot_enable_execution() {
  FakeBenchIo io;
  bench::request(true, false, "/enable", io);
  bench::request(false, false, "/settings", io);  // PUT/DELETE/etc.
  bench::request(false, false, "/test/pressure", io);
  TEST_ASSERT_EQUAL_INT(1, io.missing);
  TEST_ASSERT_EQUAL_INT(2, io.denied);
  TEST_ASSERT_EQUAL_INT(0, io.samples);
}
void test_bench_only_pressure_post_can_sample_local_input() {
  FakeBenchIo io;
  bench::request(false, true, "/test/pressure", io);
  TEST_ASSERT_EQUAL_INT(1, io.samples);
  TEST_ASSERT_EQUAL_INT(0, io.denied);
  const pressure::Reading reading = pressure::convertReading(1000, pressure::Calibration{});
  TEST_ASSERT_FALSE(reading.voltageAvailable);
  TEST_ASSERT_FALSE(reading.pressureAvailable);
  TEST_ASSERT_EQUAL_STRING("not_calibrated", reading.status);
  TEST_ASSERT_TRUE(io.calibrated);  // persistent fixture was not rewritten
}

struct FakeEntropy {
  // Synthetic bytes, deliberately not a measured entropy sample or real key.
  uint8_t bytes[8] = {0x37, 0x81, 0xe2, 0x54, 0xab, 0x09, 0xc6, 0x7d};
  bool fillOk = true, noWrite = false;
  int phase = 0;
  void enable() { TEST_ASSERT_EQUAL_INT(0, phase); phase = 1; }
  bool fill(uint8_t* output, size_t size) {
    TEST_ASSERT_EQUAL_INT(1, phase);
    phase = 2;
    if (!noWrite) std::memcpy(output, bytes, size);
    return fillOk;
  }
  void disable() { TEST_ASSERT_EQUAL_INT(2, phase); phase = 3; }
};

void test_bench_password_valid_synthetic_bytes_and_entropy_order() {
  FakeEntropy source;
  char password[64];
  TEST_ASSERT_TRUE(bench::generatePassword(source, password, sizeof(password)));
  TEST_ASSERT_EQUAL_INT(3, source.phase);
  TEST_ASSERT_EQUAL_STRING("3781e254ab09c67d", password);
}
void test_bench_password_rejects_zero_and_all_constant_buffers() {
  for (int value = 0; value <= 255; ++value) {
    FakeEntropy source;
    std::memset(source.bytes, value, sizeof(source.bytes));
    char password[64];
    std::memset(password, 'x', sizeof(password));
    TEST_ASSERT_FALSE(bench::generatePassword(source, password, sizeof(password)));
    TEST_ASSERT_EQUAL_INT(3, source.phase);
    for (char byte : password) TEST_ASSERT_EQUAL_INT(0, byte);
  }
}
void test_bench_password_rejects_repeating_and_counting_patterns() {
  const uint8_t patterns[][8] = {
      {0x12, 0x34, 0x12, 0x34, 0x12, 0x34, 0x12, 0x34},
      {0x13, 0xa4, 0x65, 0xc2, 0x13, 0xa4, 0x65, 0xc2},
      {0, 1, 2, 3, 4, 5, 6, 7}, {7, 6, 5, 4, 3, 2, 1, 0}};
  for (const auto& bytes : patterns) {
    char password[17];
    TEST_ASSERT_FALSE(bench::passwordFromBytes(bytes, 8, password, sizeof(password)));
    TEST_ASSERT_EQUAL_STRING("", password);
  }
}
void test_bench_password_rejects_malformed_buffers() {
  FakeEntropy source;
  char shortBuffer[16], password[17];
  TEST_ASSERT_FALSE(bench::passwordFromBytes(source.bytes, 8, shortBuffer, sizeof(shortBuffer)));
  TEST_ASSERT_FALSE(bench::passwordFromBytes(source.bytes, 7, password, sizeof(password)));
  TEST_ASSERT_FALSE(bench::passwordFromBytes(nullptr, 8, password, sizeof(password)));
  TEST_ASSERT_FALSE(bench::passwordFromBytes(source.bytes, 8, nullptr, 17));
}
void test_bench_entropy_failure_disables_source_and_clears_output() {
  FakeEntropy source;
  source.fillOk = false;
  char password[64];
  std::memset(password, 'x', sizeof(password));
  TEST_ASSERT_FALSE(bench::generatePassword(source, password, sizeof(password)));
  TEST_ASSERT_EQUAL_INT(3, source.phase);
  for (char byte : password) TEST_ASSERT_EQUAL_INT(0, byte);
}
void test_bench_unwritten_rng_buffer_is_rejected() {
  FakeEntropy source;
  source.noWrite = true;
  char password[17];
  TEST_ASSERT_FALSE(bench::generatePassword(source, password, sizeof(password)));
  TEST_ASSERT_EQUAL_INT(3, source.phase);
}
void test_bench_bad_entropy_stops_before_ap_and_http_start() {
  struct FailedEntropyIo : FakeBenchIo {
    bool protectedAp() {
      FakeEntropy source;
      std::memset(source.bytes, 0, sizeof(source.bytes));
      char password[17];
      if (!bench::generatePassword(source, password, sizeof(password))) return false;
      ++aps;
      return true;
    }
  } io;
  TEST_ASSERT_FALSE(bench::start(io));
  TEST_ASSERT_EQUAL_INT(0, io.aps);
  TEST_ASSERT_EQUAL_INT(0, io.servers);
  TEST_ASSERT_EQUAL_INT(1, io.failures);
}
