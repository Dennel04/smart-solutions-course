#include "post_office_model.h"

#include <ctype.h>
#include <string.h>

namespace postoffice {
namespace {

bool validId(const char* value) {
  if (value == nullptr || value[0] == '\0') return false;
  const size_t length = strlen(value);
  if (length > kMaxJobId) return false;
  for (size_t i = 0; i < length; ++i) {
    const unsigned char c = static_cast<unsigned char>(value[i]);
    if (!(isalnum(c) || c == '-' || c == '_' || c == '.')) return false;
  }
  return true;
}

bool startsWith(const char* value, const char* prefix) {
  return value != nullptr && strncmp(value, prefix, strlen(prefix)) == 0;
}

void copyId(char* target, const char* source) {
  if (source == nullptr) {
    target[0] = '\0';
    return;
  }
  strncpy(target, source, kMaxJobId);
  target[kMaxJobId] = '\0';
}

}  // namespace

WifiStartupMode wifiStartupMode(bool hasStoredSsid) {
  return hasStoredSsid ? WifiStartupMode::StationAttempt
                       : WifiStartupMode::SetupAccessPoint;
}

bool shouldFallbackToSetupAccessPoint(bool stationConnected, uint32_t elapsedMs,
                                      uint32_t timeoutMs) {
  return !stationConnected && elapsedMs >= timeoutMs;
}

WifiRecoveryAction wifiRecoveryAction(bool fallbackActive, bool stationAttemptActive,
                                      bool stationConnected, uint32_t attemptElapsedMs,
                                      bool retryTimerExpired, uint32_t timeoutMs) {
  if (fallbackActive && stationConnected) return WifiRecoveryAction::RetrySucceeded;
  if (stationAttemptActive && !stationConnected && attemptElapsedMs >= timeoutMs) {
    return fallbackActive ? WifiRecoveryAction::RetryTimedOut
                          : WifiRecoveryAction::EnterFallback;
  }
  if (fallbackActive && !stationAttemptActive && retryTimerExpired) {
    return WifiRecoveryAction::StartRetry;
  }
  return WifiRecoveryAction::None;
}

ValidationResult validateJob(const Job& job, int64_t nowEpoch, bool clockAvailable) {
  if (job.id[0] == '\0') return {ValidationCode::MissingId, "missing_job_id"};
  if (!validId(job.id)) return {ValidationCode::InvalidId, "invalid_job_id"};
  if (job.hasDirectMotionData) {
    return {ValidationCode::DirectMotionNotAllowed, "direct_motion_not_allowed"};
  }
  if (strcmp(job.type, "letter") != 0) {
    return {ValidationCode::UnknownJob, "unknown_job"};
  }
  if (job.letter < 'A' || job.letter > 'Z') {
    return {ValidationCode::InvalidLetter, "invalid_letter"};
  }
  if (job.expiresEpoch <= 0) {
    return {ValidationCode::InvalidExpiration, "invalid_expiration"};
  }
  if (!clockAvailable) {
    return {ValidationCode::ClockUnavailable, "clock_unavailable"};
  }
  if (job.expiresEpoch <= nowEpoch) return {ValidationCode::Expired, "expired"};
  return {ValidationCode::Ok, "ok"};
}

ConfigResult validateConfig(const ConfigInput& config) {
  if (config.serverUrl == nullptr || config.serverUrl[0] == '\0') {
    return {ConfigCode::MissingServerUrl, "server_url_required"};
  }
  const size_t urlLength = strlen(config.serverUrl);
  if (urlLength > 200) {
    return {ConfigCode::InvalidServerUrl, "invalid_server_url"};
  }
  for (size_t i = 0; i < urlLength; ++i) {
    if (isspace(static_cast<unsigned char>(config.serverUrl[i]))) {
      return {ConfigCode::InvalidServerUrl, "invalid_server_url"};
    }
  }
  const bool https = startsWith(config.serverUrl, "https://");
  const bool http = startsWith(config.serverUrl, "http://");
  if (!https && !http) return {ConfigCode::InvalidServerUrl, "invalid_server_url"};
  const char* authority = config.serverUrl + (https ? 8 : 7);
  if (*authority == '\0' || *authority == '/' || *authority == '?' || *authority == '#') {
    return {ConfigCode::InvalidServerUrl, "invalid_server_url"};
  }
  if (http && !config.allowDevHttp) {
    return {ConfigCode::HttpRequiresDevMode, "http_requires_dev_mode"};
  }
  if (config.atomKey == nullptr || config.atomKey[0] == '\0') {
    return {ConfigCode::MissingAtomKey, "atom_key_required"};
  }
  if (config.pollIntervalMs < kMinPollIntervalMs ||
      config.pollIntervalMs > kMaxPollIntervalMs) {
    return {ConfigCode::InvalidPollInterval, "invalid_poll_interval"};
  }
  return {ConfigCode::Ok, "ok"};
}

bool ClaimGuard::canPoll() const {
  return activeJobId_[0] == '\0' && pendingResultId_[0] == '\0';
}

bool ClaimGuard::start(const char* jobId) {
  if (!canPoll() || !validId(jobId)) return false;
  copyId(activeJobId_, jobId);
  return true;
}

bool ClaimGuard::queueResult(const char* jobId) {
  if (!validId(jobId)) return false;
  if (pendingResultId_[0] != '\0') return strcmp(pendingResultId_, jobId) == 0;
  if (activeJobId_[0] != '\0' && strcmp(activeJobId_, jobId) != 0) return false;
  copyId(pendingResultId_, jobId);
  activeJobId_[0] = '\0';
  return true;
}

bool ClaimGuard::acknowledgeResult(const char* jobId) {
  if (jobId == nullptr || strcmp(pendingResultId_, jobId) != 0) return false;
  pendingResultId_[0] = '\0';
  return true;
}

bool ClaimGuard::isDuplicate(const char* jobId) const {
  if (jobId == nullptr || jobId[0] == '\0') return false;
  return strcmp(activeJobId_, jobId) == 0 || strcmp(pendingResultId_, jobId) == 0;
}

void ClaimGuard::restore(const char* activeJobId, const char* pendingResultId) {
  copyId(activeJobId_, validId(activeJobId) ? activeJobId : "");
  copyId(pendingResultId_, validId(pendingResultId) ? pendingResultId : "");
}

}  // namespace postoffice
