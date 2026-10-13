#include <unity.h>

#include <cstring>

#include "post_office_model.h"

using namespace postoffice;

static Job validJob() {
  Job job;
  std::strcpy(job.id, "example-job-1");
  std::strcpy(job.type, "letter");
  job.letter = 'A';
  job.expiresEpoch = 2000;
  return job;
}

void test_valid_letter_job() {
  TEST_ASSERT_TRUE(validateJob(validJob(), 1000, true).ok());
}

void test_invalid_letter_is_refused() {
  Job job = validJob();
  job.letter = '1';
  TEST_ASSERT_EQUAL(
      static_cast<int>(ValidationCode::InvalidLetter),
      static_cast<int>(validateJob(job, 1000, true).code));
}

void test_valid_pick_place_job() {
  Job job = validJob();
  std::strcpy(job.type, "pick_place");
  std::strcpy(job.routine, "source_to_finished");
  TEST_ASSERT_TRUE(validateJob(job, 1000, true).ok());
}

void test_invalid_pick_place_routine_is_refused() {
  Job job = validJob();
  std::strcpy(job.type, "pick_place");
  std::strcpy(job.routine, "other");
  TEST_ASSERT_EQUAL(
      static_cast<int>(ValidationCode::InvalidRoutine),
      static_cast<int>(validateJob(job, 1000, true).code));
}

void test_unknown_job_is_refused() {
  Job job = validJob();
  std::strcpy(job.type, "move_robot");
  TEST_ASSERT_EQUAL(
      static_cast<int>(ValidationCode::UnknownJob),
      static_cast<int>(validateJob(job, 1000, true).code));
}

void test_direct_motion_is_refused() {
  Job job = validJob();
  job.hasDirectMotionData = true;
  TEST_ASSERT_EQUAL(
      static_cast<int>(ValidationCode::DirectMotionNotAllowed),
      static_cast<int>(validateJob(job, 1000, true).code));
}

void test_expired_job_is_refused() {
  Job job = validJob();
  TEST_ASSERT_EQUAL(
      static_cast<int>(ValidationCode::Expired),
      static_cast<int>(validateJob(job, 2000, true).code));
}

void test_clock_is_required_for_expiration_check() {
  TEST_ASSERT_EQUAL(
      static_cast<int>(ValidationCode::ClockUnavailable),
      static_cast<int>(validateJob(validJob(), 0, false).code));
}

void test_config_requires_https_without_dev_flag() {
  ConfigInput config{"http://127.0.0.1:5001", "test-key", 1000, false};
  TEST_ASSERT_EQUAL(
      static_cast<int>(ConfigCode::HttpRequiresDevMode),
      static_cast<int>(validateConfig(config).code));
  config.allowDevHttp = true;
  TEST_ASSERT_TRUE(validateConfig(config).ok());
}

void test_config_requires_key_and_poll_range() {
  ConfigInput missingKey{"https://example.invalid", "", 1000, false};
  TEST_ASSERT_EQUAL(
      static_cast<int>(ConfigCode::MissingAtomKey),
      static_cast<int>(validateConfig(missingKey).code));
  ConfigInput badInterval{"https://example.invalid", "test-key", 1, false};
  TEST_ASSERT_EQUAL(
      static_cast<int>(ConfigCode::InvalidPollInterval),
      static_cast<int>(validateConfig(badInterval).code));
}

void test_config_rejects_missing_host_and_whitespace() {
  ConfigInput missingHost{"https://", "test-key", 1000, false};
  TEST_ASSERT_EQUAL(
      static_cast<int>(ConfigCode::InvalidServerUrl),
      static_cast<int>(validateConfig(missingHost).code));
  ConfigInput whitespace{"https://example.invalid/path\n", "test-key", 1000, false};
  TEST_ASSERT_EQUAL(
      static_cast<int>(ConfigCode::InvalidServerUrl),
      static_cast<int>(validateConfig(whitespace).code));
}

void test_claim_guard_blocks_second_job_and_duplicate() {
  ClaimGuard guard;
  TEST_ASSERT_TRUE(guard.start("job-1"));
  TEST_ASSERT_FALSE(guard.canPoll());
  TEST_ASSERT_FALSE(guard.start("job-2"));
  TEST_ASSERT_TRUE(guard.isDuplicate("job-1"));
}

void test_result_must_match_active_job_and_ack() {
  ClaimGuard guard;
  TEST_ASSERT_TRUE(guard.start("job-1"));
  TEST_ASSERT_FALSE(guard.queueResult("job-2"));
  TEST_ASSERT_TRUE(guard.queueResult("job-1"));
  TEST_ASSERT_FALSE(guard.canPoll());
  TEST_ASSERT_TRUE(guard.acknowledgeResult("job-1"));
  TEST_ASSERT_TRUE(guard.canPoll());
}

void test_restored_ambiguous_claim_is_not_pollable() {
  ClaimGuard guard;
  guard.restore("ambiguous-job", "");
  TEST_ASSERT_FALSE(guard.canPoll());
  TEST_ASSERT_TRUE(guard.isDuplicate("ambiguous-job"));
}

void test_missing_persisted_claim_restores_as_empty_state() {
  ClaimGuard guard;
  guard.restore("", "");
  TEST_ASSERT_TRUE(guard.canPoll());
  TEST_ASSERT_EQUAL_STRING("", guard.activeJobId());
  TEST_ASSERT_EQUAL_STRING("", guard.pendingResultId());
}

void test_missing_wifi_credentials_start_setup_ap() {
  TEST_ASSERT_EQUAL(
      static_cast<int>(WifiStartupMode::SetupAccessPoint),
      static_cast<int>(wifiStartupMode(false)));
}

void test_saved_wifi_credentials_attempt_station_connection() {
  TEST_ASSERT_EQUAL(
      static_cast<int>(WifiStartupMode::StationAttempt),
      static_cast<int>(wifiStartupMode(true)));
}

void test_station_attempt_waits_before_timeout() {
  TEST_ASSERT_FALSE(shouldFallbackToSetupAccessPoint(false, kWifiStaTimeoutMs - 1));
  TEST_ASSERT_FALSE(shouldFallbackToSetupAccessPoint(true, kWifiStaTimeoutMs));
}

void test_station_timeout_falls_back_to_setup_ap() {
  TEST_ASSERT_TRUE(shouldFallbackToSetupAccessPoint(false, kWifiStaTimeoutMs));
}

void test_wifi_recovery_enters_fallback_after_initial_timeout() {
  TEST_ASSERT_EQUAL(
      static_cast<int>(WifiRecoveryAction::EnterFallback),
      static_cast<int>(wifiRecoveryAction(false, true, false, kWifiStaTimeoutMs,
                                          false)));
}

void test_wifi_recovery_waits_for_retry_timer() {
  TEST_ASSERT_EQUAL(
      static_cast<int>(WifiRecoveryAction::None),
      static_cast<int>(wifiRecoveryAction(true, false, false, 0, false)));
  TEST_ASSERT_EQUAL(
      static_cast<int>(WifiRecoveryAction::StartRetry),
      static_cast<int>(wifiRecoveryAction(true, false, false, 0, true)));
}

void test_wifi_recovery_success_stops_retry() {
  TEST_ASSERT_EQUAL(
      static_cast<int>(WifiRecoveryAction::RetrySucceeded),
      static_cast<int>(wifiRecoveryAction(true, true, true, 1000, false)));
}

void test_failed_wifi_retry_returns_to_fallback_wait() {
  TEST_ASSERT_EQUAL(
      static_cast<int>(WifiRecoveryAction::RetryTimedOut),
      static_cast<int>(wifiRecoveryAction(true, true, false, kWifiStaTimeoutMs,
                                          false)));
}

int main(int argc, char** argv) {
  UNITY_BEGIN();
  RUN_TEST(test_valid_letter_job);
  RUN_TEST(test_invalid_letter_is_refused);
  RUN_TEST(test_valid_pick_place_job);
  RUN_TEST(test_invalid_pick_place_routine_is_refused);
  RUN_TEST(test_unknown_job_is_refused);
  RUN_TEST(test_direct_motion_is_refused);
  RUN_TEST(test_expired_job_is_refused);
  RUN_TEST(test_clock_is_required_for_expiration_check);
  RUN_TEST(test_config_requires_https_without_dev_flag);
  RUN_TEST(test_config_requires_key_and_poll_range);
  RUN_TEST(test_config_rejects_missing_host_and_whitespace);
  RUN_TEST(test_claim_guard_blocks_second_job_and_duplicate);
  RUN_TEST(test_result_must_match_active_job_and_ack);
  RUN_TEST(test_restored_ambiguous_claim_is_not_pollable);
  RUN_TEST(test_missing_persisted_claim_restores_as_empty_state);
  RUN_TEST(test_missing_wifi_credentials_start_setup_ap);
  RUN_TEST(test_saved_wifi_credentials_attempt_station_connection);
  RUN_TEST(test_station_attempt_waits_before_timeout);
  RUN_TEST(test_station_timeout_falls_back_to_setup_ap);
  RUN_TEST(test_wifi_recovery_enters_fallback_after_initial_timeout);
  RUN_TEST(test_wifi_recovery_waits_for_retry_timer);
  RUN_TEST(test_wifi_recovery_success_stops_retry);
  RUN_TEST(test_failed_wifi_retry_returns_to_fallback_wait);
  return UNITY_END();
}
