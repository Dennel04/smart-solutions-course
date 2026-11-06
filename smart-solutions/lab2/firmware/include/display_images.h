#pragma once

#include <stddef.h>
#include <stdint.h>

namespace localdisplay {

constexpr size_t kImageWidth = 16;
constexpr size_t kImageHeight = 16;
constexpr int kPanelWidth = 128;
constexpr int kPanelHeight = 128;

struct Image {
  const char* id;
  const uint16_t* pixels;
  size_t count;
};

// Fixed RGB565 resources only; no URL, file, decoder or mutable storage.
const Image* findImage(const char* id);

}  // namespace localdisplay
