# XIAO ESP32S3 Sense tool-camera firmware

See on Smart Solutions Lab 2 eraldiseisev PlatformIO projekt. Seeed Studio
XIAO ESP32S3 Sense annab station'ile kohaliku Wi-Fi kaudu JPEG snapshot'i.
Seade ei tunne dropleti postkontorit, MG400-t ega VPN-i ning ei saada pilte ise
kuhugi. HTTP serverit ei tohi internetti port-forward'ida. Lab 3 võib hiljem
anda VPN-i kaudu ligipääsu station'i lehele, mitte avalikustada XIAO serverit.

> **Software status:** hardware build ja native unit tests läbivad. Päris XIAO,
> kaamera, Wi-Fi, pildikvaliteet ja reconnect ei ole veel füüsiliselt testitud.

## PlatformIO

Projekt kasutab Arduino framework'i ainult PlatformIO kaudu:

- environment: `seeed_xiao_esp32s3`;
- ametlik board ID: `seeed_xiao_esp32s3`;
- platform: `espressif32@6.13.0`;
- native-test platform: `native@1.2.1`.

```bash
pio run
pio test -e native
```

Upload'i selle tarkvaralise ettevalmistuse käigus ei tehta. Hilisem füüsiline
upload on eraldi kontrollitud tegevus; käsku `pio run -t upload` praegu ei
kasutata.

## Wi-Fi private configuration

Kopeeri placeholder-fail lokaalselt:

```bash
cp include/wifi_private.example.h include/wifi_private.h
```

Täida `TOOL_CAMERA_WIFI_SSID`, `TOOL_CAMERA_WIFI_PASSWORD` ja valikuline
`TOOL_CAMERA_HOSTNAME`. `wifi_private.h` on `.gitignore` failis ja seda ei tohi
commit'ida. Näidis ei sisalda factory credentials'e. Tühja SSID-ga firmware
build'ib, kirjutab seriali `missing_ssid` ning ei alusta lõputut ühenduskatset.
Parooli seriali, HTTP vastusesse ega logisse ei kirjutata.

Wi-Fi reconnect on mitteblokeeriv ja kasutab piiratud exponential backoff'i
1–30 sekundit. Kaamerat ei reinitialiseerita võrgu reconnect'i ajal.

## Camera pins, sensor ja PSRAM

Pin mapping pärineb Seeed Studio XIAO ESP32S3 Sense camera dokumentatsioonist
ja Arduino-ESP32 `CAMERA_MODEL_XIAO_ESP32S3` näitest:

| Signaal | GPIO | Signaal | GPIO |
| :--- | ---: | :--- | ---: |
| XCLK | 10 | PCLK | 13 |
| SIOD | 40 | SIOC | 39 |
| D0/Y2 | 15 | D1/Y3 | 17 |
| D2/Y4 | 18 | D3/Y5 | 16 |
| D4/Y6 | 14 | D5/Y7 | 12 |
| D6/Y8 | 11 | D7/Y9 | 48 |
| VSYNC | 38 | HREF | 47 |

Official references:

- <https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/>
- <https://wiki.seeedstudio.com/xiao_esp32s3_camera_usage/>
- <https://github.com/espressif/arduino-esp32/tree/2.0.17/libraries/ESP32/examples/Camera/CameraWebServer>

`seeed_xiao_esp32s3` board definition valib 8 MB flash'i, `qio_opi` memory
type'i ja `BOARD_HAS_PSRAM`. Firmware kontrollib lisaks runtime'is
`psramFound()` tulemust ning kasutab kaht `CAMERA_FB_IN_PSRAM` JPEG buffer'it.
PSRAM-i puudumisel jääb HTTP diagnostika pärast Wi-Fi ühendust kasutatavaks,
kuid camera status on `unavailable`; rapid reboot loop'i ei ole.

`esp_camera` driver tuvastab sensori PID pärast initialization'it. `/status`
kasutab driver'i tuvastatud nime; OV2640, OV3660 ja OV5640 on tarkvaraliselt
lubatud. OV3660 jaoks rakendatakse alles pärast detection'it ametliku Arduino
camera näite vflip/brightness/saturation korrektsioon. Meeskonna päris sensor:
**TODO — verify on hardware**.

## Development camera settings

`include/camera_settings.h` sisaldab seadistatavaid frame size'i, JPEG quality,
frame-buffer count'i ja tulevase stream'i FPS-limit'i. Praegused väärtused on
ainult builditavad software defaults.

**TODO — choose final resolution/FPS after real Gridfinity readability,
latency and bandwidth measurements.**

## HTTP contract

Server käivitub ainult station'iga samas lokaalses laborivõrgus.

| Endpoint | Vastus |
| :--- | :--- |
| `GET /status` | JSON: device, camera/wifi state, lokaalne IP, detected sensor, served frames ja uptime |
| `GET /snapshot.jpg` | üks täielik JPEG, `Content-Type: image/jpeg`, `Cache-Control: no-store` |

`/snapshot.jpg` vastab olemasoleva station'i `XiaoCameraConfig.snapshot_url`
lepingule. Station kontrollib JPEG SOI/EOI-d ja moodustab oma lokaalse MJPEG
voo ühise capture worker'i kaudu.

XIAO pidevat `/stream.mjpg` endpoint'i selles aluses teadlikult ei ole.
Snapshot-polling katab olemasoleva station'i lepingu; lõputu synchronous
handler muudaks status/snapshot diagnostika ja frame-buffer ownership'i
hapramaks. MJPEG lisatakse ainult siis, kui päris riistvarakatse näitab selle
vajadust ning implementation säilitab concurrent diagnostics'i.

Snapshot capture on mutex'iga serialiseeritud. Iga edukas
`esp_camera_fb_get()` haru tagastab buffer'i `esp_camera_fb_return()` abil ka
HTTP saatmisvea korral. Poolik JPEG lükatakse tagasi ega suurenda frame counter'it.

## Failure behaviour ja logid

- camera init error jääb `/status` kaudu nähtavaks, kui Wi-Fi töötab;
- puuduva PSRAM-i või kaamera tõttu ei restartita seadet;
- Wi-Fi ühendub uuesti bounded backoff'iga;
- snapshot'i capture/busy/incomplete vead saavad 5xx JSON vastuse;
- boot, camera init, detected sensor, Wi-Fi state/IP ja HTTP start logitakse;
- parooli ega muid saladusi ei logita.

## Hardware TODO

- kinnitada füüsilise mooduli sensor revision;
- laadida firmware XIAO-sse kontrollitud laborietapil;
- kontrollida päris Wi-Fi, `/status` ja `/snapshot.jpg`;
- kontrollida frame-buffer release'i client disconnect'i ja võrgu katkestuse ajal;
- valida lõplik resolution, JPEG quality ja polling FPS pärismõõtmiste põhjal;
- mõõta FOV/readability, latency, FPS ja bandwidth;
- kinnitada kaamera nii, et otsik ja detail oleksid nähtavad.
