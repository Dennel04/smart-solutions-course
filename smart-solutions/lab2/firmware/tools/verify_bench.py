"""Inspect local build artifacts only; never open a serial port or print secrets."""
import argparse
import hashlib
import re
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nm", required=True, help="xtensa-esp32s3-elf-nm executable")
    parser.add_argument("--sdk-dir", type=Path, default=Path.home() /
                        ".platformio/packages/framework-arduinoespressif32/tools/sdk/esp32s3")
    args = parser.parse_args()
    build = Path(__file__).resolve().parents[1] / ".pio/build/atoms3r"
    image = (build / "firmware.bin").read_bytes()
    marker = b"LAB2_BENCH_MODE=1;execution=disabled;nvs=blocked"
    if marker not in image:
        raise SystemExit("FAIL: bench marker missing")
    symbols = subprocess.check_output([args.nm, "-C", str(build / "firmware.elf")], text=True)
    forbidden = ("postoffice::", "Preferences::", "configTime", "HTTPClient::",
                 "WiFiSTAClass::", "LittleFS", "recoverAmbiguousClaim")
    for name in forbidden:
        if name in symbols:
            raise SystemExit(f"FAIL: forbidden live symbol: {name}")
    for name in ("nvs_flash_init", "nvs_flash_init_partition", "nvs_open",
                 "nvs_open_from_partition"):
        if f" T __wrap_{name}\n" not in symbols:
            raise SystemExit(f"FAIL: NVS guard missing: {name}")
        if f" T {name}\n" in symbols:
            raise SystemExit(f"FAIL: original NVS entrypoint linked: {name}")
    print("ISOLATION PASS: BENCH_MODE=1 marker, NVS guards, no live client/store/STA symbols")
    print("firmware.bin SHA-256:", hashlib.sha256(image).hexdigest())
    sdkconfig = (args.sdk_dir / "sdkconfig").read_text()
    version = (args.sdk_dir / "include/esp_common/include/esp_idf_version.h").read_text()
    parts = [re.search(r"#define ESP_IDF_VERSION_" + part + r"\s+(\d+)", version)
             for part in ("MAJOR", "MINOR", "PATCH")]
    if not all(parts):
        raise SystemExit("NOT READY: SDK version could not be verified")
    print("SDK ESP-IDF:", ".".join(part.group(1) for part in parts))
    flash_dump = any(name in symbols for name in
                     ("esp_core_dump_to_flash", "esp_core_dump_flash_write"))
    configured = "CONFIG_ESP_COREDUMP_ENABLE_TO_FLASH=y" in sdkconfig.splitlines()
    if flash_dump or configured:
        print(f"NOT READY: flash coredump: SDK configured={configured}, ELF linked={flash_dump}")
        print("NVS guards do not block panic dumps or bootloader/OTA metadata writes.")
        raise SystemExit(2)
    # An unrecognised SDK/config must not turn a source-only check into approval.
    raise SystemExit("NOT READY: SDK changed; review panic/bootloader paths separately")


if __name__ == "__main__":
    main()
