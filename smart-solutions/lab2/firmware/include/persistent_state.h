#pragma once

#include <Arduino.h>
#include <Preferences.h>

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
  bool queueTerminal(const String& jobId, const char* status, const String& reason);
  mutable Preferences preferences_;
};

}  // namespace postoffice
