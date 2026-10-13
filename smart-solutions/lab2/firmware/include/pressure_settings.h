#pragma once

#include <Preferences.h>

#include "pressure_model.h"

namespace pressure {

class SettingsStore {
 public:
  bool begin();
  Calibration load() const;
  bool save(const Calibration& calibration);

 private:
  mutable Preferences preferences_;
};

}  // namespace pressure
