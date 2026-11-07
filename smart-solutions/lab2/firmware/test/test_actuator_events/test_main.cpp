#include <unity.h>

#include "actuator_events.h"

using namespace actuator;

namespace {

struct SimIo final : Io {
  EventInbox& inbox;
  Output output = Output::Off;
  unsigned starts = 0;

  explicit SimIo(EventInbox& inbox) : inbox(inbox) {}
  Tick nowMs() const override { return 0; }
  bool armOneShot(OperationId id, Tick) override { return inbox.expectTimeout(id); }
  void disarmOneShot(OperationId id) override { inbox.forgetTimeout(id); }
  void setOutput(Output next) override {
    if (next != Output::Off) ++starts;
    output = next;
  }
};

struct Fixture {
  const SessionId session;
  EventInbox inbox;
  SimIo io{inbox};
  Model model{io, {{1, 20}, {1, 20}}};

  explicit Fixture(SessionId session = 1) : session(session), inbox(session) {}
  Delivery drain() { return inbox.deliver(session, model); }
  void level(bool active) { inbox.postComparatorLevel(session, active); }
  void expire(OperationId id) { inbox.postTimeout(session, id); }
  Result localClear() {
    model.clearLocalButton(false);
    return model.clearLocalButton(true);
  }
  void start(OperationId id = 1) {
    TEST_ASSERT_TRUE(model.dispense(id, 10) == Result::Accepted);
  }
  void unlock() {
    level(false);
    TEST_ASSERT_TRUE(drain() == Delivery::Delivered);
    TEST_ASSERT_TRUE(localClear() == Result::Accepted);
  }
  void off(State expected) {
    TEST_ASSERT_TRUE(model.state() == expected);
    TEST_ASSERT_TRUE(io.output == Output::Off);
  }
};

void normal_timeout_is_delivered_by_consumer_only() {
  Fixture f;
  f.unlock();
  f.start();
  f.expire(1);
  TEST_ASSERT_TRUE(f.model.state() == State::Dispensing);
  TEST_ASSERT_TRUE(f.io.output == Output::Valve);
  TEST_ASSERT_TRUE(f.drain() == Delivery::Delivered);
  f.off(State::Idle);
  TEST_ASSERT_TRUE(f.drain() == Delivery::NoEvents);
}

void comparator_producer_does_not_call_model() {
  Fixture f;
  f.unlock();
  f.start();
  f.level(true);
  TEST_ASSERT_TRUE(f.model.state() == State::Dispensing);
  TEST_ASSERT_TRUE(f.io.output == Output::Valve);
  TEST_ASSERT_TRUE(f.drain() == Delivery::Delivered);
  f.off(State::AlarmLocked);
  TEST_ASSERT_TRUE(f.model.alarm() == Alarm::Comparator);
}

void brief_trip_survives_inactive_sample_and_needs_local_clear() {
  Fixture f;
  f.unlock();
  f.start();
  f.level(true);
  f.level(false);
  f.drain();
  f.off(State::AlarmLocked);
  TEST_ASSERT_TRUE(f.model.dispense(2, 10) == Result::Blocked);
  TEST_ASSERT_TRUE(f.model.clearLocalButton(true) == Result::LocalConfirmationRequired);
  TEST_ASSERT_TRUE(f.localClear() == Result::Accepted);
  f.off(State::Idle);
  TEST_ASSERT_EQUAL_UINT(1, f.io.starts);
}

void trip_wins_in_both_publication_orders() {
  for (unsigned order = 0; order < 2; ++order) {
    Fixture f;
    f.unlock();
    f.start();
    if (order == 0) f.expire(1);
    f.level(true);
    if (order == 1) f.expire(1);
    f.drain();
    f.off(State::AlarmLocked);
    f.expire(1);
    f.drain();
    f.off(State::AlarmLocked);
  }
}

void trip_locks_even_after_timeout_was_already_delivered() {
  Fixture f;
  f.unlock();
  f.start();
  f.expire(1);
  f.drain();
  f.off(State::Idle);
  f.level(true);
  f.drain();
  f.off(State::AlarmLocked);
}

void duplicate_notifications_coalesce_and_never_start_output() {
  Fixture f;
  f.unlock();
  f.start();
  f.expire(1);
  f.expire(1);
  f.drain();
  f.off(State::Idle);
  f.expire(1);
  TEST_ASSERT_TRUE(f.drain() == Delivery::NoEvents);
  f.level(true);
  f.level(false);
  f.level(true);
  f.level(false);
  f.drain();
  f.off(State::AlarmLocked);
  TEST_ASSERT_TRUE(f.localClear() == Result::Accepted);
  f.off(State::Idle);
  TEST_ASSERT_EQUAL_UINT(1, f.io.starts);
}

void old_operation_timeout_cannot_displace_current_timeout() {
  Fixture f;
  f.unlock();
  f.start(1);
  f.expire(1);
  f.model.cancel();  // Disarm discards the pending notification for 1.
  f.start(2);
  f.expire(1);
  TEST_ASSERT_TRUE(f.drain() == Delivery::NoEvents);
  TEST_ASSERT_TRUE(f.model.state() == State::Dispensing);
  f.expire(2);
  f.expire(1);
  TEST_ASSERT_TRUE(f.drain() == Delivery::Delivered);
  f.off(State::Idle);
}

void old_boot_timeout_cannot_finish_reused_operation_id() {
  Fixture previous(11);
  previous.unlock();
  previous.start(1);
  previous.model.reboot();

  Fixture current(12);
  current.unlock();
  current.start(1);
  current.inbox.postTimeout(previous.session, 1);
  TEST_ASSERT_TRUE(current.drain() == Delivery::NoEvents);
  TEST_ASSERT_TRUE(current.model.state() == State::Dispensing);
  current.expire(1);
  current.drain();
  current.off(State::Idle);
}

void old_session_trip_fault_and_inbox_cannot_affect_new_instance() {
  Fixture previous(11);
  previous.level(true);
  previous.inbox.postDeliveryFailure(previous.session);
  Fixture current(12);
  current.unlock();
  current.start();
  current.inbox.postComparatorLevel(previous.session, true);
  current.inbox.postDeliveryFailure(previous.session);
  TEST_ASSERT_TRUE(previous.inbox.deliver(current.session, current.model) ==
                   Delivery::WrongSession);
  TEST_ASSERT_TRUE(current.drain() == Delivery::NoEvents);
  TEST_ASSERT_TRUE(current.model.state() == State::Dispensing);
}

void occupied_timer_slot_fails_closed_even_without_comparator_trip() {
  Fixture f;
  f.unlock();
  f.start();
  f.expire(1);
  TEST_ASSERT_FALSE(f.inbox.expectTimeout(2));
  TEST_ASSERT_TRUE(f.model.state() == State::Dispensing);
  TEST_ASSERT_TRUE(f.drain() == Delivery::FaultLocked);
  f.off(State::AlarmLocked);
  TEST_ASSERT_FALSE(f.inbox.expectTimeout(3));
}

void fault_and_overflow_do_not_lose_a_pending_trip_or_allow_clear() {
  Fixture f;
  f.unlock();
  f.start();
  f.level(true);
  f.level(false);
  f.expire(1);
  TEST_ASSERT_FALSE(f.inbox.expectTimeout(2));
  f.inbox.postDeliveryFailure(f.session);
  TEST_ASSERT_TRUE(f.drain() == Delivery::FaultLocked);
  f.off(State::AlarmLocked);
  f.level(false);
  TEST_ASSERT_TRUE(f.drain() == Delivery::FaultLocked);
  TEST_ASSERT_TRUE(f.localClear() == Result::ComparatorNotSafe);
  f.off(State::AlarmLocked);
  TEST_ASSERT_EQUAL_UINT(1, f.io.starts);
}

void delivery_fault_alone_requires_new_session_and_local_unlock() {
  Fixture f;
  f.unlock();
  f.start();
  f.inbox.postDeliveryFailure(f.session);
  TEST_ASSERT_TRUE(f.model.state() == State::Dispensing);
  TEST_ASSERT_TRUE(f.drain() == Delivery::FaultLocked);
  f.off(State::AlarmLocked);
  f.model.reboot();
  f.off(State::BootBlocked);
  f.level(false);
  TEST_ASSERT_TRUE(f.drain() == Delivery::FaultLocked);
  TEST_ASSERT_TRUE(f.localClear() == Result::ComparatorNotSafe);

  Fixture fresh(2);
  fresh.off(State::BootBlocked);
  fresh.unlock();
  fresh.off(State::Idle);
  TEST_ASSERT_EQUAL_UINT(0, fresh.io.starts);
}

void comparator_must_be_inactive_before_local_clear() {
  Fixture f;
  f.unlock();
  f.level(true);
  f.drain();
  TEST_ASSERT_TRUE(f.localClear() == Result::ComparatorNotSafe);
  f.level(false);
  f.drain();
  f.off(State::AlarmLocked);
  TEST_ASSERT_TRUE(f.model.clearLocalButton(true) == Result::LocalConfirmationRequired);
  TEST_ASSERT_TRUE(f.localClear() == Result::Accepted);
  f.off(State::Idle);
}

}  // namespace

int main() {
  UNITY_BEGIN();
  RUN_TEST(normal_timeout_is_delivered_by_consumer_only);
  RUN_TEST(comparator_producer_does_not_call_model);
  RUN_TEST(brief_trip_survives_inactive_sample_and_needs_local_clear);
  RUN_TEST(trip_wins_in_both_publication_orders);
  RUN_TEST(trip_locks_even_after_timeout_was_already_delivered);
  RUN_TEST(duplicate_notifications_coalesce_and_never_start_output);
  RUN_TEST(old_operation_timeout_cannot_displace_current_timeout);
  RUN_TEST(old_boot_timeout_cannot_finish_reused_operation_id);
  RUN_TEST(old_session_trip_fault_and_inbox_cannot_affect_new_instance);
  RUN_TEST(occupied_timer_slot_fails_closed_even_without_comparator_trip);
  RUN_TEST(fault_and_overflow_do_not_lose_a_pending_trip_or_allow_clear);
  RUN_TEST(delivery_fault_alone_requires_new_session_and_local_unlock);
  RUN_TEST(comparator_must_be_inactive_before_local_clear);
  return UNITY_END();
}
