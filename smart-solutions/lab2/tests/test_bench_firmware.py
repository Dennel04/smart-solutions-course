"""Host-only checks of the isolated build and actual NVS guard implementation."""
import configparser
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

FIRMWARE = Path(__file__).resolve().parents[1] / "firmware"


def test_bench_build_excludes_all_live_modules():
    config = configparser.ConfigParser(interpolation=None)
    config.read(FIRMWARE / "platformio.ini")
    assert config["platformio"]["default_envs"] == "atoms3r"
    bench = config["env:atoms3r"]
    assert "-DBENCH_MODE=1" in bench["build_flags"].split()
    assert bench["build_src_filter"].split() == [
        "-<*>", "+<bench_main.cpp>", "+<bench_nvs_guard.cpp>",
        "+<core/pressure_model.cpp>",
    ]
    for symbol in ("nvs_flash_init", "nvs_flash_init_partition", "nvs_open",
                   "nvs_open_from_partition"):
        assert f"-Wl,--wrap={symbol}" in bench["build_flags"].split()
    normal = config["env:atoms3r_normal"]
    assert "-DBENCH_MODE=0" in normal["build_flags"].split()
    assert "--wrap=" not in normal["build_flags"]
    assert "-<bench_main.cpp>" in normal["build_src_filter"]
    assert "-<bench_nvs_guard.cpp>" in normal["build_src_filter"]


def test_bench_ap_is_protected_and_configured_before_radio_start():
    code = (FIRMWARE / "src/bench_main.cpp").read_text()
    assert "init.nvs_enable = 0;" in code
    assert "esp_wifi_set_storage(WIFI_STORAGE_RAM)" in code
    assert "esp_wifi_set_mode(WIFI_MODE_AP)" in code
    assert "ap.ap.authmode = WIFI_AUTH_WPA2_PSK;" in code
    assert "ap.ap.max_connection = 1;" in code
    assert code.index("esp_wifi_set_config(") < code.index("esp_wifi_start()")
    assert code.index("bootloader_random_enable()") < code.index("esp_fill_random(")
    startup = code[code.index("bool protectedAp()") : code.index("void startFailed()")]
    assert startup.index("bench::generatePassword(") < startup.index("esp_wifi_init(")
    assert startup.index("return false;") < startup.index("esp_wifi_init(")
    assert startup.index("esp_wifi_start()") < startup.index("analogReadResolution(")
    runtime = (FIRMWARE / "include/bench_runtime.h").read_text()
    assert runtime.index("source.enable()") < runtime.index("source.fill(")
    assert runtime.index("source.fill(") < runtime.index("source.disable()")
    assert runtime.index("source.disable()") < runtime.index("const bool valid =")
    assert "Serial.println(bench::kBuildMarker)" in code
    for forbidden in ("Preferences", "LittleFS", "WiFi.begin", "WIFI_MODE_APSTA",
                      "configTime(", "PostOfficeClient", "StationBridge",
                      "Serial.read", "Serial.available", "post_office_ca"):
        assert forbidden not in code
    serial_lines = [line for line in code.splitlines() if "Serial." in line]
    assert all("password" not in line and "random" not in line for line in serial_lines)


def test_bench_pressure_cannot_load_old_calibration():
    code = (FIRMWARE / "src/bench_main.cpp").read_text()
    assert "const pressure::Calibration calibration{};" in code
    assert 'response["calibrated"] = false;' in code
    assert 'response["voltage_v"] = nullptr;' in code
    assert 'response["pressure_kpa"] = nullptr;' in code


def test_actual_nvs_guards_block_read_and_write_handles(tmp_path):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("host C++ compiler not available")
    # Stub only the SDK declarations, compile the real bench_nvs_guard.cpp.
    (tmp_path / "nvs.h").write_text(
        "#pragma once\nusing esp_err_t=int; using nvs_handle_t=unsigned;\n"
        "enum nvs_open_mode_t {NVS_READONLY, NVS_READWRITE};\n"
        "constexpr int ESP_OK=0, ESP_ERR_NVS_NOT_INITIALIZED=0x1101;\n"
    )
    (tmp_path / "nvs_flash.h").write_text('#include "nvs.h"\n')
    main = tmp_path / "test.cpp"
    main.write_text(
        '#include "nvs.h"\n#include <cassert>\n'
        'extern "C" int __wrap_nvs_flash_init();\n'
        'extern "C" int __wrap_nvs_flash_init_partition(const char*);\n'
        'extern "C" int __wrap_nvs_open(const char*,nvs_open_mode_t,unsigned*);\n'
        'extern "C" int __wrap_nvs_open_from_partition(const char*,const char*,nvs_open_mode_t,unsigned*);\n'
        'int main(){unsigned h=123; assert(__wrap_nvs_flash_init()==0);'
        'assert(__wrap_nvs_flash_init_partition("nvs")==0);'
        'for(auto mode:{NVS_READONLY,NVS_READWRITE}){'
        'assert(__wrap_nvs_open("wifi",mode,&h)==ESP_ERR_NVS_NOT_INITIALIZED);'
        'assert(__wrap_nvs_open_from_partition("nvs","postoffice",mode,&h)==ESP_ERR_NVS_NOT_INITIALIZED);'
        'assert(h==123);}}\n'
    )
    # initializer_list is provided explicitly, not by the real SDK.
    binary = tmp_path / "guard-test"
    subprocess.run([compiler, "-std=c++17", "-include", "initializer_list",
                    "-I", str(tmp_path), "-I", str(FIRMWARE / "include"),
                    str(FIRMWARE / "src/bench_nvs_guard.cpp"), str(main),
                    "-o", str(binary)], check=True, capture_output=True)
    subprocess.run([str(binary)], check=True, capture_output=True)


def test_compile_time_mode_rejects_invalid_flag_and_defaults_to_bench(tmp_path):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("host C++ compiler not available")
    source = tmp_path / "mode.cpp"
    source.write_text('#include "build_mode.h"\nstatic_assert(BENCH_MODE==EXPECTED);\n')
    for flags in (["-DEXPECTED=1"], ["-DBENCH_MODE=0", "-DEXPECTED=0"],
                  ["-DBENCH_MODE=1", "-DEXPECTED=1"]):
        subprocess.run([compiler, "-std=c++17", "-fsyntax-only", "-I",
                        str(FIRMWARE / "include"), *flags, str(source)],
                       check=True, capture_output=True)
    invalid = subprocess.run([compiler, "-std=c++17", "-fsyntax-only", "-I",
                              str(FIRMWARE / "include"), "-DBENCH_MODE=2",
                              "-DEXPECTED=2", str(source)], capture_output=True)
    assert invalid.returncode != 0


@pytest.mark.parametrize("configured,linked", [(True, True), (True, False), (False, True)])
def test_bench_verifier_does_not_approve_flash_coredump(
        tmp_path, monkeypatch, capsys, configured, linked):
    sdk = tmp_path / "sdk"
    includes = sdk / "include/esp_common/include"
    includes.mkdir(parents=True)
    (sdk / "sdkconfig").write_text(
        "CONFIG_ESP_COREDUMP_ENABLE_TO_FLASH=y\n" if configured else "")
    (includes / "esp_idf_version.h").write_text(
        "#define ESP_IDF_VERSION_MAJOR 4\n#define ESP_IDF_VERSION_MINOR 4\n"
        "#define ESP_IDF_VERSION_PATCH 7\n")
    symbols = "".join(f"00000000 T __wrap_{name}\n" for name in
                      ("nvs_flash_init", "nvs_flash_init_partition", "nvs_open",
                       "nvs_open_from_partition"))
    if linked:
        symbols += "00000000 T esp_core_dump_to_flash\n"
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **kw: symbols)
    monkeypatch.setattr(Path, "read_bytes", lambda _: (
        b"synthetic image LAB2_BENCH_MODE=1;execution=disabled;nvs=blocked"))
    monkeypatch.setattr(sys, "argv", ["verify_bench.py", "--nm", "synthetic-nm",
                                      "--sdk-dir", str(sdk)])
    spec = importlib.util.spec_from_file_location(
        "bench_verify_test", FIRMWARE / "tools/verify_bench.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit) as result:
        module.main()
    assert result.value.code == 2
    assert "NOT READY: flash coredump" in capsys.readouterr().out
