// Copied unchanged from data-acquisition-course (data-acquisition/lab1/src/firmware, commit 7ea7afa).
#pragma once
#include <Arduino.h>

// MPX5700AP wired directly to the ADC pin -- no divider, no op-amp, no
// filter (README part 2: deliberate, Lab 2 adds those and compares).
namespace sensor {

constexpr int kAdcPin = 5;                 // AtomS3(R) "G5"
constexpr float kVcc = 5.0f;                // sensor supply -- confirm with multimeter
constexpr float kAdcMaxCounts = 4095.0f;    // 12-bit

// MPX5700AP transfer function (datasheet, absolute pressure):
//   Vout = Vcc * (0.0012858 * P_kPa + 0.04)
constexpr float kTransferSlope = 0.0012858f;
constexpr float kTransferOffset = 0.04f;

void begin();

// 8x-oversampled raw ADC count on kAdcPin.
int readRawAdc();

// The ADC reference this firmware assumes when turning counts into volts.
// THIS IS A PLACEHOLDER (3.3f, the nominal rail voltage) -- part of the
// lab's own job is measuring how far real ADC counts diverge from a
// multimeter reading of Vout and deciding what reference value (or
// correction) actually gets you within the assignment's 2% target.
// Don't treat the number below as settled; that decision + its evidence
// belongs in docs/sensor_choice.md, not hidden in firmware.
float adcReferenceVolts();

float countsToVolts(int counts);

// Inverts the transfer function above: volts -> absolute kPa.
float voltsToAbsoluteKpa(float volts);

// "p_kpa" in the assignment's wire format is pump-relative, i.e. absolute
// minus atmospheric. Measure atmospheric once (pump off, tubing open) and
// pass it in here every time.
float toRelativeKpa(float absoluteKpa, float atmosphericKpa);

} // namespace sensor
