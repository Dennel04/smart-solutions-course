// Excluded from BENCH; the normal wildcard build sees an empty translation unit.
#if defined(HEALTH_ONLY) && HEALTH_ONLY == 1
#include "build_mode.h"
#if !BENCH_MODE
#error "Health-only requires the isolated NVS guards, never normal mode"
#endif
#include <Arduino.h>
#include <ArduinoJson.h>
#include <M5Unified.h>
#include <WiFiClientSecure.h>
#include <bootloader_random.h>
#include <esp_event.h>
#include <esp_log.h>
#include <esp_netif.h>
#include <esp_random.h>
#include <esp_wifi.h>
#include <lwip/netdb.h>
#include <mbedtls/x509_crt.h>
#include "bench_runtime.h"
#include "health_only_runtime.h"
#include "health_only_protocol.h"
#include "health_only_tls.h"
#include "post_office_ca.h"

#ifndef MBEDTLS_SSL_KEEP_PEER_CERTIFICATE
#error "Health-only requires access to the peer certificate chain"
#endif

namespace {
healthonly::Gate gate;
char input[512]{};
size_t inputSize = 0;
char challenge[17]{};  // public freshness nonce, not a credential
bool hello = false, stopped = false;
uint32_t inputStarted = 0, helloAt = 0;

void report(const char* status) {
  Serial.print("# HEALTH "); Serial.println(status);
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setCursor(2, 2);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.setTextSize(1);
  M5.Display.println("HEALTH ONLY");
  M5.Display.println("execution disabled");
  M5.Display.println(status);
}

struct Entropy {
  void enable() { bootloader_random_enable(); }
  bool fill(uint8_t* b, size_t n) { esp_fill_random(b, n); return true; }
  void disable() { bootloader_random_disable(); }
};

struct HealthIo {
  WiFiClientSecure client;
  mbedtls_x509_crt root;
  uint32_t authorizedAt = 0;
  int64_t utc = 0;
  bool radio = false;
  HealthIo() { mbedtls_x509_crt_init(&root); }
  ~HealthIo() { mbedtls_x509_crt_free(&root); }
  bool caReady() {
    return POST_OFFICE_ROOT_CA &&
        mbedtls_x509_crt_parse(&root, reinterpret_cast<const unsigned char*>(POST_OFFICE_ROOT_CA),
                               std::strlen(POST_OFFICE_ROOT_CA) + 1) == 0 &&
        root.raw.p && root.ca_istrue && !root.next;  // one reviewed trust anchor
  }
  bool wifi(const healthonly::Credentials& c) {
    utc = c.utc; authorizedAt = millis();
    if (esp_netif_init() != ESP_OK || esp_event_loop_create_default() != ESP_OK ||
        !esp_netif_create_default_wifi_sta()) return false;
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    init.nvs_enable = 0;
    if (esp_wifi_init(&init) != ESP_OK) return false;
    radio = true;
    wifi_config_t config{};
    std::memcpy(config.sta.ssid, c.ssid, std::strlen(c.ssid));
    std::memcpy(config.sta.password, c.password, std::strlen(c.password));
    config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    const bool configured = esp_wifi_set_storage(WIFI_STORAGE_RAM) == ESP_OK &&
        esp_wifi_set_mode(WIFI_MODE_STA) == ESP_OK &&
        esp_wifi_set_config(WIFI_IF_STA, &config) == ESP_OK;
    healthonly::wipe(&config, sizeof(config));
    if (!configured || esp_wifi_start() != ESP_OK || esp_wifi_connect() != ESP_OK) return false;
    esp_netif_t* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    while (millis() - authorizedAt < 15000) {
      esp_netif_ip_info_t ip{};
      if (netif && esp_netif_get_ip_info(netif, &ip) == ESP_OK && ip.ip.addr != 0) {
        report("WIFI CONNECTED"); return true;
      }
      delay(20);
    }
    return false;  // no reconnect callback, AP fallback or retry
  }
  bool tls() {
    // lwIP resolver has finite SDK retries. No Arduino WiFi startup is used.
    addrinfo hints{}, *answer = nullptr;
    hints.ai_family = AF_INET; hints.ai_socktype = SOCK_STREAM;
    const int result = getaddrinfo(healthonly::kHost, "443", &hints, &answer);
    if (result != 0 || !answer) { if (answer) freeaddrinfo(answer); return false; }
    IPAddress address(reinterpret_cast<sockaddr_in*>(answer->ai_addr)->sin_addr.s_addr);
    freeaddrinfo(answer);
    if (millis() - authorizedAt >= healthonly::kSessionMs) return false;
    client.setTimeout(5);  // this SDK uses seconds, including socket timeout
    client.setHandshakeTimeout(8);
    client.setCACert(POST_OFFICE_ROOT_CA);
    // Public SDK overload preserves hostname/SNI while using the resolved IP.
    return client.connect(address, 443, healthonly::kHost, POST_OFFICE_ROOT_CA, nullptr, nullptr) == 1;
  }
  bool validChain() {
    if (millis() - authorizedAt >= healthonly::kSessionMs) return false;
    const mbedtls_x509_crt* peer = client.getPeerCertificate();
    if (!peer) return false;
    const bool verified = healthonly::checkedChain(const_cast<mbedtls_x509_crt*>(peer), &root,
        utc + (millis() - authorizedAt) / 1000, MBEDTLS_X509_BADCERT_OTHER,
        [](mbedtls_x509_crt* chain, mbedtls_x509_crt* ca, const char* host,
           uint32_t* flags, int (*callback)(void*, mbedtls_x509_crt*, int, uint32_t*), void* ctx) {
          return mbedtls_x509_crt_verify(chain, ca, nullptr, host, flags, callback, ctx);
        });
    if (!verified) return false;
    report("TLS VERIFIED"); return true;
  }
  bool getHealth() {
    // No HTTP library, redirect handling, authentication, or caller-supplied URL.
    if (client.write(reinterpret_cast<const uint8_t*>(healthonly::kRequest),
                     sizeof(healthonly::kRequest) - 1) != sizeof(healthonly::kRequest) - 1) return false;
    char response[2049]{};
    size_t n = 0;
    const uint32_t started = millis();
    bool closed = false;
    while (millis() - started < 8000 && n < sizeof(response) - 1) {
      while (millis() - started < 8000 && client.available() && n < sizeof(response) - 1) {
        const int byte = client.read();
        if (byte < 0 || byte == 0) return false;
        response[n++] = static_cast<char>(byte);
      }
      if (!client.connected() && !client.available()) { closed = true; break; }
      delay(2);
    }
    if (!closed || millis() - started >= 8000 || n == sizeof(response)-1) return false;
    return healthonly::responseValid(response, n);
  }
  bool close() {
    client.stop();
    if (!radio) return true;
    esp_wifi_disconnect();  // stop/deinit below are the authoritative shutdown checks
    const bool didStop = esp_wifi_stop() == ESP_OK;
    const bool didDeinit = esp_wifi_deinit() == ESP_OK;
    radio = false;  // no automatic cleanup/reconnect retry on failure
    return didStop && didDeinit;
  }
  void report(const char* status) { ::report(status); }
};

void reject() {
  gate.take(); stopped = true;
  healthonly::wipe(input, sizeof(input));
  report("INPUT ERROR; STOP");
}
void line() {
  if (!hello) {
    if (std::strcmp(input, "HELLO") != 0) { reject(); return; }
    hello = true; helloAt = millis();
    Serial.print("# HEALTH CHALLENGE "); Serial.println(challenge);
    return;
  }
  healthonly::Credentials c;
  if (!healthonly::parseFrame(input, challenge, c)) {
    healthonly::wipe(&c, sizeof(c)); reject(); return;
  }
  healthonly::wipe(input, sizeof(input));
  stopped = true;
  HealthIo io;
  healthonly::runOnce(gate, c, io);
}
}  // namespace

void setup() {
  esp_log_level_set("*", ESP_LOG_NONE);  // driver diagnostics must not expose SSID
  auto config = M5.config(); M5.begin(config);
  M5.Display.setRotation(0); M5.Display.setBrightness(128);
  Serial.begin(115200);
  Serial.println(healthonly::kMarker);
  Entropy entropy;
  if (!bench::generatePassword(entropy, challenge, sizeof(challenge))) {
    stopped = true; report("NONCE ERROR; STOP"); return;
  }
  report("WAITING FOR USB");
}
void loop() {
  M5.update();
  if (!stopped && ((hello && millis()-helloAt >= 60000) ||
      (inputSize && millis()-inputStarted >= 10000))) reject();
  while (!stopped && Serial.available()) {
    const int c = Serial.read();
    if (c == '\n') {
      input[inputSize] = '\0'; line();
      healthonly::wipe(input, sizeof(input)); inputSize = 0;
    } else if (c < 32 || c > 126 || inputSize >= sizeof(input)-1) reject();
    else {
      if (!inputSize) inputStarted = millis();
      input[inputSize++] = static_cast<char>(c);
    }
  }
  delay(2);
}
#endif
