#include "actuator_model.h"

namespace actuator {

Model::Model(Io& io, Limits limits) : io_(io), limits_(limits) {
  io_.setOutput(Output::Off);
}

bool Model::freshPress(bool pressed, bool& released) {
  const bool fresh = pressed && released;
  released = !pressed;
  return fresh;
}

Result Model::dispense(OperationId id, Tick durationMs) {
  return start(State::Dispensing, id, durationMs, limits_.valve);
}

Result Model::uvLocalButton(bool pressed, OperationId id, Tick durationMs) {
  if (!freshPress(pressed, uvButtonReleased_)) {
    return Result::LocalConfirmationRequired;
  }
  if (!uvPermitted_) return Result::UvPermissionMissing;
  return start(State::UvActive, id, durationMs, limits_.uv);
}

Result Model::clearLocalButton(bool pressed) {
  if (!freshPress(pressed, clearButtonReleased_)) {
    return Result::LocalConfirmationRequired;
  }
  if (state_ == State::Dispensing || state_ == State::UvActive) {
    return Result::Busy;
  }
  if (!comparatorSafe_) return Result::ComparatorNotSafe;
  alarm_ = Alarm::None;
  state_ = State::Idle;
  return Result::Accepted;
}

void Model::setUvLocalPermission(bool permitted) {
  uvPermitted_ = permitted;
  if (!permitted) {
    uvButtonReleased_ = false;
    if (state_ == State::UvActive) stopTo(State::Idle);
  }
}

void Model::setComparatorActive(bool active) {
  comparatorSafe_ = !active;
  if (!active || state_ == State::AlarmLocked) return;
  clearButtonReleased_ = false;
  uvButtonReleased_ = false;
  alarm_ = Alarm::Comparator;
  stopTo(State::AlarmLocked);
}

Result Model::start(State operation, OperationId id, Tick durationMs,
                    DurationRange range) {
  if (state_ == State::BootBlocked || state_ == State::AlarmLocked) {
    return Result::Blocked;
  }
  if (id <= lastAcceptedId_) return Result::ReplayedId;
  if (state_ != State::Idle) return Result::Busy;
  if (!comparatorSafe_) return Result::ComparatorNotSafe;
  constexpr Tick kMaxUnambiguousDuration = 0x7fffffffU;
  if (range.minMs == 0 || range.minMs > range.maxMs ||
      range.maxMs > kMaxUnambiguousDuration ||
      durationMs < range.minMs || durationMs > range.maxMs) {
    return Result::InvalidDuration;
  }

  const Tick now = io_.nowMs();
  if (!io_.armOneShot(id, durationMs)) {
    io_.disarmOneShot(id);
    return Result::TimerUnavailable;
  }

  activeId_ = lastAcceptedId_ = id;
  startedMs_ = now;
  durationMs_ = durationMs;
  state_ = operation;
  io_.setOutput(operation == State::Dispensing ? Output::Valve : Output::Uv);
  return Result::Accepted;
}

void Model::stopTo(State next) {
  const OperationId stoppedId = activeId_;
  activeId_ = 0;
  state_ = next;
  io_.setOutput(Output::Off);
  if (stoppedId != 0) io_.disarmOneShot(stoppedId);
}

void Model::onTimeout(OperationId id) {
  if (activeId_ != 0 && id == activeId_) stopTo(State::Idle);
}

void Model::serviceTime() {
  if (activeId_ != 0 && static_cast<Tick>(io_.nowMs() - startedMs_) >= durationMs_) {
    onTimeout(activeId_);
  }
}

void Model::cancel() {
  if (activeId_ != 0) stopTo(State::Idle);
}

void Model::reboot() {
  comparatorSafe_ = false;
  uvPermitted_ = false;
  uvButtonReleased_ = false;
  clearButtonReleased_ = false;
  alarm_ = Alarm::None;
  stopTo(State::BootBlocked);
}

}  // namespace actuator
