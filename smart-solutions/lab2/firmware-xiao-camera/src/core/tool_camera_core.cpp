#include "tool_camera_core.h"

#include <cstring>

namespace tool_camera {
namespace {

bool validHostname(const char* hostname) {
  if (hostname == nullptr || hostname[0] == '\0') {
    return true;
  }
  const size_t length = std::strlen(hostname);
  if (length > 63 || hostname[0] == '-' || hostname[length - 1] == '-') {
    return false;
  }
  for (size_t index = 0; index < length; ++index) {
    const char value = hostname[index];
    const bool valid = (value >= 'a' && value <= 'z') ||
                       (value >= 'A' && value <= 'Z') ||
                       (value >= '0' && value <= '9') || value == '-';
    if (!valid) {
      return false;
    }
  }
  return true;
}

}  // namespace

WifiConfigError validateWifiConfig(const char* ssid, const char* password,
                                   const char* hostname) {
  if (ssid == nullptr || ssid[0] == '\0') {
    return WifiConfigError::kMissingSsid;
  }
  if (std::strlen(ssid) > 32) {
    return WifiConfigError::kSsidTooLong;
  }
  const size_t password_length = password == nullptr ? 0 : std::strlen(password);
  if (password_length != 0 && (password_length < 8 || password_length > 63)) {
    return WifiConfigError::kInvalidPasswordLength;
  }
  if (!validHostname(hostname)) {
    return WifiConfigError::kInvalidHostname;
  }
  return WifiConfigError::kOk;
}

const char* wifiConfigErrorName(WifiConfigError error) {
  switch (error) {
    case WifiConfigError::kOk:
      return "ok";
    case WifiConfigError::kMissingSsid:
      return "missing_ssid";
    case WifiConfigError::kSsidTooLong:
      return "ssid_too_long";
    case WifiConfigError::kInvalidPasswordLength:
      return "invalid_password_length";
    case WifiConfigError::kInvalidHostname:
      return "invalid_hostname";
  }
  return "unknown";
}

const char* sensorModelName(uint16_t pid) {
  switch (pid) {
    case 0x0026:
      return "OV2640";
    case 0x3660:
      return "OV3660";
    case 0x5640:
      return "OV5640";
    default:
      return "unknown";
  }
}

const char* snapshotContentType() { return "image/jpeg"; }

uint32_t reconnectBackoffMs(uint32_t failed_attempts, uint32_t base_ms,
                            uint32_t maximum_ms) {
  if (base_ms == 0 || maximum_ms == 0) {
    return 0;
  }
  uint32_t delay = base_ms > maximum_ms ? maximum_ms : base_ms;
  for (uint32_t attempt = 0; attempt < failed_attempts && delay < maximum_ms;
       ++attempt) {
    if (delay > maximum_ms / 2) {
      return maximum_ms;
    }
    delay *= 2;
  }
  return delay > maximum_ms ? maximum_ms : delay;
}

bool intervalElapsed(uint32_t now_ms, uint32_t previous_ms,
                     uint32_t interval_ms) {
  return static_cast<uint32_t>(now_ms - previous_ms) >= interval_ms;
}

}  // namespace tool_camera
