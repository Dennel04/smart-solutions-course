#include "post_office_client.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>

namespace postoffice {
namespace {

constexpr uint32_t kResultRetryMs = 2000;
constexpr int64_t kClockPlausibleAfter = 1700000000LL;

void logLine(const String& message) {
  Serial.println("# POST " + message);
}

// Gregorian civil date to Unix days, adapted from Howard Hinnant's public
// domain civil calendar algorithm. This avoids locale/timezone ambiguity.
int64_t daysFromCivil(int year, unsigned month, unsigned day) {
  year -= month <= 2;
  const int era = (year >= 0 ? year : year - 399) / 400;
  const unsigned yearOfEra = static_cast<unsigned>(year - era * 400);
  const unsigned dayOfYear =
      (153 * (month + (month > 2 ? -3 : 9)) + 2) / 5 + day - 1;
  const unsigned dayOfEra = yearOfEra * 365 + yearOfEra / 4 - yearOfEra / 100 + dayOfYear;
  return static_cast<int64_t>(era) * 146097 + static_cast<int64_t>(dayOfEra) - 719468;
}

bool parseUtc(const char* value, int64_t& epoch) {
  if (value == nullptr) return false;
  int year = 0;
  unsigned month = 0, day = 0, hour = 0, minute = 0, second = 0;
  int consumed = 0;
  if (sscanf(value, "%d-%u-%uT%u:%u:%u%n", &year, &month, &day, &hour, &minute,
             &second, &consumed) != 6) {
    return false;
  }
  const char* tail = value + consumed;
  if (*tail == '.') {
    ++tail;
    const char* fractionStart = tail;
    while (*tail >= '0' && *tail <= '9') ++tail;
    if (tail == fractionStart) return false;
  }
  if (*tail != 'Z' || tail[1] != '\0') return false;
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59 ||
      second > 60) {
    return false;
  }
  epoch = daysFromCivil(year, month, day) * 86400 + hour * 3600 + minute * 60 + second;
  return true;
}

bool hasDirectMotionField(JsonObjectConst object) {
  static const char* fields[] = {"x",       "y",       "z",      "r",
                                 "speed",   "pump",    "command", "coordinates",
                                 "trajectory", "motion"};
  for (JsonPairConst pair : object) {
    for (const char* field : fields) {
      if (strcmp(pair.key().c_str(), field) == 0) return true;
    }
  }
  return false;
}

}  // namespace

void PostOfficeClient::begin(const String& deviceId, PersistentState& state,
                             StationBridge& bridge, const char* rootCa) {
  deviceId_ = deviceId;
  state_ = &state;
  bridge_ = &bridge;
  rootCa_ = rootCa;
}

void PostOfficeClient::configure(const Settings& settings) {
  settings_ = settings;
  nextPollAtMs_ = 0;
  setStatus("configured");
}

void PostOfficeClient::setStatus(const String& value) {
  statusText_ = value;
}

String PostOfficeClient::endpoint(const String& path) const {
  String base = settings_.serverUrl;
  while (base.endsWith("/")) base.remove(base.length() - 1);
  return base + path;
}

bool PostOfficeClient::transportReady(String& reason) const {
  const ConfigInput input{settings_.serverUrl.c_str(), settings_.atomKey.c_str(),
                          settings_.pollIntervalMs, settings_.allowDevHttp};
  const ConfigResult validation = validateConfig(input);
  if (!validation.ok()) {
    reason = validation.reason;
    return false;
  }
  if (settings_.serverUrl.startsWith("https://") && rootCa_ == nullptr) {
    reason = "https_ca_not_configured";
    return false;
  }
  if (WiFi.status() != WL_CONNECTED) {
    reason = "wifi_disconnected";
    return false;
  }
  return true;
}

int PostOfficeClient::postJson(const String& path, const String& payload, String& response) {
  String reason;
  if (!transportReady(reason)) {
    setStatus(reason);
    return -1;
  }

  HTTPClient http;
  http.setConnectTimeout(1500);
  http.setTimeout(2500);
  const String url = endpoint(path);
  int code = -1;
  if (url.startsWith("https://")) {
    WiFiClientSecure client;
    client.setCACert(rootCa_);
    if (!http.begin(client, url)) return -1;
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", "Bearer " + settings_.atomKey);
    code = http.POST(payload);
    if (code > 0) response = http.getString();
    http.end();
  } else {
    WiFiClient client;
    if (!http.begin(client, url)) return -1;
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", "Bearer " + settings_.atomKey);
    code = http.POST(payload);
    if (code > 0) response = http.getString();
    http.end();
  }
  return code;
}

int PostOfficeClient::get(const String& path, String& response) {
  String reason;
  if (!transportReady(reason)) {
    setStatus(reason);
    return -1;
  }

  HTTPClient http;
  http.setConnectTimeout(1500);
  http.setTimeout(2500);
  const String url = endpoint(path);
  int code = -1;
  if (url.startsWith("https://")) {
    WiFiClientSecure client;
    client.setCACert(rootCa_);
    if (!http.begin(client, url)) return -1;
    http.addHeader("Authorization", "Bearer " + settings_.atomKey);
    code = http.GET();
    if (code > 0) response = http.getString();
    http.end();
  } else {
    WiFiClient client;
    if (!http.begin(client, url)) return -1;
    http.addHeader("Authorization", "Bearer " + settings_.atomKey);
    code = http.GET();
    if (code > 0) response = http.getString();
    http.end();
  }
  return code;
}

bool PostOfficeClient::parseJobResponse(const String& response, Job& job, bool& hasJob,
                                        String& refusalReason) {
  JsonDocument document;
  if (deserializeJson(document, response) != DeserializationError::Ok) {
    refusalReason = "invalid_server_json";
    return false;
  }
  if (document["job"].isNull()) {
    hasJob = false;
    return true;
  }
  hasJob = true;
  JsonObjectConst object = document["job"].as<JsonObjectConst>();
  JsonObjectConst argument = object["arg"].as<JsonObjectConst>();
  strlcpy(job.id, object["id"] | "", sizeof(job.id));
  strlcpy(job.type, object["job"] | "", sizeof(job.type));

  const char* letter = argument["letter"] | "";
  job.letter = strlen(letter) == 1 ? letter[0] : 0;
  job.hasDirectMotionData = hasDirectMotionField(object) || hasDirectMotionField(argument) ||
                            argument.size() != 1;
  if (!parseUtc(object["expires_at"] | nullptr, job.expiresEpoch)) {
    refusalReason = "invalid_expiration";
    return false;
  }

  const int64_t nowEpoch = static_cast<int64_t>(time(nullptr));
  const bool clockAvailable = nowEpoch >= kClockPlausibleAfter;
  const ValidationResult validation = validateJob(job, nowEpoch, clockAvailable);
  if (!validation.ok()) {
    refusalReason = validation.reason;
    return false;
  }
  return true;
}

void PostOfficeClient::pollOnce(uint32_t nowMs) {
  JsonDocument request;
  request["device_id"] = deviceId_;
  request["poll_interval_ms"] = settings_.pollIntervalMs;
  request["atom_uptime_ms"] = nowMs;
  JsonObject station = request["station"].to<JsonObject>();
  // The serial adapter exists, but station reachability has not been measured.
  station["reachable"] = false;
  station["robot_state"] = "unknown";
  String payload;
  serializeJson(request, payload);

  String response;
  const int code = postJson("/api/atom/poll", payload, response);
  if (code != 200) {
    setStatus(code > 0 ? "poll_http_" + String(code) : "poll_failed");
    logLine(statusText_);
    return;
  }

  Job job;
  bool hasJob = false;
  String refusalReason;
  if (!parseJobResponse(response, job, hasJob, refusalReason)) {
    // The server has already claimed a response job. If an ID is available,
    // report a terminal refusal rather than silently dropping it.
    if (job.id[0] != '\0') state_->queueRefused(job.id, refusalReason);
    setStatus("job_refused:" + refusalReason);
    logLine(statusText_);
    return;
  }
  if (!hasJob) {
    setStatus("poll_ok_no_job");
    return;
  }

  logLine("received id=" + String(job.id) + " type=" + String(job.type));
  if (state_->isDuplicate(job.id)) {
    state_->queueRefused(job.id, "duplicate_job");
    setStatus("duplicate_job");
    return;
  }
  if (!state_->startClaim(job.id)) {
    state_->queueRefused(job.id, "claim_state_conflict");
    setStatus("claim_state_conflict");
    return;
  }
  if (!bridge_->dispatchLetter(job, nowMs)) {
    state_->queueRefused(job.id, "station_dispatch_failed");
    setStatus("station_dispatch_failed");
    return;
  }
  setStatus("awaiting_station_result");
  logLine("dispatched id=" + String(job.id) + " to local station boundary");
}

void PostOfficeClient::sendPendingResult(uint32_t nowMs) {
  const PendingResult pending = state_->pendingResult();
  if (!pending.present) return;

  JsonDocument document;
  document["id"] = pending.jobId;
  document["status"] = pending.status;
  if (pending.status == "done") {
    document["result"]["source"] = "local_station";
  } else {
    document["reason"] = pending.reason;
  }
  String payload;
  serializeJson(document, payload);

  String response;
  const int code = postJson("/api/atom/result", payload, response);
  if (code == 200) {
    state_->acknowledgeResult(pending.jobId);
    setStatus("result_sent");
    logLine("result sent id=" + pending.jobId);
  } else {
    nextResultAttemptAtMs_ = nowMs + kResultRetryMs;
    setStatus(code > 0 ? "result_http_" + String(code) : "result_retry_wait");
    logLine("result retained id=" + pending.jobId + " status=" + statusText_);
  }
}

void PostOfficeClient::tick(uint32_t nowMs) {
  if (state_ == nullptr || bridge_ == nullptr) return;
  if (state_->pendingResult().present) {
    if (static_cast<int32_t>(nowMs - nextResultAttemptAtMs_) >= 0) {
      sendPendingResult(nowMs);
    }
    return;
  }
  if (!state_->activeJobId().isEmpty()) return;
  if (static_cast<int32_t>(nowMs - nextPollAtMs_) < 0) return;
  nextPollAtMs_ = nowMs + settings_.pollIntervalMs;
  pollOnce(nowMs);
}

String PostOfficeClient::testConnection() {
  String response;
  const int code = get("/health", response);
  if (code == 200) return "health_ok";
  return code > 0 ? "health_http_" + String(code) : statusText_;
}

}  // namespace postoffice
