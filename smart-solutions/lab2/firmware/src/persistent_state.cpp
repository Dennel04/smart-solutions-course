#include "persistent_state.h"

namespace postoffice {

bool PersistentState::begin() {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  healthy_=preferences_.begin("lab2jobs",false);
  return healthy_ && recoverAmbiguousClaim();
}

bool PersistentState::writeString(const char* key,const String& value) {
  if (value.isEmpty() || preferences_.putString(key,value)!=value.length() ||
      preferences_.getString(key,"")!=value) return fail();
  return true;
}

bool PersistentState::removeIfPresent(const char* key) {
  if (!preferences_.isKey(key)) return true;
  if (!preferences_.remove(key) || preferences_.isKey(key)) return fail();
  return true;
}

String PersistentState::activeJobId() const {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  // A fresh device normally has no activeId key. Preferences::getString logs
  // ESP_ERR_NVS_NOT_FOUND, so guard the read instead of turning the empty
  // state into a tight-loop error message.
  if (!preferences_.isKey("activeId")) return "";
  const String id=preferences_.getString("activeId", "");
  if (id.isEmpty() || id.length()>kMaxJobId) fail();
  return id;
}

PendingResult PersistentState::pendingResult() const {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  PendingResult result;
  result.present = preferences_.getBool("resultReady", false);
  if (!result.present) return result;
  result.jobId = preferences_.getString("resultId", "");
  result.status = preferences_.getString("resultStatus", "");
  if (preferences_.isKey("resultReason"))
    result.reason = preferences_.getString("resultReason", "");
  if (result.jobId.isEmpty() || result.jobId.length()>kMaxJobId ||
      (result.status!="done" && result.status!="refused") ||
      (result.status=="refused" && result.reason.isEmpty()) ||
      (result.status=="done" && !result.reason.isEmpty())) fail();
  return result;
}

bool PersistentState::canPoll() const {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  if (!healthy_) return false;
  const String active=activeJobId();
  const PendingResult pending=pendingResult();
  return healthy_ && active.isEmpty() && !pending.present;
}

bool PersistentState::isDuplicate(const String& jobId) const {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  if (jobId.isEmpty()) return false;
  const PendingResult result = pendingResult();
  return activeJobId() == jobId || (result.present && result.jobId == jobId);
}

bool PersistentState::startClaim(const String& jobId) {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  if (!canPoll() || jobId.isEmpty() || jobId.length() > kMaxJobId) return false;
  return writeString("activeId",jobId);
}

bool PersistentState::queueTerminal(const String& jobId, const char* status,
                                    const String& reason) {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  if (!healthy_ || jobId.isEmpty() || jobId.length() > kMaxJobId ||
      (String(status)=="refused" && reason.isEmpty())) return false;
  const PendingResult current = pendingResult();
  if (!healthy_) return false;
  if (current.present) {
    return current.jobId == jobId && current.status == status && current.reason == reason;
  }
  const String active = activeJobId();
  // A late serial result must not recreate a claim after acknowledged cleanup.
  if (!healthy_ || active != jobId) return false;
  if (!writeString("resultId",jobId) || !writeString("resultStatus",status)) return false;
  if (reason.isEmpty()) {
    if (!removeIfPresent("resultReason")) return false;
  } else if (!writeString("resultReason",reason)) return false;
  if (preferences_.putBool("resultReady",true)!=sizeof(bool) ||
      !preferences_.getBool("resultReady",false)) return fail();
  // Retain activeId until the server acknowledges the terminal result.
  return true;
}

bool PersistentState::queueDone(const String& jobId) {
  return queueTerminal(jobId, "done", "");
}

bool PersistentState::queueRefused(const String& jobId, const String& reason) {
  return queueTerminal(jobId, "refused", reason);
}

bool PersistentState::acknowledgeResult(const String& jobId) {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  if (!healthy_) return false;
  const PendingResult result = pendingResult();
  if (!healthy_ || !result.present || result.jobId != jobId) return false;
  if (!writeString("ackedId",jobId)) return false;
  return finishAcknowledgement();
}

bool PersistentState::finishAcknowledgement() {
  // ackedId was committed AFTER server delivery and BEFORE any cleanup.
  const String acked=preferences_.getString("ackedId","");
  const String active=activeJobId();
  if (!healthy_ || acked.isEmpty() || acked.length()>kMaxJobId ||
      (!active.isEmpty() && active!=acked)) return fail();
  if (preferences_.isKey("resultId") &&
      preferences_.getString("resultId", "")!=acked) return fail();
  if (preferences_.putBool("resultReady",false)!=sizeof(bool) ||
      preferences_.getBool("resultReady",true)) return fail();
  for (const char* key : {"resultId","resultStatus","resultReason","activeId"})
    if (!removeIfPresent(key)) return false;
  return removeIfPresent("ackedId");
}

bool PersistentState::recoverAmbiguousClaim() {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  if (!healthy_) return false;
  if (preferences_.isKey("ackedId")) return finishAcknowledgement();
  const String active = activeJobId();
  const PendingResult result = pendingResult();
  if (!healthy_) return false;
  if (result.present) {
    if (!active.isEmpty() && active!=result.jobId) return fail();
    return true;
  }
  if (!active.isEmpty()) return queueRefused(active, "ambiguous_after_reboot");
  if (preferences_.isKey("resultId") || preferences_.isKey("resultStatus") ||
      preferences_.isKey("resultReason")) return fail();
  return true;
}

}  // namespace postoffice
