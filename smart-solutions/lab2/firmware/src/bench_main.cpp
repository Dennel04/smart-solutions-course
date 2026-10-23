#include "build_mode.h"
#if BENCH_MODE
#include <Arduino.h>
#include <ArduinoJson.h>
#include <M5Unified.h>
#include <WebServer.h>
#include <bootloader_random.h>
#include <esp_event.h>
#include <esp_netif.h>
#include <esp_random.h>
#include <esp_wifi.h>

#include "bench_runtime.h"
#include "pressure_model.h"

namespace {
WebServer server(80);
bool ready = false;
const pressure::Calibration calibration{};  // RAM only, never loaded from NVS

struct HardwareEntropy {
  void enable() { bootloader_random_enable(); }
  bool fill(uint8_t* bytes, size_t size) {
    esp_fill_random(bytes, size);  // SDK returns void; validate output separately
    return true;
  }
  void disable() { bootloader_random_disable(); }
};

const char kPage[] PROGMEM = R"HTML(
<!doctype html><html lang="et"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AtomS3R BENCH</title><body>
<h1>BENCH — täitmine keelatud</h1>
<p>Ainult kohalik USB/AP kontroll. STA, postkontor ja robotikanal on keelatud.
Salvestatud seadeid ei loeta ega muudeta. Rõhukalibratsioon: not_calibrated.</p>
<h2>Seaded (ainult lugemine)</h2>
<fieldset disabled><label>Wi-Fi SSID <input placeholder="NVS ei loeta"></label>
<label>Postkontori URL <input placeholder="NVS ei loeta"></label>
<button>Salvesta seaded (keelatud)</button>
<button>Testi postkontorit (keelatud)</button></fieldset>
<p>Ilma andurita on ADC ujuv; see ei ole rõhumõõtmine.</p>
<button id="test">Loe G5 ADC (kohalik)</button><pre id="reading">not_calibrated</pre>
<script>document.getElementById('test').onclick=async()=>{try{
const r=await fetch('/test/pressure',{method:'POST'});
document.getElementById('reading').textContent=await r.text();
}catch(e){document.getElementById('reading').textContent='Kohalik lugemine ebaõnnestus';}};
</script></body></html>)HTML";

struct LocalIo {
  void displayAndSerial() {
    auto config = M5.config();
    config.clear_display = true;
    M5.begin(config);
    M5.Display.setRotation(0);
    M5.Display.setBrightness(128);
    Serial.begin(115200);
    Serial.println(bench::kBuildMarker);
    M5.Display.fillScreen(TFT_BLACK);
    M5.Display.setTextColor(TFT_GREEN, TFT_BLACK);
    M5.Display.setTextSize(1);
    M5.Display.setCursor(2, 2);
    M5.Display.println("BENCH");
    M5.Display.println("execution disabled");
  }

  bool protectedAp() {
    // Complete SAR entropy use before Wi-Fi init or local ADC setup.
    wifi_config_t ap{};
    HardwareEntropy entropy;
    if (!bench::generatePassword(entropy, reinterpret_cast<char*>(ap.ap.password),
                                 sizeof(ap.ap.password))) return false;
    // Configure AP fully BEFORE starting the radio: no transient open AP/STA.
    if (esp_netif_init() != ESP_OK || esp_event_loop_create_default() != ESP_OK) {
      bench::clearSecret(&ap, sizeof(ap));
      return false;
    }
    esp_netif_t* netif = esp_netif_create_default_wifi_ap();
    if (netif == nullptr) {
      bench::clearSecret(&ap, sizeof(ap));
      return false;
    }
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    init.nvs_enable = 0;
    if (esp_wifi_init(&init) != ESP_OK ||
        esp_wifi_set_storage(WIFI_STORAGE_RAM) != ESP_OK ||
        esp_wifi_set_mode(WIFI_MODE_AP) != ESP_OK) {
      bench::clearSecret(&ap, sizeof(ap));
      return false;
    }
    std::strcpy(reinterpret_cast<char*>(ap.ap.ssid), bench::kSsid);
    ap.ap.ssid_len = std::strlen(bench::kSsid);
    ap.ap.authmode = WIFI_AUTH_WPA2_PSK;
    ap.ap.max_connection = 1;
    ap.ap.channel = 1;
    if (esp_wifi_set_config(WIFI_IF_AP, &ap) != ESP_OK ||
        esp_wifi_start() != ESP_OK) {
      bench::clearSecret(&ap, sizeof(ap));
      return false;
    }
    esp_netif_ip_info_t ip{};
    if (esp_netif_get_ip_info(netif, &ip) != ESP_OK) {
      bench::clearSecret(&ap, sizeof(ap));
      return false;
    }
    char address[16];
    snprintf(address, sizeof(address), IPSTR, IP2STR(&ip.ip));
    M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
    M5.Display.println(bench::kSsid);
    M5.Display.println(address);
    M5.Display.println("AP password:");
    // LCD only, split to fit 128 pixels. Never serial, HTTP or NVS.
    M5.Display.write(ap.ap.password, 8);
    M5.Display.println();
    M5.Display.write(ap.ap.password + 8, 8);
    M5.Display.println();
    bench::clearSecret(&ap, sizeof(ap));
    pinMode(5, INPUT);
    analogReadResolution(12);
    analogSetPinAttenuation(5, ADC_11db);
    return true;
  }

  void startFailed() {
    esp_wifi_stop();
    Serial.println("# BENCH AP failed; no fallback; execution disabled");
    M5.Display.println("AP failed; STOP");
  }
  void localServer() {
    server.onNotFound([this]() {
      bench::request(server.method() == HTTP_GET, server.method() == HTTP_POST,
                     server.uri().c_str(), *this);
    });
    server.begin();
    Serial.println("# BENCH protected local AP ready; NVS blocked");
  }
  void serveLocal() { server.handleClient(); }
  void page() { server.send_P(200, "text/html; charset=utf-8", kPage); }
  void settings() {
    server.send(200, "application/json",
                "{\"bench_mode\":true,\"read_only\":true,\"stored_settings_loaded\":false,"
                "\"wifi_mode\":\"ap_only\",\"post_office_status\":\"bench_disabled\"}");
  }
  void state() {
    server.send(200, "application/json",
                "{\"bench_mode\":true,\"execution_enabled\":false,"
                "\"nvs_access\":\"blocked\",\"pressure_calibrated\":false}");
  }
  void pressureSettings() {
    server.send(200, "application/json",
                "{\"calibrated\":false,\"adc_pin\":\"G5\",\"volts_per_count\":null,"
                "\"voltage_offset_v\":null,\"kpa_per_volt\":null,\"pressure_offset_kpa\":null}");
  }
  void pressureTest() {
    uint32_t sum = 0;
    for (int i = 0; i < 8; ++i) sum += analogRead(5);
    const auto reading = pressure::convertReading(sum / 8, calibration);
    JsonDocument response;
    response["status"] = reading.status;
    response["raw_adc"] = reading.rawAdc;
    response["calibrated"] = false;
    response["sensor_connected"] = "not_verified";
    response["voltage_v"] = nullptr;
    response["pressure_kpa"] = nullptr;
    String json;
    serializeJson(response, json);
    server.send(reading.code == pressure::ReadingCode::InvalidRawAdc ? 503 : 200,
                "application/json", json);
  }
  void blocked() {
    server.send(423, "application/json", "{\"error\":\"bench_read_only\"}");
  }
  void notFound() { server.send(404, "application/json", "{\"error\":\"not_found\"}"); }
};
LocalIo io;
}  // namespace

void setup() { ready = bench::start(io); }
void loop() {
  M5.update();
  bench::tick(ready, io);
  delay(2);
}
#endif
