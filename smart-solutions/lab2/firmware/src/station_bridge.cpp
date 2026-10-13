#include "station_bridge.h"

#include <ArduinoJson.h>

namespace postoffice {

bool StationBridge::begin() {
  return preferences_.begin("lab2bridge", false);
}

bool StationBridge::dispatchJob(const Job& job, uint32_t sentAtMs) {
  const uint32_t sequence = preferences_.getUInt("seq", 0) + 1;
  if (preferences_.putUInt("seq", sequence) != sizeof(uint32_t)) return false;

  // Letters retain the Lab 1 USB fields. Pick-place carries only a predefined
  // routine name; coordinates and actuator commands never cross this boundary.
  JsonDocument document;
  if (strcmp(job.type, "letter") == 0) {
    document["letter"] = String(job.letter);
  } else {
    document["job"] = "pick_place";
    document["routine"] = job.routine;
  }
  document["session"] = "post-office";
  document["seq"] = sequence;
  document["atom_sent_ms"] = sentAtMs;
  document["job_id"] = job.id;
  serializeJson(document, Serial);
  Serial.println();
  return true;
}

bool StationBridge::handleResultLine(const String& line, PersistentState& state) {
  JsonDocument document;
  if (deserializeJson(document, line) != DeserializationError::Ok) return false;
  JsonObject result = document["post_office_result"].as<JsonObject>();
  if (result.isNull()) return false;

  const String jobId = result["id"] | "";
  const String status = result["status"] | "";
  if (jobId.isEmpty() || jobId != state.activeJobId()) return true;
  if (status == "done") {
    state.queueDone(jobId);
  } else if (status == "refused") {
    const String reason = result["reason"] | "station_refused";
    state.queueRefused(jobId, reason.substring(0, 160));
  }
  return true;
}

}  // namespace postoffice
