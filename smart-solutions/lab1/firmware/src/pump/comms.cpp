// Copied from data-acquisition-course (data-acquisition/lab1/src/firmware,
// commit 7ea7afa). Only change: the merged firmware owns the serial line
// reader (text commands and JSON share one USB port), so pollCommand() became
// parseCommand(line).
#include "comms.h"
#include <ArduinoJson.h>

namespace comms {

static const char* modeName(pump::Mode m) {
  switch (m) {
    case pump::Mode::Suction: return "suction";
    case pump::Mode::Blow: return "blow";
    default: return "off";
  }
}

void begin(unsigned long baud) { Serial.begin(baud); }

bool parseCommand(const String& line, Command& outCmd) {
  if (line.length() == 0) return false;

  JsonDocument doc; // ArduinoJson v7: no fixed capacity to size by hand
  if (deserializeJson(doc, line) != DeserializationError::Ok) return false;

  const char* cmd = doc["cmd"] | "";
  if (strcmp(cmd, "mode") == 0) {
    const char* m = doc["mode"] | "";
    outCmd.type = Command::Type::SetMode;
    if (strcmp(m, "suction") == 0) outCmd.mode = pump::Mode::Suction;
    else if (strcmp(m, "blow") == 0) outCmd.mode = pump::Mode::Blow;
    else outCmd.mode = pump::Mode::Off;
    return true;
  }
  if (strcmp(cmd, "band") == 0) {
    outCmd.type = Command::Type::SetBand;
    outCmd.band.onKpa = doc["on"] | 0.0f;
    outCmd.band.offKpa = doc["off"] | 0.0f;
    return true;
  }
  if (strcmp(cmd, "limits") == 0) {
    outCmd.type = Command::Type::SetLimits;
    outCmd.limits.minOffTimeMs = doc["minOffMs"] | 0;
    outCmd.limits.maxCyclesPerMin = doc["maxCyclesPerMin"] | 0;
    return true;
  }
  if (strcmp(cmd, "stop") == 0) {
    outCmd.type = Command::Type::Stop;
    return true;
  }
  if (strcmp(cmd, "zero") == 0) {
    outCmd.type = Command::Type::Zero;
    return true;
  }
  return false;
}

void sendTelemetry(uint32_t tMs, int adcRaw, float pKpa, pump::Mode mode,
                    bool pumpOn) {
  JsonDocument doc;
  doc["t"] = tMs;
  doc["adc"] = adcRaw;
  doc["p"] = pKpa;
  doc["mode"] = modeName(mode);
  doc["pump"] = pumpOn ? 1 : 0;
  serializeJson(doc, Serial);
  Serial.println();
}

} // namespace comms
