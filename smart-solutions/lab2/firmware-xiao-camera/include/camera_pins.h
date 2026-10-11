#pragma once

// Seeed Studio XIAO ESP32S3 Sense camera expansion-board mapping.
// Sources:
// - Seeed XIAO ESP32S3 Sense camera documentation and schematic
// - Arduino-ESP32 CameraWebServer CAMERA_MODEL_XIAO_ESP32S3 example
// Keep the D0..D7 order aligned with esp_camera camera_config_t.

constexpr int kCameraPinPwdn = -1;
constexpr int kCameraPinReset = -1;
constexpr int kCameraPinXclk = 10;
constexpr int kCameraPinSiod = 40;
constexpr int kCameraPinSioc = 39;

constexpr int kCameraPinD0 = 15;  // Y2
constexpr int kCameraPinD1 = 17;  // Y3
constexpr int kCameraPinD2 = 18;  // Y4
constexpr int kCameraPinD3 = 16;  // Y5
constexpr int kCameraPinD4 = 14;  // Y6
constexpr int kCameraPinD5 = 12;  // Y7
constexpr int kCameraPinD6 = 11;  // Y8
constexpr int kCameraPinD7 = 48;  // Y9
constexpr int kCameraPinVsync = 38;
constexpr int kCameraPinHref = 47;
constexpr int kCameraPinPclk = 13;
