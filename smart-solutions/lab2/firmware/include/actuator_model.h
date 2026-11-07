#pragma once

#include <cstdint>

namespace actuator {

using OperationId = std::uint64_t;
using Tick = std::uint32_t;

enum class State { BootBlocked, Idle, Dispensing, UvActive, AlarmLocked };
enum class Output { Off, Valve, Uv };
enum class Alarm { None, Comparator };

enum class Result {
  Accepted,
  Blocked,
  Busy,
  InvalidDuration,
  ReplayedId,
  TimerUnavailable,
  LocalConfirmationRequired,
  UvPermissionMissing,
  ComparatorNotSafe,
};

struct DurationRange {
  Tick minMs;
  Tick maxMs;
};

struct Limits {
  DurationRange valve;
  DurationRange uv;
};

// Simulation boundary only. A successful arm schedules one timeout carrying its ID;
// disarm is safe even after a failed arm or a delivered timeout.
class Io {
 public:
  virtual ~Io() = default;
  virtual Tick nowMs() const = 0;
  virtual bool armOneShot(OperationId id, Tick durationMs) = 0;
  virtual void disarmOneShot(OperationId id) = 0;
  virtual void setOutput(Output output) = 0;
};

// Single-owner model: serialize all access and do not reenter it from Io.
// A hardware adapter must deliver timer/comparator events in that same
// serialized context, never call these methods directly from an ISR.
class Model {
 public:
  Model(Io& io, Limits limits);
  Model(const Model&) = delete;
  Model& operator=(const Model&) = delete;

  State state() const { return state_; }
  Alarm alarm() const { return alarm_; }

  // Operation IDs (including UV) are positive and strictly increasing among
  // accepted operations for this instance. They are not transport boot IDs.
  Result dispense(OperationId id, Tick durationMs);

  // Only trusted local input adapters may call the button methods with actual
  // levels. A release followed by a press is required; a rejected press is
  // consumed too. There is no stored approval and no generic UV start command.
  Result uvLocalButton(bool pressed, OperationId id, Tick durationMs);
  Result clearLocalButton(bool pressed);
  void setUvLocalPermission(bool permitted);

  // true delivers a comparator trip; false is a fresh observation of the input.
  // The comparator is considered unknown until sampled after boot.
  void setComparatorActive(bool active);

  void onTimeout(OperationId id);
  // Optional clock-based servicing for the simulation. Unsigned elapsed time
  // handles wrap, provided it is observed within one full counter cycle of
  // arm. Ranges are limited to half the counter span.
  void serviceTime();
  void cancel();
  // In-place safety reset: stop and require a new local check, but keep the ID
  // watermark so old commands and late timer events cannot reuse accepted IDs.
  // A real boot creates a fresh instance and starts a new ID sequence. The
  // USB adapter must reject packets from other boot sessions before dispatch;
  // the model cannot distinguish them. Timeout delivery must also be scoped
  // to its originating instance by the timer adapter.
  void reboot();

 private:
  static bool freshPress(bool pressed, bool& released);
  Result start(State operation, OperationId id, Tick durationMs,
               DurationRange range);
  void stopTo(State next);

  Io& io_;
  const Limits limits_;
  State state_ = State::BootBlocked;
  Alarm alarm_ = Alarm::None;
  bool comparatorSafe_ = false;
  bool uvPermitted_ = false;
  bool uvButtonReleased_ = false;
  bool clearButtonReleased_ = false;
  OperationId activeId_ = 0;
  OperationId lastAcceptedId_ = 0;
  Tick startedMs_ = 0;
  Tick durationMs_ = 0;
};

}  // namespace actuator
