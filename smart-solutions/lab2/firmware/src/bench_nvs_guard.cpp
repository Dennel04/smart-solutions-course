#include "build_mode.h"
#if BENCH_MODE
#include <nvs.h>
#include <nvs_flash.h>

// Arduino initArduino() normally initialises NVS and may erase a damaged NVS
// partition. Pretend initialisation succeeded, but never initialise/open it.
// M5GFX autodetection can still run; its optional NVS cache is inaccessible.
// The bench AP uses wifi_init_config_t::nvs_enable=0 and WIFI_STORAGE_RAM.
extern "C" esp_err_t __wrap_nvs_flash_init() { return ESP_OK; }
extern "C" esp_err_t __wrap_nvs_flash_init_partition(const char*) { return ESP_OK; }
extern "C" esp_err_t __wrap_nvs_open(const char*, nvs_open_mode_t,
                                     nvs_handle_t*) {
  return ESP_ERR_NVS_NOT_INITIALIZED;
}
extern "C" esp_err_t __wrap_nvs_open_from_partition(
    const char*, const char*, nvs_open_mode_t, nvs_handle_t*) {
  return ESP_ERR_NVS_NOT_INITIALIZED;
}
#endif
