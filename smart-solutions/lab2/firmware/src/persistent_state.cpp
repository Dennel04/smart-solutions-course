#include "persistent_state.h"

namespace postoffice {

bool PersistentState::begin() {
  if (!preferences_.begin("lab2jobs", false)) return false;
  return recoverAmbiguousClaim();
}

String PersistentState::activeJobId() const {
  // A fresh device normally has no activeId key. Preferences::getString logs
  // ESP_ERR_NVS_NOT_FOUND, so guard the read instead of turning the empty
  // state into a tight-loop error message.
  if (!preferences_.isKey("activeId")) return "";
  return preferences_.getString("activeId", "");
}

PendingResult PersistentState::pendingResult() const {
  PendingResult result;
  result.present = preferences_.getBool("resultReady", false);
  if (!result.present) return result;
  result.jobId = preferences_.getString("resultId", "");
  result.status = preferences_.getString("resultStatus", "");
  result.reason = preferences_.getString("resultReason", "");
  return result;
}

bool PersistentState::canPoll() const {
  return activeJobId().isEmpty() && !pendingResult().present;
}

bool PersistentState::isDuplicate(const String& jobId) const {
  if (jobId.isEmpty()) return false;
  const PendingResult result = pendingResult();
  return activeJobId() == jobId || (result.present && result.jobId == jobId);
}

bool PersistentState::startClaim(const String& jobId) {
  if (!canPoll() || jobId.isEmpty() || jobId.length() > kMaxJobId) return false;
  return preferences_.putString("activeId", jobId) > 0;
}

bool PersistentState::queueTerminal(const String& jobId, const char* status,
                                    const String& reason) {
  if (jobId.isEmpty() || jobId.length() > kMaxJobId) return false;
  const PendingResult current = pendingResult();
  if (current.present) {
    return current.jobId == jobId && current.status == status && current.reason == reason;
  }
  const String active = activeJobId();
  if (!active.isEmpty() && active != jobId) return false;

  // Write the terminal payload first and publish resultReady last. After that
  // point it is safe to remove the active claim; a reboot can only resend the
  // same idempotent result, never repeat motion.
  bool ok = preferences_.putString("resultId", jobId) > 0;
  ok = preferences_.putString("resultStatus", status) > 0 && ok;
  preferences_.putString("resultReason", reason);
  ok = preferences_.putBool("resultReady", true) == sizeof(bool) && ok;
  if (ok) preferences_.remove("activeId");
  return ok;
}

bool PersistentState::queueDone(const String& jobId) {
  return queueTerminal(jobId, "done", "");
}

bool PersistentState::queueRefused(const String& jobId, const String& reason) {
  return queueTerminal(jobId, "refused", reason);
}

bool PersistentState::acknowledgeResult(const String& jobId) {
  const PendingResult result = pendingResult();
  if (!result.present || result.jobId != jobId) return false;
  // resultReady is cleared last, so an interrupted erase still retries rather
  // than losing an unacknowledged result.
  preferences_.remove("resultId");
  preferences_.remove("resultStatus");
  preferences_.remove("resultReason");
  preferences_.putBool("resultReady", false);
  return true;
}

bool PersistentState::recoverAmbiguousClaim() {
  const String active = activeJobId();
  if (active.isEmpty()) return true;
  const PendingResult result = pendingResult();
  if (result.present) {
    preferences_.remove("activeId");
    return true;
  }
  return queueRefused(active, "ambiguous_after_reboot");
}

}  // namespace postoffice
