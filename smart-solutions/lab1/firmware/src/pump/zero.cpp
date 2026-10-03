// Copied unchanged from data-acquisition-course (data-acquisition/lab1/src/firmware, commit 7ea7afa).
#include "zero.h"
#include <Preferences.h>
#include <math.h>

namespace zero {

static Preferences prefs;

static float loadStored() {
  prefs.begin("atm", true);
  float v = prefs.getFloat("kpa", NAN);
  prefs.end();
  return v;
}

static void store(float v) {
  prefs.begin("atm", false);
  prefs.putFloat("kpa", v);
  prefs.end();
}

static bool plausible(float v) {
  return fabsf(v - kNominalKpa) <= kCommandWindowKpa;
}

float atBoot(float measured, const char** source) {
  const float stored = loadStored();
  if (!isnan(stored)) {
    if (fabsf(measured - stored) <= kBootTrackKpa) {
      store(measured);               // tube at atmosphere: follow the weather
      *source = "boot";
      return measured;
    }
    *source = "stored";              // tube not at atmosphere (vacuum/pressure held)
    return stored;
  }
  if (plausible(measured)) {         // first boot ever: trust a plausible reading
    store(measured);
    *source = "boot";
    return measured;
  }
  *source = "nominal";
  return kNominalKpa;
}

bool onCommand(float measured, bool pumpOn, float* zeroOut, const char** why) {
  if (pumpOn) {
    *why = "pump is on";
    return false;
  }
  if (!plausible(measured)) {
    *why = "reading is not near atmosphere -- open the tube";
    return false;
  }
  store(measured);
  *zeroOut = measured;
  *why = "ok";
  return true;
}

} // namespace zero
