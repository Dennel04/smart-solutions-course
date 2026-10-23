#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace healthonly {
constexpr char kMarker[] = "LAB2_HEALTH_ONLY=1;execution=disabled;nvs=blocked;one_get";
constexpr char kHost[] = "narva2.roboarena.org";
constexpr char kRequest[] = "GET /health HTTP/1.1\r\nHost: narva2.roboarena.org\r\n"
                            "Accept: application/json\r\nConnection: close\r\n\r\n";
constexpr int64_t kMinUtc = 1704067200LL;  // 2024-01-01, protocol sanity bounds
constexpr int64_t kMaxUtc = 2114380800LL;  // 2037-01-01, before 32-bit time_t limit
constexpr uint32_t kSessionMs = 60000;
inline bool utcValid(int64_t utc) { return utc >= kMinUtc && utc < kMaxUtc; }
inline void wipe(void* data, size_t length) {
  volatile uint8_t* p = static_cast<volatile uint8_t*>(data);
  while (length--) *p++ = 0;
}
inline bool textValid(const char* text, size_t length, size_t min, size_t max) {
  if (!text || length < min || length > max || std::strlen(text) != length) return false;
  for (size_t i = 0; i < length; ++i)
    if (static_cast<unsigned char>(text[i]) < 32 ||
        static_cast<unsigned char>(text[i]) > 126) return false;
  return true;
}
struct Credentials {
  char ssid[33]{};
  char password[64]{};
  int64_t utc = 0;
};
struct Date { int year, month, day, hour, minute, second; };
inline bool leap(int y) { return y % 4 == 0 && (y % 100 != 0 || y % 400 == 0); }
inline bool dateEpoch(Date d, int64_t& result) {
  static constexpr int days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (d.year < 1970 || d.year > 9999 || d.month < 1 || d.month > 12 ||
      d.day < 1 || d.day > days[d.month-1] + (d.month == 2 && leap(d.year)) ||
      d.hour < 0 || d.hour > 23 || d.minute < 0 || d.minute > 59 ||
      d.second < 0 || d.second > 59) return false;
  int64_t total = 0;
  for (int y = 1970; y < d.year; ++y) total += leap(y) ? 366 : 365;
  for (int m = 1; m < d.month; ++m) total += days[m-1] + (m == 2 && leap(d.year));
  result = ((total + d.day-1) * 24 + d.hour) * 3600 + d.minute * 60 + d.second;
  return true;
}
inline bool validity(Date from, Date to, int64_t now) {
  int64_t start = 0, end = 0;
  return utcValid(now) && dateEpoch(from, start) && dateEpoch(to, end) &&
         start <= end && start <= now && now <= end;
}

// One authorization attempt per boot, including malformed input/errors.
class Gate {
 public:
  bool take() { if (used_) return false; used_ = true; return true; }
  bool used() const { return used_; }
 private:
  bool used_ = false;
};

// IO has no poll, job, store, actuator, or result interface. All exits clean up.
template <class Io>
void runOnce(Gate& gate, Credentials& c, Io& io) {
  if (!gate.take()) { wipe(&c, sizeof(c)); return; }
  const char* error = nullptr;
  if (!textValid(c.ssid, std::strlen(c.ssid), 1, 32) ||
      !textValid(c.password, std::strlen(c.password), 8, 63) || !utcValid(c.utc))
    error = "INPUT ERROR";
  else if (!io.caReady()) error = "CA ERROR";
  else if (!io.wifi(c)) error = "WIFI ERROR";
  else if (!io.tls()) error = "TLS ERROR";
  else if (!io.validChain()) error = "CERT OR UTC ERROR";
  else if (!io.getHealth()) error = "HEALTH ERROR";
  if (!io.close()) error = "RADIO STOP ERROR";
  wipe(&c, sizeof(c));
  io.report(error ? error : "HEALTH OK");
}
}  // namespace healthonly
