#pragma once

#include <cstring>
#include <cstdint>
#include <initializer_list>

namespace bench {

constexpr char kBuildMarker[] = "LAB2_BENCH_MODE=1;execution=disabled;nvs=blocked";
constexpr char kSsid[] = "Lab2AtomBench";

inline void clearSecret(void* data, size_t size) {
  volatile uint8_t* bytes = static_cast<volatile uint8_t*>(data);
  while (size--) *bytes++ = 0;  // do not optimise away the wipe
}

// A stuck/patterned buffer is a fault, not a fallback password. These checks
// detect obvious faults; passing them is NOT proof of hardware entropy.
inline bool passwordFromBytes(const uint8_t* bytes, size_t size,
                              char* password, size_t capacity) {
  if (password == nullptr || capacity == 0) return false;
  clearSecret(password, capacity);
  if (bytes == nullptr || size != 8 || capacity < 17) return false;
  for (size_t period : {size_t(1), size_t(2), size_t(4)}) {
    bool repeated = true;
    for (size_t i = period; i < size; ++i)
      repeated = repeated && bytes[i] == bytes[i % period];
    if (repeated) return false;
  }
  bool ascending = true, descending = true;
  for (size_t i = 1; i < size; ++i) {
    ascending = ascending && bytes[i] == static_cast<uint8_t>(bytes[i - 1] + 1);
    descending = descending && bytes[i] == static_cast<uint8_t>(bytes[i - 1] - 1);
  }
  if (ascending || descending) return false;
  constexpr char hex[] = "0123456789abcdef";
  for (size_t i = 0; i < size; ++i) {
    password[i * 2] = hex[bytes[i] >> 4];
    password[i * 2 + 1] = hex[bytes[i] & 15];
  }
  return true;  // NUL terminator was set by clearSecret
}

template <class Entropy>
bool generatePassword(Entropy& source, char* password, size_t capacity) {
  uint8_t bytes[8]{};
  source.enable();
  const bool filled = source.fill(bytes, sizeof(bytes));
  source.disable();  // even on a synthetic fill failure, before any Wi-Fi/ADC
  const bool valid = filled && passwordFromBytes(bytes, sizeof(bytes), password, capacity);
  if (!valid && password != nullptr) clearSecret(password, capacity);
  clearSecret(bytes, sizeof(bytes));
  return valid;
}

// This interface intentionally has no store, transport, job or actuator API.
// The same dispatch is exercised on the host with synthetic persistent state.
template <class LocalIo>
void request(bool get, bool post, const char* path, LocalIo& io) {
  if (get && std::strcmp(path, "/") == 0) io.page();
  else if (get && std::strcmp(path, "/settings") == 0) io.settings();
  else if (get && std::strcmp(path, "/state") == 0) io.state();
  else if (get && std::strcmp(path, "/pressure/settings") == 0) io.pressureSettings();
  else if (post && std::strcmp(path, "/test/pressure") == 0) io.pressureTest();
  else if (!get) io.blocked();
  else io.notFound();
}

template <class LocalIo>
bool start(LocalIo& io) {
  io.displayAndSerial();
  if (!io.protectedAp()) {
    io.startFailed();
    return false;  // no unprotected AP or alternate STA fallback
  }
  io.localServer();
  return true;
}

template <class LocalIo>
void tick(bool ready, LocalIo& io) {
  if (ready) io.serveLocal();
  // No serial reads, recovery, polling, pending-result retry or job dispatch.
}

}  // namespace bench
