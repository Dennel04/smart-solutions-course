import struct

from src.motion_watch import MAGIC, OFF_Q_ACTUAL, OFF_TEST_VALUE, PACKET_SIZE, MotionDetector, parse_joints


def packet(joints):
    data = bytearray(PACKET_SIZE)
    struct.pack_into("<Q", data, OFF_TEST_VALUE, MAGIC)
    struct.pack_into("<6d", data, OFF_Q_ACTUAL, *joints, 0.0, 0.0)
    return bytes(data)


def test_parse_joints_reads_actual_angles_and_rejects_misaligned():
    assert parse_joints(packet([1.0, 2.0, 3.0, 4.0])) == (1.0, 2.0, 3.0, 4.0)
    assert parse_joints(b"\0" * PACKET_SIZE) is None
    assert parse_joints(b"short") is None


def run(detector, samples):
    return [(t, e) for t, j in samples if (e := detector.update(t, j))]


def test_first_movement_after_rest_is_reported_once():
    d = MotionDetector(threshold_deg=0.05, rest_s=0.3)
    rest = [(i * 0.008, (10.0, 20.0, 30.0, 0.0)) for i in range(50)]
    move = [(0.4 + i * 0.008, (10.0 + 0.02 * (i + 1), 20.0, 30.0, 0.0)) for i in range(20)]
    events = run(d, rest + move)
    assert len(events) == 1
    t, (joint, delta, rest_ms) = events[0]
    assert joint == 1 and delta > 0.05
    assert abs(t - (0.4 + 2 * 0.008)) < 1e-9  # third step crosses 0.05 deg
    assert rest_ms > 300


def test_no_event_without_prior_rest_or_with_small_noise():
    d = MotionDetector(threshold_deg=0.05, rest_s=0.3)
    moving = [(i * 0.008, (0.1 * i, 0.0, 0.0, 0.0)) for i in range(30)]
    assert run(d, moving) == []
    d = MotionDetector(threshold_deg=0.05, rest_s=0.3)
    noise = [(i * 0.008, (0.001 * (i % 2), 0.0, 0.0, 0.0)) for i in range(200)]
    assert run(d, noise) == []
