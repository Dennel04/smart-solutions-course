#include "post_office_settings.h"

namespace postoffice {

bool SettingsStore::begin() {
  return preferences_.begin("postoffice", false);
}

Settings SettingsStore::load() const {
  Settings settings;
  settings.serverUrl = preferences_.getString("server", "");
  settings.atomKey = preferences_.getString("atomKey", "");
  settings.pollIntervalMs = preferences_.getUInt("pollMs", kDefaultPollIntervalMs);
  settings.allowDevHttp = preferences_.getBool("devHttp", false);
  return settings;
}

bool SettingsStore::save(const Settings& settings) {
  const ConfigInput input{settings.serverUrl.c_str(), settings.atomKey.c_str(),
                          settings.pollIntervalMs, settings.allowDevHttp};
  if (!validateConfig(input).ok()) return false;
  bool ok = preferences_.putString("server", settings.serverUrl) > 0;
  ok = preferences_.putString("atomKey", settings.atomKey) > 0 && ok;
  ok = preferences_.putUInt("pollMs", settings.pollIntervalMs) == sizeof(uint32_t) && ok;
  ok = preferences_.putBool("devHttp", settings.allowDevHttp) == sizeof(bool) && ok;
  return ok;
}

}  // namespace postoffice
