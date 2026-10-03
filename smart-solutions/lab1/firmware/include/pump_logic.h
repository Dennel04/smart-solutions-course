// Copied unchanged from data-acquisition-course (data-acquisition/lab1/src/firmware, commit 7ea7afa).
#pragma once
#include <cstdint>
#include <cstring>

// Bang-bang / hysteresis controller matching README part 4's pseudocode:
//
//   suction: if p weaker than "on" AND idle-time >= min-off-time -> pump 1
//            if p stronger than "off"                            -> pump 0
//   blow:    same shape, opposite sign
//   off / out-of-scale / cycles-per-min over limit -> pump 0, reason shown
//
// The actual on/off kPa thresholds, min-off-time and max-cycles/min are
// NOT hardcoded here -- those five numbers are what part 4 asks the team
// to measure (holding curves on glass / in air / capped tube) and record
// in docs/pump_control.md. This class only implements the *shape* of the
// control law; you supply the numbers via setBand()/setSafetyLimits().
namespace pump {

enum class Mode { Off, Suction, Blow };

struct Band {
  float onKpa = 0;   // relative kPa: weaker-than-this starts the pump
  float offKpa = 0;  // relative kPa: stronger-than-this stops the pump
};

struct SafetyLimits {
  uint32_t minOffTimeMs = 0;     // don't restart before this much idle time
  uint16_t maxCyclesPerMin = 0;  // 0 = no limit; else a hard safety cutoff
  float outOfScaleAbsKpa = 200;  // |p| beyond this -> treat as sensor fault
};

class Controller {
 public:
  void setMode(Mode m) {
    if (m != mode_) {
      mode_ = m;
      pumpOn_ = false;
      // A mode change is a command from the robot side ("grip" / "release"):
      // like the factory smart box, it starts at once. min-off-time and the
      // starts-per-minute cap protect the motor from the *automatic*
      // re-pumping of the band, not from commanded actions. 02.10.26: with
      // them applied to everything, a release blow 6.7 s after a band stop
      // and the 3rd grip within a minute were both refused.
      commandedStart_ = (m != Mode::Off);
    }
  }
  void setBand(const Band& b) { band_ = b; }
  void setSafetyLimits(const SafetyLimits& s) { limits_ = s; }

  // Call every 10ms with the latest relative-kPa reading. Writes a short
  // reason string (for screen/log) into reasonOut, which must hold at
  // least 12 bytes including the terminator.
  bool update(float pKpa, uint32_t nowMs, char* reasonOut) {
    auto setReason = [&](const char* r) {
      if (reasonOut) std::strncpy(reasonOut, r, 11);
    };

    if (mode_ == Mode::Off) {
      pumpOn_ = false;
      setReason("off");
      return false;
    }

    if (pKpa > limits_.outOfScaleAbsKpa || pKpa < -limits_.outOfScaleAbsKpa) {
      pumpOn_ = false;
      setReason("out-of-scale");
      return false;
    }

    if (limits_.maxCyclesPerMin > 0 && nowMs - cycleWindowStartMs_ > 60000) {
      cycleWindowStartMs_ = nowMs;
      cyclesThisWindow_ = 0;
    }

    const bool suction = (mode_ == Mode::Suction);
    const bool weakerThanOn =
        suction ? (pKpa > band_.onKpa) : (pKpa < band_.onKpa);
    const bool strongerThanOff =
        suction ? (pKpa < band_.offKpa) : (pKpa > band_.offKpa);

    bool wantOn = pumpOn_;
    if (!pumpOn_) {
      if (weakerThanOn) {
        if (commandedStart_) {
          wantOn = true;                       // commanded: start now
        } else {
          const bool idleLongEnough =
              (nowMs - lastOffAtMs_) >= limits_.minOffTimeMs;
          const bool underCap = limits_.maxCyclesPerMin == 0 ||
                                cyclesThisWindow_ < limits_.maxCyclesPerMin;
          if (idleLongEnough && underCap) {
            wantOn = true;
            ++cyclesThisWindow_;               // only automatic restarts count
          } else if (!underCap) {
            setReason("cycle-limit");
            return false;
          }
        }
      }
    } else {
      if (strongerThanOff) wantOn = false;
    }
    commandedStart_ = false;   // one commanded start per mode change

    if (wantOn != pumpOn_) {
      if (!wantOn) lastOffAtMs_ = nowMs;
      pumpOn_ = wantOn;
    }

    setReason(pumpOn_ ? (suction ? "suction" : "blow") : "band-hold");
    return pumpOn_;
  }

 private:
  Mode mode_ = Mode::Off;
  Band band_;
  SafetyLimits limits_;

  bool pumpOn_ = false;
  uint32_t lastOffAtMs_ = 0;
  uint32_t cycleWindowStartMs_ = 0;
  uint16_t cyclesThisWindow_ = 0;
  bool commandedStart_ = false;
};

} // namespace pump
