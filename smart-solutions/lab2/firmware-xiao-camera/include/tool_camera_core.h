#pragma once

#include <cstdint>

namespace tool_camera {

enum class WifiConfigError : uint8_t {
  kOk,
  kMissingSsid,
  kSsidTooLong,
  kInvalidPasswordLength,
  kInvalidHostname,
};

WifiConfigError validateWifiConfig(const char* ssid, const char* password,
                                   const char* hostname);
const char* wifiConfigErrorName(WifiConfigError error);
const char* sensorModelName(uint16_t pid);
const char* snapshotContentType();

uint32_t reconnectBackoffMs(uint32_t failed_attempts,
                            uint32_t base_ms = 1000,
                            uint32_t maximum_ms = 30000);
bool intervalElapsed(uint32_t now_ms, uint32_t previous_ms,
                     uint32_t interval_ms);

}  // namespace tool_camera
