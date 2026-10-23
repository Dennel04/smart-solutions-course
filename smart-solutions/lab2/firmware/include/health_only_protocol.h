#pragma once
#include <ArduinoJson.h>
#include "health_only_runtime.h"

namespace healthonly {
inline bool oneObject(const char* text) {
  if (!text) return false;
  while (*text == ' ' || *text == '\t' || *text == '\r' || *text == '\n') ++text;
  if (*text != '{') return false;
  int depth = 0; bool quoted = false, escape = false, ended = false;
  for (; *text; ++text) {
    const char c = *text;
    if (ended) {
      if (c != ' ' && c != '\t' && c != '\r' && c != '\n') return false;
    } else if (quoted) {
      if (escape) escape = false;
      else if (c == '\\') escape = true;
      else if (c == '"') quoted = false;
    } else if (c == '"') quoted = true;
    else if (c == '{') ++depth;
    else if (c == '}' && --depth == 0) ended = true;
  }
  return ended && !quoted;
}
// Mutable frame enables zero-copy decoding; caller wipes the entire buffer.
inline bool parseFrame(char* frame, const char* nonce, Credentials& out) {
  JsonDocument json;
  if (!frame || std::strlen(frame) > 510 || !oneObject(frame) ||
      deserializeJson(json, frame) != DeserializationError::Ok ||
      !json.is<JsonObject>() || json.size() != 6 ||
      !json["action"].is<const char*>() || !json["challenge"].is<const char*>() ||
      !json["ssid"].is<const char*>() || !json["password"].is<const char*>() ||
      !json["utc"].is<int64_t>() || !json["confirm"].is<bool>() ||
      !json["confirm"].as<bool>()) return false;
  const JsonString action = json["action"], challenge = json["challenge"],
                   ssid = json["ssid"], password = json["password"];
  if (action.size() != 11 || std::strcmp(action.c_str(), "health_once") ||
      challenge.size() != 16 || std::strcmp(challenge.c_str(), nonce) ||
      !textValid(ssid.c_str(), ssid.size(), 1, 32) ||
      !textValid(password.c_str(), password.size(), 8, 63) ||
      !utcValid(json["utc"].as<int64_t>())) return false;
  std::memcpy(out.ssid, ssid.c_str(), ssid.size());
  std::memcpy(out.password, password.c_str(), password.size());
  out.utc = json["utc"].as<int64_t>();
  return true;
}

inline bool responseValid(char* response, size_t n) {
  if (!response || n == 0 || n > 2048 || std::strlen(response) != n) return false;
  char* body = std::strstr(response, "\r\n\r\n");
  if (!body || (std::strncmp(response, "HTTP/1.1 200 ", 13) != 0 &&
                std::strncmp(response, "HTTP/1.0 200 ", 13) != 0)) return false;
  for (char* p = response; p < body; ++p)
    if (*p >= 'A' && *p <= 'Z') *p += 'a' - 'A';
  // Only unambiguous, non-chunked framing. Fail closed rather than retry.
  const char* type = std::strstr(response, "\r\ncontent-type: application/json");
  if (std::strstr(response, "transfer-encoding:") || !type) return false;
  const char next = type[std::strlen("\r\ncontent-type: application/json")];
  if (next != '\r' && next != ';') return false;
  const char* length = std::strstr(response, "\r\ncontent-length: ");
  if (!length || std::strstr(length+2, "\r\ncontent-length:")) return false;
  length += std::strlen("\r\ncontent-length: ");
  size_t expected = 0;
  if (*length < '0' || *length > '9') return false;
  while (*length >= '0' && *length <= '9') {
    expected = expected*10 + (*length++ - '0');
    if (expected > 256) return false;
  }
  if (*length != '\r' || length[1] != '\n' || expected != std::strlen(body+4)) return false;
  *body = '\0';
  JsonDocument json;
  if (!oneObject(body+4) || deserializeJson(json, body+4) != DeserializationError::Ok) return false;
  return json.is<JsonObject>() && json.size() == 2 && json["ok"].is<bool>() &&
      json["ok"].as<bool>() && json["service"].is<const char*>() &&
      json["service"].as<JsonString>().size() == 16 &&
      std::strcmp(json["service"].as<const char*>(), "lab2-post-office") == 0;
}
}  // namespace healthonly
