#pragma once

#include <stddef.h>
#include <stdint.h>

namespace postoffice {

constexpr size_t kMaxJobId = 80;
constexpr size_t kMaxJobType = 24;
constexpr uint32_t kDefaultPollIntervalMs = 1000;  // software default, not a measurement
constexpr uint32_t kMinPollIntervalMs = 250;
constexpr uint32_t kMaxPollIntervalMs = 60000;

struct Job {
  char id[kMaxJobId + 1] = {0};
  char type[kMaxJobType + 1] = {0};
  char letter = 0;
  int64_t expiresEpoch = 0;
  bool hasDirectMotionData = false;
};

enum class ValidationCode {
  Ok,
  MissingId,
  InvalidId,
  UnknownJob,
  InvalidLetter,
  DirectMotionNotAllowed,
  InvalidExpiration,
  ClockUnavailable,
  Expired,
};

struct ValidationResult {
  ValidationCode code;
  const char* reason;
  bool ok() const { return code == ValidationCode::Ok; }
};

ValidationResult validateJob(const Job& job, int64_t nowEpoch, bool clockAvailable);

struct ConfigInput {
  const char* serverUrl;
  const char* atomKey;
  uint32_t pollIntervalMs;
  bool allowDevHttp;
};

enum class ConfigCode {
  Ok,
  MissingServerUrl,
  InvalidServerUrl,
  HttpRequiresDevMode,
  MissingAtomKey,
  InvalidPollInterval,
};

struct ConfigResult {
  ConfigCode code;
  const char* reason;
  bool ok() const { return code == ConfigCode::Ok; }
};

ConfigResult validateConfig(const ConfigInput& config);

class ClaimGuard {
 public:
  bool canPoll() const;
  bool start(const char* jobId);
  bool queueResult(const char* jobId);
  bool acknowledgeResult(const char* jobId);
  bool isDuplicate(const char* jobId) const;
  void restore(const char* activeJobId, const char* pendingResultId);
  const char* activeJobId() const { return activeJobId_; }
  const char* pendingResultId() const { return pendingResultId_; }

 private:
  char activeJobId_[kMaxJobId + 1] = {0};
  char pendingResultId_[kMaxJobId + 1] = {0};
};

}  // namespace postoffice
