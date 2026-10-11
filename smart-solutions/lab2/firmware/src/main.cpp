#include <Arduino.h>
#include <ArduinoJson.h>
#include <DNSServer.h>
#include <M5Unified.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_system.h>
#include <time.h>

#include "persistent_state.h"
#include "post_office_ca.h"
#include "post_office_client.h"
#include "post_office_model.h"
#include "post_office_settings.h"
#include "station_bridge.h"
#include "web_page.h"

namespace {

constexpr uint16_t kDnsPort = 53;
constexpr char kSetupSsid[] = "Lab2AtomSetup";

WebServer webServer(80);
DNSServer dnsServer;
Preferences wifiPreferences;
postoffice::SettingsStore settingsStore;
postoffice::PersistentState persistentState;
postoffice::StationBridge stationBridge;
postoffice::PostOfficeClient postOfficeClient;
postoffice::Settings settings;
String serialLine;
bool accessPointActive = false;

void logLine(const String& message) {
  // Never pass Wi-Fi passwords or the Atom API key to this function.
  Serial.println("# " + message);
}

String jsonString(const String& value) {
  JsonDocument document;
  document.set(value);
  String output;
  serializeJson(document, output);
  return output;
}

String deviceId() {
  const uint64_t mac = ESP.getEfuseMac();
  char value[32];
  snprintf(value, sizeof(value), "atom-%04lx%08lx", (unsigned long)(mac >> 32),
           (unsigned long)mac);
  return String(value);
}

void showStatus(const String& heading, const String& detail) {
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextColor(TFT_GREEN, TFT_BLACK);
  M5.Display.setTextSize(1);
  M5.Display.setCursor(4, 5);
  M5.Display.println(heading);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.println(detail);
}

void startNetwork() {
  const String ssid = wifiPreferences.getString("ssid", "");
  if (!ssid.isEmpty()) {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(ssid.c_str(), wifiPreferences.getString("pass", "").c_str());
    accessPointActive = false;
    logLine("Wi-Fi STA connecting to configured SSID");
    showStatus("Wi-Fi connecting", ssid);
    return;
  }

  WiFi.mode(WIFI_AP);
  WiFi.softAP(kSetupSsid);  // local setup AP; no production credential in source
  dnsServer.start(kDnsPort, "*", WiFi.softAPIP());
  accessPointActive = true;
  logLine("Wi-Fi setup AP active");
  showStatus("Setup AP", WiFi.softAPIP().toString());
}

String wifiModeName() {
  if (accessPointActive) return "ap";
  if (WiFi.status() == WL_CONNECTED) return "sta_connected";
  return "sta_connecting";
}

void handleRoot() {
  webServer.send_P(200, "text/html", LAB2_INDEX_HTML);
}

void handleSettingsGet() {
  settings = settingsStore.load();
  JsonDocument document;
  document["ssid"] = wifiPreferences.getString("ssid", "");
  document["server_url"] = settings.serverUrl;
  document["poll_interval_ms"] = settings.pollIntervalMs;
  document["dev_http"] = settings.allowDevHttp;
  document["atom_key_configured"] = !settings.atomKey.isEmpty();
  document["wifi_mode"] = wifiModeName();
  document["post_office_status"] = postOfficeClient.statusText();
  // Wi-Fi password and Atom key are intentionally never returned.
  String response;
  serializeJson(document, response);
  webServer.send(200, "application/json", response);
}

void handleSettingsPost() {
  postoffice::Settings candidate = settingsStore.load();
  candidate.serverUrl = webServer.arg("server_url");
  candidate.serverUrl.trim();
  candidate.allowDevHttp = webServer.arg("dev_http") == "1";
  const String key = webServer.arg("atom_key");
  if (!key.isEmpty()) candidate.atomKey = key;

  const String interval = webServer.arg("poll_interval_ms");
  if (interval.isEmpty()) {
    webServer.send(400, "application/json", "{\"error\":\"poll_interval_required\"}");
    return;
  }
  candidate.pollIntervalMs = interval.toInt();
  const postoffice::ConfigInput input{candidate.serverUrl.c_str(), candidate.atomKey.c_str(),
                                      candidate.pollIntervalMs, candidate.allowDevHttp};
  const postoffice::ConfigResult validation = postoffice::validateConfig(input);
  if (!validation.ok()) {
    webServer.send(400, "application/json",
                   "{\"error\":" + jsonString(validation.reason) + "}");
    return;
  }
  if (!settingsStore.save(candidate)) {
    webServer.send(500, "application/json", "{\"error\":\"settings_store_failed\"}");
    return;
  }

  const String ssid = webServer.arg("ssid");
  const String wifiPassword = webServer.arg("wifi_pass");
  if (!ssid.isEmpty()) {
    wifiPreferences.putString("ssid", ssid);
    if (!wifiPassword.isEmpty()) wifiPreferences.putString("pass", wifiPassword);
  }
  settings = candidate;
  postOfficeClient.configure(settings);
  logLine("post-office settings saved; secrets not logged");
  webServer.send(200, "application/json", "{\"saved\":true,\"wifi_restart_required\":true}");
}

void handlePostOfficeTest() {
  // Deliberately calls only /health; it cannot claim or execute a job.
  const String result = postOfficeClient.testConnection();
  const bool ok = result == "health_ok";
  webServer.send(ok ? 200 : 503, "application/json",
                 "{\"result\":" + jsonString(result) + "}");
}

void handleState() {
  const postoffice::PendingResult pending = persistentState.pendingResult();
  JsonDocument document;
  document["device_id"] = deviceId();
  document["wifi"] = wifiModeName();
  document["post_office"] = postOfficeClient.statusText();
  document["active_job_id"] = persistentState.activeJobId();
  document["pending_result_id"] = pending.present ? pending.jobId : "";
  document["pressure_available"] = false;
  document["pressure"] = nullptr;
  String response;
  serializeJson(document, response);
  webServer.send(200, "application/json", response);
}

void networkTask(void*) {
  bool lastConnected = false;
  for (;;) {
    webServer.handleClient();
    if (accessPointActive) dnsServer.processNextRequest();
    const bool connected = WiFi.status() == WL_CONNECTED;
    if (connected != lastConnected) {
      logLine(connected ? "Wi-Fi connected" : "Wi-Fi disconnected");
      lastConnected = connected;
    }
    postOfficeClient.tick(millis());
    vTaskDelay(1);
  }
}

void pollSerialStationBoundary() {
  while (Serial.available()) {
    const char character = static_cast<char>(Serial.read());
    if (character == '\n' || character == '\r') {
      if (!serialLine.isEmpty()) {
        const postoffice::PendingResult before = persistentState.pendingResult();
        if (stationBridge.handleResultLine(serialLine, persistentState)) {
          const postoffice::PendingResult after = persistentState.pendingResult();
          if (!before.present && after.present) logLine("local station result queued");
        }
        // Non-post-office JSON can be handed to the Lab 1 pump parser when
        // the projects are merged. That hardware integration remains TODO.
        serialLine = "";
      }
    } else if (character >= 0x20 && serialLine.length() < 512) {
      serialLine += character;
    }
  }
}

}  // namespace

void setup() {
  auto config = M5.config();
  M5.begin(config);
  M5.Display.setRotation(0);
  Serial.begin(115200);

  wifiPreferences.begin("wifi", false);  // compatible with Lab 1 keys
  settingsStore.begin();
  persistentState.begin();
  stationBridge.begin();
  settings = settingsStore.load();
  postOfficeClient.begin(deviceId(), persistentState, stationBridge, POST_OFFICE_ROOT_CA);
  postOfficeClient.configure(settings);

  startNetwork();
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  webServer.on("/", HTTP_GET, handleRoot);
  webServer.on("/settings", HTTP_GET, handleSettingsGet);
  webServer.on("/settings", HTTP_POST, handleSettingsPost);
  webServer.on("/state", HTTP_GET, handleState);
  webServer.on("/test/post-office", HTTP_POST, handlePostOfficeTest);
  webServer.onNotFound([]() {
    if (accessPointActive) handleRoot();
    else webServer.send(404, "application/json", "{\"error\":\"not_found\"}");
  });
  webServer.begin();

  xTaskCreatePinnedToCore(networkTask, "lab2-net", 12288, nullptr, 1, nullptr, 0);
  logLine("Lab 2 foundation ready; real station/hardware validation TODO");
}

void loop() {
  M5.update();
  pollSerialStationBoundary();
  // Future Lab 1 display/button and pressure/pump work remains on core 1.
  delay(2);
}
