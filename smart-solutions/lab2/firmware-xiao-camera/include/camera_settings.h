#pragma once

#include "esp_camera.h"

namespace tool_camera {

// Software development defaults, not measured or final Lab 2 settings.
// TODO: choose final resolution/FPS after real Gridfinity readability,
// latency and bandwidth measurements.
constexpr framesize_t kFrameSize = FRAMESIZE_SVGA;
constexpr int kJpegQuality = 12;
constexpr int kFrameBufferCount = 2;
constexpr uint32_t kXclkHz = 20000000;
constexpr uint32_t kFutureStreamFpsLimit = 5;
constexpr uint32_t kCaptureMutexTimeoutMs = 2000;

}  // namespace tool_camera
