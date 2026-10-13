#pragma once

#include <Arduino.h>
#include <Preferences.h>

#include "persistent_state.h"
#include "post_office_model.h"

namespace postoffice {

class StationBridge {
 public:
  bool begin();
  bool dispatchJob(const Job& job, uint32_t sentAtMs);
  bool handleResultLine(const String& line, PersistentState& state);

 private:
  Preferences preferences_;
};

}  // namespace postoffice
