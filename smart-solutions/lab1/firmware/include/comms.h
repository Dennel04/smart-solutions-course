#pragma once
#include <Arduino.h>
#include "pump_logic.h"

// Wire protocol, exactly as specified in README part 4:
//   Atom -> PC:  {"t":123456,"adc":2011,"p":-52.3,"mode":"suction","pump":1}
//   PC -> Atom:  {"cmd":"mode","mode":"suction"}
//                {"cmd":"band","on":-40,"off":-60}
//                {"cmd":"limits","minOffMs":15000,"maxCyclesPerMin":4}
//                {"cmd":"stop"}
//                {"cmd":"zero"}   re-take the atmospheric zero (pump off, tube open)
namespace comms {

struct Command {
  enum class Type { None, SetMode, SetBand, SetLimits, Stop, Zero } type = Type::None;
  pump::Mode mode = pump::Mode::Off;
  pump::Band band;
  pump::SafetyLimits limits;
};

void begin(unsigned long baud);

// Parse one complete JSON command line. Malformed lines return false.
// (Merged firmware: main.cpp reads the serial port and routes lines that
// start with '{' here; the data-acquisition copy had pollCommand().)
bool parseCommand(const String& line, Command& outCmd);

void sendTelemetry(uint32_t tMs, int adcRaw, float pKpa, pump::Mode mode,
                    bool pumpOn);

} // namespace comms
