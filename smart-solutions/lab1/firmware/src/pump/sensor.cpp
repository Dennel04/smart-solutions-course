// Copied unchanged from data-acquisition-course (data-acquisition/lab1/src/firmware, commit 7ea7afa).
#include "sensor.h"

namespace sensor {

void begin() {
  analogReadResolution(12);
  analogSetPinAttenuation(kAdcPin, ADC_11db);
}

int readRawAdc() {
  long sum = 0;
  for (int i = 0; i < 8; ++i) sum += analogRead(kAdcPin);
  return sum / 8;
}

float adcReferenceVolts() {
  // Measured 12.09.26 (docs/sensor_choice.md): multimeter Vout at atmosphere
  // was 0.85V (matches README's expected value) while the naive 3.3V/4095
  // formula computed ~0.758V from the same raw counts -- a consistent ~11%
  // gap reproduced across two independent readings. Back-solving gives an
  // effective reference of ~3.70V, used here instead of the nominal rail
  // voltage. Re-verify if you re-flash on different hardware.
  return 3.70f;
}

float countsToVolts(int counts) {
  return counts * (adcReferenceVolts() / kAdcMaxCounts);
}

float voltsToAbsoluteKpa(float volts) {
  return (volts / kVcc - kTransferOffset) / kTransferSlope;
}

float toRelativeKpa(float absoluteKpa, float atmosphericKpa) {
  return absoluteKpa - atmosphericKpa;
}

} // namespace sensor
