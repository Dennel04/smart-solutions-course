// Copied unchanged from data-acquisition-course (data-acquisition/lab1/src/firmware, commit 7ea7afa).
#pragma once
#include <Arduino.h>

// Atmospheric zero for the relative "p" reading.
//
// 02.10.26: the old firmware took the zero from a 32-sample average at every
// boot. Opening the USB port reboots the Atom, so a reconnect while the glass
// hung at -62 kPa made -62 the new zero and the screen read 0. The MPX5700AP
// is an absolute sensor, so the zero does not have to be re-guessed at boot:
// keep the last good value in flash (NVS) and only accept a new one when it
// is plausible.
namespace zero {

constexpr float kNominalKpa = 101.3f;   // sea-level atmosphere, absolute
constexpr float kBootTrackKpa = 2.0f;   // boot reading this close to the stored zero -> take it (weather drift)
constexpr float kCommandWindowKpa = 8.0f; // "zero" command accepted only this close to nominal

// Decide the zero at boot from a fresh reading taken with the pump off.
// Returns the zero to use; *source is "boot", "stored" or "nominal".
float atBoot(float measuredAbsKpa, const char** source);

// {"cmd":"zero"}: accept measuredAbsKpa as the new zero if the pump is off and
// the value is plausible. Returns true and stores it, or false + reason.
bool onCommand(float measuredAbsKpa, bool pumpOn, float* zeroOut, const char** why);

} // namespace zero
