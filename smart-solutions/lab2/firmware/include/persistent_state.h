#pragma once

#include <Arduino.h>
#include <Preferences.h>
#include <mutex>

#include "post_office_model.h"

namespace postoffice {

struct PendingResult {
  bool present = false;
  String jobId;
  String status;
  String reason;
};

class PersistentState {
 public:
  bool begin();
  bool healthy() const {
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    return healthy_;
  }
  bool canPoll() const;
  bool isDuplicate(const String& jobId) const;
  String activeJobId() const;
  PendingResult pendingResult() const;

  bool startClaim(const String& jobId);
  bool queueDone(const String& jobId);
  bool queueRefused(const String& jobId, const String& reason);
  bool acknowledgeResult(const String& jobId);

  // Fail-safe reboot policy: a persisted active claim is never dispatched
  // again automatically. It becomes a refused result unless a terminal result
  // had already been persisted before the reboot.
  bool recoverAmbiguousClaim();

 private:
  bool fail() const { healthy_ = false; return false; }
  bool writeString(const char* key,const String& value);
  bool removeIfPresent(const char* key);
  bool finishAcknowledgement();
  bool queueTerminal(const String& jobId, const char* status, const String& reason);
  mutable Preferences preferences_;
  // Serial results and network delivery run on different ESP32 cores.
  mutable std::recursive_mutex mutex_;
  mutable bool healthy_ = false;
};

}  // namespace postoffice
