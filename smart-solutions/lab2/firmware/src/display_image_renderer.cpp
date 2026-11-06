#include "display_image_renderer.h"

#include <M5Unified.h>
#include <mutex>

namespace localdisplay {
namespace {
std::mutex panelMutex;
bool imageVisible = false;
}

bool render(const Image& image) {
  std::lock_guard<std::mutex> lock(panelMutex);
  if (!image.pixels || image.count != kImageWidth * kImageHeight ||
      M5.Display.width() != kPanelWidth || M5.Display.height() != kPanelHeight) return false;
  M5Canvas canvas(&M5.Display);
  canvas.setColorDepth(16);
  if (!canvas.createSprite(kPanelWidth, kPanelHeight)) return false;
  for (size_t y = 0; y < kImageHeight; ++y)
    for (size_t x = 0; x < kImageWidth; ++x)
      canvas.fillRect(x * 8, y * 8, 8, 8, image.pixels[y * kImageWidth + x]);
  M5.Display.startWrite();
  canvas.pushSprite(0, 0);
  M5.Display.waitDMA();  // Finish any library DMA before committing done/freeing pixels.
  M5.Display.endWrite();
  canvas.deleteSprite();
  imageVisible = true;
  return true;  // Transfer completed; optical success still requires a real LCD test.
}

void showStatus(const char* heading, const char* detail) {
  std::lock_guard<std::mutex> lock(panelMutex);
  if (imageVisible) return;
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextColor(TFT_GREEN, TFT_BLACK);
  M5.Display.setTextSize(1);
  M5.Display.setCursor(4, 5);
  M5.Display.println(heading);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.println(detail);
}

}  // namespace localdisplay
