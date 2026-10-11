#pragma once

#include <Arduino.h>
#include <Preferences.h>

#include "post_office_model.h"

namespace postoffice {

struct Settings {
  String serverUrl;
  String atomKey;
  uint32_t pollIntervalMs = kDefaultPollIntervalMs;
  bool allowDevHttp = false;
};

class SettingsStore {
 public:
  bool begin();
  Settings load() const;
  bool save(const Settings& settings);

 private:
  mutable Preferences preferences_;
};

}  // namespace postoffice
