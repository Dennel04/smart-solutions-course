#include <unity.h>

#include <cstdint>
#include <cstring>

#include "tool_camera_core.h"

using tool_camera::WifiConfigError;

void test_wifi_config_rejects_missing_and_invalid_values() {
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(WifiConfigError::kMissingSsid),
      static_cast<int>(tool_camera::validateWifiConfig(
          "", "", "lab2-tool-camera")));
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(WifiConfigError::kInvalidPasswordLength),
      static_cast<int>(tool_camera::validateWifiConfig(
          "lab-network", "short", "lab2-tool-camera")));
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(WifiConfigError::kInvalidHostname),
      static_cast<int>(tool_camera::validateWifiConfig(
          "lab-network", "valid-password", "bad host")));
}

void test_wifi_config_accepts_private_and_open_networks() {
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(WifiConfigError::kOk),
      static_cast<int>(tool_camera::validateWifiConfig(
          "lab-network", "valid-password", "lab2-tool-camera")));
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(WifiConfigError::kOk),
      static_cast<int>(
          tool_camera::validateWifiConfig("isolated-open-lab", "", "")));
}

void test_sensor_names_cover_supported_xiao_revisions() {
  TEST_ASSERT_EQUAL_STRING("OV2640", tool_camera::sensorModelName(0x0026));
  TEST_ASSERT_EQUAL_STRING("OV3660", tool_camera::sensorModelName(0x3660));
  TEST_ASSERT_EQUAL_STRING("OV5640", tool_camera::sensorModelName(0x5640));
  TEST_ASSERT_EQUAL_STRING("unknown", tool_camera::sensorModelName(0xffff));
}

void test_snapshot_contract_uses_jpeg_content_type() {
  TEST_ASSERT_EQUAL_STRING("image/jpeg", tool_camera::snapshotContentType());
}

void test_reconnect_backoff_is_bounded() {
  TEST_ASSERT_EQUAL_UINT32(1000, tool_camera::reconnectBackoffMs(0));
  TEST_ASSERT_EQUAL_UINT32(2000, tool_camera::reconnectBackoffMs(1));
  TEST_ASSERT_EQUAL_UINT32(16000, tool_camera::reconnectBackoffMs(4));
  TEST_ASSERT_EQUAL_UINT32(30000, tool_camera::reconnectBackoffMs(5));
  TEST_ASSERT_EQUAL_UINT32(30000, tool_camera::reconnectBackoffMs(100));
}

void test_elapsed_time_handles_millis_wraparound() {
  const uint32_t previous = 0xfffffff0U;
  TEST_ASSERT_FALSE(tool_camera::intervalElapsed(0x00000003U, previous, 20));
  TEST_ASSERT_TRUE(tool_camera::intervalElapsed(0x00000004U, previous, 20));
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_wifi_config_rejects_missing_and_invalid_values);
  RUN_TEST(test_wifi_config_accepts_private_and_open_networks);
  RUN_TEST(test_sensor_names_cover_supported_xiao_revisions);
  RUN_TEST(test_snapshot_contract_uses_jpeg_content_type);
  RUN_TEST(test_reconnect_backoff_is_bounded);
  RUN_TEST(test_elapsed_time_handles_millis_wraparound);
  return UNITY_END();
}
