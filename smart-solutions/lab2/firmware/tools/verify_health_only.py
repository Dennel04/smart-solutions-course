"""Read local artifacts only. An isolation PASS is not permission to upload."""
import argparse
import hashlib
import re
from pathlib import Path
import subprocess

MARKER = b"LAB2_HEALTH_ONLY=1;execution=disabled;nvs=blocked;one_get"
ROOT_SHA256 = "69729b8e15a86efc177a57afb7171dfc64add28c2fca8cf1507e34453ccb1470"


def trusted_root_present(image):
    # Public certificate only, in memory; never print PEM or read private headers.
    blocks = re.findall(b"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", image, re.S)
    for block in blocks:
        result = subprocess.run(["openssl", "x509", "-outform", "DER"],
                                input=block, capture_output=True, check=False)
        if result.returncode == 0 and hashlib.sha256(result.stdout).hexdigest() == ROOT_SHA256:
            return True
    return False


def inspect(image, symbols, sdk):
    if MARKER not in image:
        raise ValueError("health-only marker missing")
    forbidden = ("postoffice::", "Preferences::", "StationBridge", "PersistentState",
                 "configTime", "sntp_init", "HTTPClient::", "LittleFS", "WebServer::",
                 "recoverAmbiguousClaim", "WiFiSTAClass::begin", "bench::start")
    if any(name in symbols for name in forbidden):
        raise ValueError("live module found")
    for name in ("nvs_flash_init", "nvs_flash_init_partition", "nvs_open", "nvs_open_from_partition"):
        if f" T __wrap_{name}\n" not in symbols or f" T {name}\n" in symbols:
            raise ValueError("NVS guard missing/original entrypoint linked")
    for name in ("mbedtls_x509_crt_verify", "mbedtls_ssl_set_hostname", "mbedtls_x509_crt_parse",
                 "healthonly::checkCertificate", "healthonly::responseValid"):
        if name not in symbols:
            raise ValueError("TLS/protocol verification missing")
    if b"GET /health HTTP/1.1" not in image or b"narva2.roboarena.org" not in image:
        raise ValueError("fixed request missing")
    if b"-----BEGIN CERTIFICATE-----" not in image:
        raise ValueError("local trust anchor missing")
    if "CONFIG_MBEDTLS_SSL_KEEP_PEER_CERTIFICATE=y" not in sdk:
        raise ValueError("SDK does not retain peer certificates")
    return "CONFIG_ESP_COREDUMP_ENABLE_TO_FLASH=y" in sdk or "esp_core_dump_to_flash" in symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nm", required=True)
    args = parser.parse_args()
    firmware = Path(__file__).resolve().parents[1]
    build = firmware / ".pio/build/atoms3r_health"
    sdk = Path.home() / ".platformio/packages/framework-arduinoespressif32/tools/sdk/esp32s3/sdkconfig"
    image = (build / "firmware.bin").read_bytes()
    symbols = subprocess.check_output([args.nm, "-C", str(build / "firmware.elf")], text=True)
    try:
        coredump = inspect(image, symbols, sdk.read_text())
        if not trusted_root_present(image):
            raise ValueError("reviewed ISRG Root X2 fingerprint not found in binary")
    except ValueError as error:
        raise SystemExit("NOT READY: " + str(error))
    print("ISOLATION PASS: health-only marker, NVS guards, fixed GET, TLS/date code; no live job modules")
    print("CA PASS: reviewed ISRG Root X2 SHA-256 matches embedded certificate")
    print("SHA-256:", hashlib.sha256(image).hexdigest())
    if coredump:
        print("LIMITATION: SDK flash-coredump remains enabled; RAM may contain Wi-Fi credentials.")
    print("REVIEW ONLY: no hardware HTTPS test; upload requires separate authorization, including residual flash risk.")


if __name__ == "__main__":
    main()
