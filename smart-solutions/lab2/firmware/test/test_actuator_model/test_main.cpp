#include <unity.h>

#include <initializer_list>
#include <limits>

#include "actuator_model.h"

using namespace actuator;

namespace {

// All durations here are synthetic fixtures, not device limits.
constexpr Limits kLimits{{5, 20}, {30, 60}};

struct FakeIo final : Io {
  Tick now = 0;
  Tick armedAt = 0;
  Tick duration = 0;
  OperationId armedId = 0;
  Output output = Output::Uv;  // Verify construction actively drives Off.
  bool armSucceeds = true;
  unsigned arms = 0;
  unsigned starts = 0;

  Tick nowMs() const override { return now; }
  bool armOneShot(OperationId id, Tick durationMs) override {
    TEST_ASSERT_TRUE(output == Output::Off);
    TEST_ASSERT_EQUAL_UINT64(0, armedId);
    ++arms;
    if (!armSucceeds) return false;
    armedId = id;
    armedAt = now;
    duration = durationMs;
    return true;
  }
  void disarmOneShot(OperationId id) override {
    TEST_ASSERT_TRUE(output == Output::Off);
    if (armedId == id) armedId = 0;
  }
  void setOutput(Output next) override {
    if (next != Output::Off) {
      TEST_ASSERT_TRUE(output == Output::Off);
      TEST_ASSERT_NOT_EQUAL(0, armedId);
      ++starts;
    }
    output = next;
  }

  void advance(Model& model, Tick ms) {
    now += ms;
    if (armedId != 0 && static_cast<Tick>(now - armedAt) >= duration) {
      const OperationId expired = armedId;
      armedId = 0;
      model.onTimeout(expired);
    }
  }
};

struct Fixture {
  FakeIo io;
  Model model{io, kLimits};

  void unlock() {
    model.setComparatorActive(false);
    model.clearLocalButton(false);
    TEST_ASSERT_TRUE(model.clearLocalButton(true) == Result::Accepted);
  }
  void dispense(OperationId id = 1) {
    TEST_ASSERT_TRUE(model.dispense(id, 10) == Result::Accepted);
  }
  void uv(OperationId id = 1) {
    model.setUvLocalPermission(true);
    model.uvLocalButton(false, id, 40);
    TEST_ASSERT_TRUE(model.uvLocalButton(true, id, 40) == Result::Accepted);
  }
  void assertOff(State expected) {
    TEST_ASSERT_TRUE(model.state() == expected);
    TEST_ASSERT_TRUE(io.output == Output::Off);
    TEST_ASSERT_EQUAL_UINT64(0, io.armedId);
  }
};

void boots_off_and_blocked() {
  Fixture f;
  f.assertOff(State::BootBlocked);
  TEST_ASSERT_TRUE(f.model.dispense(1, 10) == Result::Blocked);
  f.model.setUvLocalPermission(true);
  f.model.uvLocalButton(false, 1, 40);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 1, 40) == Result::Blocked);
  TEST_ASSERT_EQUAL_UINT(0, f.io.arms);
}

void local_clear_unlocks_after_comparator_sample() {
  Fixture f;
  f.model.clearLocalButton(false);
  TEST_ASSERT_TRUE(f.model.clearLocalButton(true) == Result::ComparatorNotSafe);
  f.model.setComparatorActive(false);
  TEST_ASSERT_TRUE(f.model.clearLocalButton(true) == Result::LocalConfirmationRequired);
  f.assertOff(State::BootBlocked);
  f.unlock();
  f.assertOff(State::Idle);
}

void dispense_is_one_bounded_pulse() {
  Fixture f;
  f.unlock();
  f.dispense();
  TEST_ASSERT_TRUE(f.model.state() == State::Dispensing);
  TEST_ASSERT_TRUE(f.io.output == Output::Valve);
  f.io.advance(f.model, 9);
  TEST_ASSERT_TRUE(f.io.output == Output::Valve);
  f.io.advance(f.model, 1);
  f.assertOff(State::Idle);
  f.io.advance(f.model, 100);
  TEST_ASSERT_EQUAL_UINT(1, f.io.starts);
}

void rejects_invalid_durations_and_invalid_limits() {
  Fixture f;
  f.unlock();
  TEST_ASSERT_TRUE(f.model.dispense(1, 0) == Result::InvalidDuration);
  TEST_ASSERT_TRUE(f.model.dispense(1, 4) == Result::InvalidDuration);
  TEST_ASSERT_TRUE(f.model.dispense(1, 21) == Result::InvalidDuration);
  f.model.setUvLocalPermission(true);
  f.model.uvLocalButton(false, 1, 20);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 1, 20) == Result::InvalidDuration);
  f.model.uvLocalButton(false, 1, 61);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 1, 61) == Result::InvalidDuration);
  TEST_ASSERT_EQUAL_UINT(0, f.io.arms);
  f.assertOff(State::Idle);

  FakeIo io;
  Model invalid(io, {{1, std::numeric_limits<Tick>::max()}, {0, 20}});
  invalid.setComparatorActive(false);
  invalid.clearLocalButton(false);
  TEST_ASSERT_TRUE(invalid.clearLocalButton(true) == Result::Accepted);
  TEST_ASSERT_TRUE(invalid.dispense(1, 10) == Result::InvalidDuration);
  invalid.setUvLocalPermission(true);
  invalid.uvLocalButton(false, 1, 10);
  TEST_ASSERT_TRUE(invalid.uvLocalButton(true, 1, 10) == Result::InvalidDuration);
  TEST_ASSERT_EQUAL_UINT(0, io.arms);
}

void failed_arm_never_energizes_output() {
  Fixture f;
  f.unlock();
  f.io.armSucceeds = false;
  TEST_ASSERT_TRUE(f.model.dispense(1, 10) == Result::TimerUnavailable);
  f.model.setUvLocalPermission(true);
  f.model.uvLocalButton(false, 1, 40);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 1, 40) == Result::TimerUnavailable);
  f.assertOff(State::Idle);
  TEST_ASSERT_EQUAL_UINT(0, f.io.starts);
  f.io.armSucceeds = true;
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 1, 40) == Result::LocalConfirmationRequired);
  f.uv();
}

void duplicate_and_busy_commands_do_not_extend_or_queue() {
  Fixture f;
  f.unlock();
  f.dispense();
  f.io.advance(f.model, 5);
  TEST_ASSERT_TRUE(f.model.dispense(1, 20) == Result::ReplayedId);
  TEST_ASSERT_TRUE(f.model.dispense(2, 20) == Result::Busy);
  f.model.setUvLocalPermission(true);
  f.model.uvLocalButton(false, 2, 40);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 2, 40) == Result::Busy);
  f.io.advance(f.model, 5);
  f.assertOff(State::Idle);
  TEST_ASSERT_EQUAL_UINT(1, f.io.arms);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 2, 40) == Result::LocalConfirmationRequired);
}

void rejects_completed_and_older_ids() {
  Fixture f;
  f.unlock();
  f.dispense(7);
  f.io.advance(f.model, 10);
  TEST_ASSERT_TRUE(f.model.dispense(7, 10) == Result::ReplayedId);
  TEST_ASSERT_TRUE(f.model.dispense(6, 10) == Result::ReplayedId);
  f.model.setUvLocalPermission(true);
  f.model.uvLocalButton(false, 7, 40);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 7, 40) == Result::ReplayedId);
  f.assertOff(State::Idle);
  TEST_ASSERT_EQUAL_UINT(1, f.io.starts);
}

void uv_requires_permission_and_new_local_press_each_time() {
  Fixture f;
  f.unlock();
  f.model.uvLocalButton(false, 1, 40);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 1, 40) == Result::UvPermissionMissing);
  f.model.setUvLocalPermission(true);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 1, 40) == Result::LocalConfirmationRequired);
  f.assertOff(State::Idle);
  f.uv();
  f.io.advance(f.model, 40);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 2, 40) == Result::LocalConfirmationRequired);
  f.assertOff(State::Idle);
}

void uv_ends_on_timer_without_local_polling() {
  Fixture f;
  f.unlock();
  f.uv();
  TEST_ASSERT_TRUE(f.model.state() == State::UvActive);
  TEST_ASSERT_TRUE(f.io.output == Output::Uv);
  f.io.advance(f.model, 39);
  TEST_ASSERT_TRUE(f.io.output == Output::Uv);
  f.io.advance(f.model, 1);
  f.assertOff(State::Idle);
}

void lost_uv_permission_turns_off_without_resuming() {
  Fixture f;
  f.unlock();
  f.uv();
  f.model.setUvLocalPermission(false);
  f.assertOff(State::Idle);
  f.model.setUvLocalPermission(true);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 2, 40) == Result::LocalConfirmationRequired);
  f.model.onTimeout(1);
  f.assertOff(State::Idle);
  TEST_ASSERT_EQUAL_UINT(1, f.io.starts);
}

void comparator_irq_switches_off_and_latches() {
  Fixture f;
  f.unlock();
  f.dispense();
  f.model.setComparatorActive(true);
  f.assertOff(State::AlarmLocked);
  TEST_ASSERT_TRUE(f.model.alarm() == Alarm::Comparator);
  f.model.setComparatorActive(false);
  TEST_ASSERT_TRUE(f.model.dispense(2, 10) == Result::Blocked);
  f.model.setUvLocalPermission(true);
  f.model.uvLocalButton(false, 2, 40);
  TEST_ASSERT_TRUE(f.model.uvLocalButton(true, 2, 40) == Result::Blocked);
  f.assertOff(State::AlarmLocked);
}

void clear_refuses_active_comparator_cause() {
  Fixture f;
  f.unlock();
  f.model.setComparatorActive(true);
  f.model.clearLocalButton(false);
  TEST_ASSERT_TRUE(f.model.clearLocalButton(true) == Result::ComparatorNotSafe);
  f.assertOff(State::AlarmLocked);
}

void clear_needs_new_press_after_cause_is_gone() {
  Fixture f;
  f.unlock();
  f.dispense();
  f.model.setComparatorActive(true);
  f.model.clearLocalButton(false);
  TEST_ASSERT_TRUE(f.model.clearLocalButton(true) == Result::ComparatorNotSafe);
  f.model.setComparatorActive(false);
  TEST_ASSERT_TRUE(f.model.clearLocalButton(true) == Result::LocalConfirmationRequired);
  f.unlock();
  f.assertOff(State::Idle);
  TEST_ASSERT_TRUE(f.model.alarm() == Alarm::None);
  f.model.onTimeout(1);
  f.assertOff(State::Idle);
  TEST_ASSERT_EQUAL_UINT(1, f.io.starts);
}

void in_place_reboot_preserves_id_watermark() {
  Fixture f;
  f.unlock();
  f.uv(7);
  TEST_ASSERT_TRUE(f.io.output == Output::Uv);
  f.model.reboot();
  f.assertOff(State::BootBlocked);
  TEST_ASSERT_TRUE(f.model.dispense(8, 10) == Result::Blocked);
  f.model.onTimeout(7);
  TEST_ASSERT_TRUE(f.model.clearLocalButton(true) == Result::LocalConfirmationRequired);
  f.unlock();
  f.assertOff(State::Idle);
  TEST_ASSERT_TRUE(f.model.dispense(7, 10) == Result::ReplayedId);
  TEST_ASSERT_TRUE(f.model.dispense(1, 10) == Result::ReplayedId);
  f.assertOff(State::Idle);
  TEST_ASSERT_EQUAL_UINT(1, f.io.starts);

  f.dispense(8);
  f.model.onTimeout(7);
  TEST_ASSERT_TRUE(f.io.output == Output::Valve);
  f.io.advance(f.model, 10);
  f.assertOff(State::Idle);
  TEST_ASSERT_EQUAL_UINT(2, f.io.starts);
}

void fresh_instance_starts_a_new_id_sequence() {
  {
    Fixture previous;
    previous.unlock();
    previous.dispense();
    previous.io.advance(previous.model, 10);
    previous.assertOff(State::Idle);
  }
  // A real reboot reconstructs the model. The transport must filter the old
  // boot session before the model sees IDs from the new one.
  Fixture fresh;
  fresh.assertOff(State::BootBlocked);
  TEST_ASSERT_TRUE(fresh.model.dispense(1, 10) == Result::Blocked);
  fresh.unlock();
  fresh.assertOff(State::Idle);
  TEST_ASSERT_EQUAL_UINT(0, fresh.io.starts);
  fresh.dispense(1);
  fresh.io.advance(fresh.model, 10);
  fresh.assertOff(State::Idle);
}

void timeout_and_irq_leave_alarm_in_either_order() {
  for (bool timeoutFirst : {false, true}) {
    Fixture f;
    f.unlock();
    f.dispense();
    if (timeoutFirst) f.io.advance(f.model, 10);
    f.model.setComparatorActive(true);
    f.model.onTimeout(1);
    f.model.cancel();
    f.assertOff(State::AlarmLocked);
    TEST_ASSERT_TRUE(f.model.alarm() == Alarm::Comparator);
    TEST_ASSERT_EQUAL_UINT(1, f.io.starts);
  }
}

void wrapped_clock_expires_at_correct_elapsed_time() {
  Fixture f;
  f.io.now = std::numeric_limits<Tick>::max() - 4;
  f.unlock();
  f.dispense();
  f.io.now += 9;
  f.model.serviceTime();
  TEST_ASSERT_TRUE(f.io.output == Output::Valve);
  ++f.io.now;
  f.model.serviceTime();
  f.assertOff(State::Idle);
}

void late_timeout_does_not_cancel_a_new_pulse() {
  Fixture f;
  f.unlock();
  f.dispense();
  f.model.cancel();
  f.assertOff(State::Idle);
  f.dispense(2);
  f.model.onTimeout(1);
  TEST_ASSERT_TRUE(f.io.output == Output::Valve);
  f.io.advance(f.model, 10);
  f.assertOff(State::Idle);
}

void comparator_irq_also_stops_uv() {
  Fixture f;
  f.unlock();
  f.uv();
  f.model.setComparatorActive(true);
  f.assertOff(State::AlarmLocked);
  f.io.advance(f.model, 40);
  f.assertOff(State::AlarmLocked);
}

}  // namespace

int main() {
  UNITY_BEGIN();
  RUN_TEST(boots_off_and_blocked);
  RUN_TEST(local_clear_unlocks_after_comparator_sample);
  RUN_TEST(dispense_is_one_bounded_pulse);
  RUN_TEST(rejects_invalid_durations_and_invalid_limits);
  RUN_TEST(failed_arm_never_energizes_output);
  RUN_TEST(duplicate_and_busy_commands_do_not_extend_or_queue);
  RUN_TEST(rejects_completed_and_older_ids);
  RUN_TEST(uv_requires_permission_and_new_local_press_each_time);
  RUN_TEST(uv_ends_on_timer_without_local_polling);
  RUN_TEST(lost_uv_permission_turns_off_without_resuming);
  RUN_TEST(comparator_irq_switches_off_and_latches);
  RUN_TEST(clear_refuses_active_comparator_cause);
  RUN_TEST(clear_needs_new_press_after_cause_is_gone);
  RUN_TEST(in_place_reboot_preserves_id_watermark);
  RUN_TEST(fresh_instance_starts_a_new_id_sequence);
  RUN_TEST(timeout_and_irq_leave_alarm_in_either_order);
  RUN_TEST(wrapped_clock_expires_at_correct_elapsed_time);
  RUN_TEST(late_timeout_does_not_cancel_a_new_pulse);
  RUN_TEST(comparator_irq_also_stops_uv);
  return UNITY_END();
}
