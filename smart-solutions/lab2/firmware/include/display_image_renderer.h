#pragma once

#include "display_images.h"

namespace localdisplay {

// render is called only from the main loop. Status writes share the same lock.
bool render(const Image& image);
void showStatus(const char* heading, const char* detail);

}  // namespace localdisplay
