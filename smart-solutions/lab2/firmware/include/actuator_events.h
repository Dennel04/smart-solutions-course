#pragma once

#include "actuator_model.h"

namespace actuator {

using SessionId = std::uint64_t;

enum class Delivery { NoEvents, Delivered, WrongSession, FaultLocked };

// Native simulation only. All calls must be serialized by the caller; this
// is neither thread-safe nor ISR-safe and cannot physically turn off a load.
// Use one inbox per model/boot generation, with a session ID never reused
// while old events can exist. An in-place Model::reboot is not a new session.
class EventInbox {
 public:
  explicit EventInbox(SessionId session) : session_(session) {}
  EventInbox(const EventInbox&) = delete;
  EventInbox& operator=(const EventInbox&) = delete;

  // Timer owner: register once on arm, release on disarm. A second registration
  // cannot overwrite the single slot, even if it uses the same ID.
  bool expectTimeout(OperationId id) {
    if (fault_) return false;
    if (id == 0 || timerId_ != 0) {
      fault_ = true;
      return false;
    }
    timerId_ = id;
    return true;
  }

  void forgetTimeout(OperationId id) {
    if (id == timerId_) {
      timerId_ = 0;
      timeoutPending_ = false;
    }
  }

  // Producers capture events only; they have no Model reference.
  void postTimeout(SessionId session, OperationId id) {
    if (session == session_ && id != 0 && id == timerId_) timeoutPending_ = true;
  }

  void postComparatorLevel(SessionId session, bool active) {
    if (session != session_) return;
    comparator_ = active ? Comparator::Active : Comparator::Inactive;
    tripPending_ = tripPending_ || active;
  }

  void postDeliveryFailure(SessionId session) {
    if (session == session_) fault_ = true;
  }

  // Consumer only: drain before servicing starts or local clear. All
  // comparator observations must go through this boundary. The model's
  // existing comparator lock is also the fail-closed representation of
  // unknown input after a delivery fault; FaultLocked distinguishes it.
  // A fault stays sticky for this inbox; a normal inactive sample cannot
  // recover it. Recovery requires a new session and normal local unlock.
  Delivery deliver(SessionId modelSession, Model& model) {
    if (modelSession != session_) return Delivery::WrongSession;
    if (fault_) {
      model.setComparatorActive(true);
      return Delivery::FaultLocked;
    }

    const auto level = comparator_;
    const bool trip = tripPending_;
    const OperationId expired = timeoutPending_ ? timerId_ : 0;
    comparator_ = Comparator::Unknown;
    tripPending_ = false;
    if (expired != 0) forgetTimeout(expired);

    // Apply the trip even if the latest sampled level is already inactive.
    // Inactive updates the input, but never clears the model's alarm.
    if (trip) model.setComparatorActive(true);
    if (level == Comparator::Inactive) model.setComparatorActive(false);
    if (expired != 0) model.onTimeout(expired);
    return trip || level != Comparator::Unknown || expired != 0
               ? Delivery::Delivered
               : Delivery::NoEvents;
  }

 private:
  enum class Comparator { Unknown, Inactive, Active };

  const SessionId session_;
  OperationId timerId_ = 0;
  Comparator comparator_ = Comparator::Unknown;
  bool timeoutPending_ = false;
  bool tripPending_ = false;
  bool fault_ = false;
};

}  // namespace actuator
