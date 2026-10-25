# Lab 2 AtomS3 püsivara alus

See on eraldiseisev PlatformIO projekt Lab 2 postkontori kliendi jaoks. See
kasutab sama AtomS3 board'i, Arduino raamistikku, M5Unified'i ja ArduinoJsoni
sõltuvust nagu Lab 1, kuid Lab 1 suurt `main.cpp` faili ei ole siia kopeeritud.
Rõhuseadete ja ohutu lokaalse testpäringu software-only alus on lisatud;
pildiserveri, pumba ja täieliku Lab 1 kasutajaliidese ühendamine jääb TODO-ks.

## Ehitus ja hostitestid

Esimeseks isoleeritud seadmekatseks vali `atoms3r`: see ehitab nüüd ainult
`BENCH_MODE=1` püsivara. Tavalise postkontorikliendi jaoks vali eraldi
`atoms3r_normal` (`BENCH_MODE=0`). Veebilehelt režiimi muuta ei saa.
Allpool toodud varasemad pollingutulemused kirjeldavad tavalist püsivara.

Käivita selles kaustas:

```bash
pio run
pio test -e native
```

### Eraldi Wi-Fi/HTTPS kontroll: atoms3r_health

23.10.2026 laadis Nikita Teterev selle püsivara päris AtomS3R-i ning
kontrollis LCD-d ja USB-helper'it. Redmi telefoni hotspot'iga sai ta
`WIFI CONNECTED`, `TLS VERIFIED`, seejärel `HEALTH ERROR`. Helper naasis
shell'i. HTTP 200 ja oodatud JSON ei ole kinnitatud; katse ei läbinud
HTTPS `/health` otsast lõpuni kontrolli. Vaikimisi `atoms3r` jääb BENCH-iks;
`atoms3r_normal` startup ja käitumine ei muutu. Health-build kasutab sama
`m5stack-atoms3` board'i ja partition table'it ning eraldi build-kausta.
Selle M5Unified 0.2.25, M5GFX 0.2.32 ja ArduinoJson 7.4.3 versioonid vastavad
kohaliku kontrollitud BENCH-build'i teekidele.

`HEALTH_ONLY=1` ja täpne source filter kaasavad ainult `health_only_main.cpp`
ning olemasoleva `bench_nvs_guard.cpp`. `BENCH_MODE=1` säilitab NVS-guard'id;
see eraldi environment lubab ainult allkirjeldatud STA/HTTPS katset, mitte
BENCH AP-d. Postkontoriklient, stores, station bridge ja jobs ei kompileeru.
Normal-build näeb uue entry point'i asemel tühja translation unit'it.

LCD/USB algolek on `HEALTH ONLY`, `execution disabled`, `WAITING FOR USB`.
Seade ei käivita Wi-Fi-d enne kohalikku luba. Python helper küsib SSID ja
parooli peidetud terminalisisendina ning kasutaja kinnitab `HEALTH ONCE`.
USB `HELLO` saab käivitusepõhise juhusliku avaliku challenge'i; ainult selle
challenge'iga korrektne ühekordne raam lubab katse. Helper ei korda ühendust
ega käsku. Restart nõuab uut luba; vana challenge ei sobi. Vigane sisend,
osaline rida üle 10 s või kinnituse puudumine 60 s jooksul lõpetab sessiooni.
Pärast edu või viga ei saa sama boot'i ajal uut katset käivitada.

Piiratud sisend: prinditav ASCII SSID 1–32 baiti, WPA2 parool 8–63 baiti,
ilma juhtmärkideta; avatud võrk, Unicode SSID/parool ja 64-märgiline PSK
pole selle testi osa. Helper ei pane paroole käsureale ega faili ja keeldub
terminali echo-fallback'ist. Rakendus kustutab sisendpuhvrid ja konfiguratsiooni
ajutised koopiad; Python ja Wi-Fi/TLS driver ei taga kõigi RAM-koopiate nullimist.

STA kasutab `nvs_enable=0`, `WIFI_STORAGE_RAM`, WPA2 miinimumnõuet ning ühte
15 s ühenduskatset. Setup AP-d, reconnect'i, NTP-d, web-serverit, ADC-d ega
salvestatud Wi-Fi/postkontori seadeid siin ei kasutata. NVS-i ega LittleFS-i
ei avata ja erase'i ei vajata. Võrk võib teha DHCP/DNS ning TLS handshake'i;
ainus rakenduse HTTP-päring on fikseeritud `GET /health` hostile
`narva2.roboarena.org`, port 443, ilma Authorization-päiseta. Redirect'e,
HTTP fallback'i, pollingut ega result retry'd ei ole.

TLS kasutab kohalikku ignoreeritud `post_office_ca_private.h` faili ja
`POST_OFFICE_ROOT_CA` väärtust. CA puudumine/viga lõpetab testi enne võrku.
Verifier kontrollib binaaris avaliku ISRG Root X2 sertifikaadi SHA-256
fingerprint'i; header'it ega binaari Git'i ei lisata. Ühe CA asemel bundle'i
lisamine vajab uut review'd, praegune parser lubab ühe trust anchor'i.

Arduino-ESP32 2.0.17 `WiFiClientSecure::connect(IPAddress, port, hostname,
CA, nullptr, nullptr)` kontrollib ahelat ja hostname'i ning säilitab SNI.
ESP-IDF 4.4.7 `CONFIG_MBEDTLS_HAVE_TIME_DATE` on välja lülitatud. Seetõttu
kasutame enne GET-i `getPeerCertificate()` ja `mbedtls_x509_crt_verify()`
uut kontrolli sama CA ja hostname'iga. SDK kutsub callback'i valitud
usaldusahela iga sertifikaadi jaoks trust anchor'ist leaf'ini. Callback
kontrollib iga `valid_from`/`valid_to` välja UTC vastu ega kustuta SDK lippe.
Puuduv peer/anchor, poolik tee, vigane kuupäev või verification flag keelab GET-i.
See kontroll ei sõltu väljalülitatud SDK date-helper'ist.

UTC tuleb Maci kellast USB kaudu; kontrolli enne testi Maci kuupäeva ja
kella sünkroonimist. Rakendus lisab katse ajal kulunud sekundid. Protokoll
lubab aastaid 2024–2036 ning GET eeldab alla 60 s vanust autoriseerimist.
Need piirid ei tõenda Maci kella õigsust. Vale usaldatud lokaalne kell võib
muuta expiry-kontrolli ekslikuks; see pole autentitud võrguaja teenus.
CRL/OCSP revocation-kontrolli selles katses ei lisata.

Socket connect/read/write timeout on 5 s, TLS handshake kuni 8 s ja vastuse
kogumisel 8 s tähtaeg; DNS kasutab SDK lõplikku retry-piiri. Edu eeldab
HTTP 200 ja JSON-i `{"ok":true,"service":"lab2-post-office"}`. Parser piirab
vastuse 2048 ja body 256 baidiga, nõuab Content-Length'i ning JSON Content-Type'i;
chunked või muu toetamata framing annab FAIL, mitte korduspäringu.
Pärast üht GET-i või viga suletakse TLS ja peatatakse/deinit'itakse Wi-Fi.
Stop/deinit'i viga annab `RADIO STOP ERROR`, mitte `HEALTH OK`; automaatset kordust pole.
LCD/USB näitavad ainult olekukoode; helper ei kuva suvalist serial-sisu.

#### HEALTH ERROR: 23.10.2026 piiratud tulemus ja järgmine diagnostika

`TLS VERIFIED` tähendab, et enne HTTP etappi läbis klient hostname'i,
CA-ahela ja USB kaudu saadud UTC põhise sertifikaadiaegade kontrolli.
`HEALTH ERROR` koondab praegu `getHealth()` vead: lühike request-write,
lugemisviga, sulgemata socket või 8 s tähtaeg, liiga suur vastus ning
HTTP/framing/JSON kontrolli ebaõnnestumine. Teade ei kinnita, et server
sai terve GET-päringu või vastas HTTP 200-ga. Serveri riket ei ole tõendatud.

Parser nõuab `Content-Length` päist ja lükkab `Transfer-Encoding: chunked`
tagasi. See on võimalik ühilduvuspiirang, mitte tuvastatud vea põhjus:
päris vastuse staatus ega framing ei ole salvestatud. Ette valmistatud
diagnostikaplaan on eristada piiratud veakoodidega write/read/timeout,
HTTP staatust, framing'ut ja JSON valideerimist, ilma body, SSID või parooli
logimiseta. Praegune püsivara neid eraldi koode veel ei väljasta.
Järgmine muudatus ja uus riistvarakatse vajavad eraldi luba; automaatset
korduspäringut ega üleminekut normal-režiimi ei tehta.

Kohalikud kontrollid firmware-kaustas (ei ava serialit ega production-võrku):

```bash
pio test -e native
pio run -e atoms3r_health
python3 tools/verify_health_only.py --nm "$HOME/.platformio/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-nm"
pio run -e atoms3r
```

Verifieri PASS tähendab ainult lähtekoodi/build'i isolatsiooni kontrolli,
mitte upload-luba ega riistvaralist HTTPS tulemust. Native-testid kasutavad
fake-transporti ja sünteetilist sertifikaadiahelat; hosti Python-testid
kompileerivad päris protokolliparseri. Need ei testi päris TLS serverit.

23.10.2026 avaldamiseelne korduskontroll: Python `541 passed`, native
`57/57` (HEALTH_ONLY `14/14`), `atoms3r_health` build `SUCCESS`, RAM
`49 112 / 327 680` baiti ja flash `982 297 / 3 342 336` baiti. ELF isolation
ja ISRG Root X2 fingerprint'i kontroll läbisid. Need on lokaalsed tulemused;
ülalkirjeldatud päris `/health` katse lõppes endiselt veaga.

Riistvarasamm vajab eraldi luba ja USB-only ühenduse kinnitust. Säilita Lab 1
backup väljaspool Git'i ning kontrollitud BENCH build/hash tagasitee jaoks;
health-upload asendab seadmes töötava BENCH püsivara. SDK flash-coredump ja
võimalikud OTA metadata kirjutused jäävad alles. Panic võib salvestada RAM-is
olevad Wi-Fi credentials. Varasem ühe BENCH-upload'i riskinõusolek ei anna
automaatselt luba uueks upload'iks; kogu flash'i muutumatust ei garanteerita.

Pärast eraldi lubatud health-upload'i ja uut portide kontrolli saab kasutaja
käivitada repo Lab 2 venv'iga (käsk ise lubab ühe production-päringu alles
interaktiivse kinnituse järel):

```bash
../.venv/bin/python tools/health_only_session.py --port <ACTUAL_PORT>
```

Helper ei pulseeri DTR/RTS-i; OS/USB driver'i käitumist tuleb kontrollida
riistvaral. Ära ava samal ajal serial monitori või station-adapterit.
PASS: `WIFI CONNECTED`, `TLS VERIFIED`, `HEALTH OK`, võrk peatub. FAIL:
veakood, puuduv tulemus või restart; ära korda automaatselt ega lülitu normal'isse.
Health ei vaja Atomi API-võtit, ei claim'i tööd ega uuenda `last_seen` väärtust.
Bearer-auth, production polling ja robotiahel jäävad eraldi katseteks.

### Isoleeritud esimene käivitus: BENCH_MODE

**23.10.2026: esimene piiratud BENCH-katse tehtud.** Kasutaja aktsepteeris
selle ühe upload'i jaoks allpool kirjeldatud flash-coredump'i ja OTA metadata
jääkriski. Flash-coredump jääb SDK-s lubatuks; uut upload'i või normaalrežiimi
see luba ei kata.

Hoia Atom ainult USB kaudu Maci küljes. Enne upload'i säilita kontrollitud
täis-flash backup väljaspool Git'i; koopia võib sisaldada paroole. Peata
station-adapter ja muud serial-porti kasutavad programmid. Upload vajab
eraldi luba. Kinnitatud bench-vaatlused on allpool eraldi kuupäevaga.

`atoms3r` ehitab failid `bench_main.cpp`, `bench_nvs_guard.cpp` ja puhta
`pressure_model.cpp` mudeli. Postkontori kliendi, station bridge'i,
Preferences-store'id ja privaatse CA header'i jätab see build välja.
BENCH_MODE puudumisel valib `build_mode.h` väärtuse `1`; muu väärtus kui
`0` või `1` peatab kompileerimise. Mõlemal environment'il on oma build-kaust.

Bench-startup kasutab kaitstud `Lab2AtomBench` AP-d, ühe kliendi piirangut ja
WPA2-PSK-d. Igal käivitusel genereerib Atom 16 hex-märgiga ajutise parooli.
Enne Wi-Fi init'i lülitab kood sisse Espressifi SAR-entroopiaallika
(`bootloader_random_enable`), täidab puhvri `esp_fill_random` abil ja lülitab
allika välja (`bootloader_random_disable`). Alles siis alustab ta Wi-Fi ja
hiljem ADC kasutamist. Null-, konstantse, perioodilise või loendurmustriga
puhvri korral katkestab kood AP käivitamise; sama kehtib vigase puhvri või
hostitestiga süstitud fill-vea puhul. Korduskatset ega varuparooli pole.
Need kontrollid tuvastavad ilmseid tõrkeid, mitte entroopia kvaliteeti.
Lokaalsed ajutised puhvrid puhastatakse volatile-kirjutustega.
Loe kaks 8-märgilist LCD-rida üheks parooliks. Ära pildista ega logi parooli.
Atom seadistab AP enne raadio käivitamist; vea korral peatab raadio ega
proovi avatud AP-d või STA-d. Kasuta lehte ainult usaldatud Macist, lühikese
laborisessiooni jooksul. Ära luba Macis Internet Sharing'ut. AP ei ruudi
liiklust internetti. HTTP-leht ise ei lisa kasutajapõhist autentimist.

Wi-Fi init kasutab `nvs_enable=0` ja `WIFI_STORAGE_RAM`. Bench-linkeri
NVS-guard jätab `nvs_flash_init`/`nvs_flash_init_partition` initsialiseerimata
ning tagastab eduka init-tulemuse, et Arduino ei prooviks vigast NVS-i
vormindada. `nvs_open` ja `nvs_open_from_partition` tagastavad vea mõlema
avamisrežiimi korral. Nii ei loe bench ka M5GFX-i board-cache'i ega salvesta
autodetect'i tulemust. Need piirangud kehtivad ainult bench environment'is.
ESP-IDF võib logida blokeeritud NVS-i või PHY kalibratsiooni veateateid;
AP käivitumise ja ekraani kontroll tuleb teha päris seadmel. Guard ei tõenda
bootloader'i ega tulevase teegiversiooni kogu flash-käitumist.

#### Flash-kirjutuste piir

Praegune tööriistaahel on PlatformIO Espressif32 6.13.0, Arduino-ESP32
2.0.17 ja ESP-IDF 4.4.7 (`IDF_VER=v4.4.7-dirty`). Arduino core kompileeritakse projektiga, kuid IDF-i
panic- ja coredump-kood tuleb SDK eelkompileeritud `.a` arhiividest.
SDK `sdkconfig` sisaldab `CONFIG_ESP_COREDUMP_ENABLE_TO_FLASH=y` ning bench
ELF sisaldab `esp_core_dump_to_flash` ja flash-dump'i kirjutusfunktsioone.
Projektipõhine `#define`, build flag või kohaliku `sdkconfig` faili muutmine
neid arhiive ümber ei kompileeri.

Espressifi toetatud valik on ESP-IDF menuconfig'is Core dump / Data
destination / None ning vastavate SDK komponentide uus build. Praegune
Arduino-only projekt seda build'i ei tee. SDK vahetus või Arduino-as-IDF-
component töövoog vajab eraldi otsust. Selle sammu käigus ei muuda me SDK-d,
normal environment'i ega lisa flash-kirjutuste linker-peretõkkeid.

Piiratud säilimisväide: bench ei ava NVS-i ega mount'i LittleFS-i; rakenduse
settings/job/calibration teed puuduvad. **See ei taga kogu flash'i
muutumatust.** Panic võib kirjutada RAM-i/stack'i coredump-partitsiooni,
sealhulgas AP parooli. Kohalik puhvri puhastamine ei eemalda Wi-Fi driver'i
vajalikku RAM-koopiat ega kaitse varem tekkinud panic'u eest. Arduino/bootloader
võivad uuendada OTA metadata't. Backup jääb puutumata eraldi Maci failina.
Ära sisesta bench'i production-saladusi. Kasutaja aktsepteeris jääkriski
23.10.26 ühe isoleeritud bench-upload'i jaoks. See ei kinnita füüsilist
NVS-i säilimist ega muuda kogu flash'i read-only'ks. Tulevased upload'id
vajavad eraldi luba.

Viited: [Espressifi RNG-juhend](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32s3/api-reference/system/random.html)
ja [coredump-seadistus](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32s3/api-guides/core_dump.html).

LCD peab näitama `BENCH`, `execution disabled`, AP nime, tegelikku IP-d ja
ajutist parooli. Serial 115200 peab sisaldama markerit
`LAB2_BENCH_MODE=1;execution=disabled;nvs=blocked`, kuid mitte AP parooli.
Bench ei loe serialist tulemusi ega salvesta aktiivset claim'i, pending
result'i või sequence'it. Ta ei käivita STA recovery't, NTP-d, pollingut,
claim'i, result retry'd, station dispatch'i ega actuator-käske.

`GET /`, `/settings`, `/state` ja `/pressure/settings` annavad ainult
bench-oleku. Leht ei laadi salvestatud SSID-d, URL-i ega võtmeid.
Salvestamine, `/test/post-office` ja muud muutvad päringud saavad HTTP 423
`bench_read_only`, ka otse API poole pöördudes. Ainult `POST /test/pressure`
loeb G5 ADC-d; selle päringu parameetrid ei muuda kalibratsiooni.
Kalibratsioon on ainult RAM-is `calibrated=false`; voltage ja kPa jäävad
`null`. Ilma sensorita on ADC ujuv. Rail-kood annab `invalid_raw_adc`, muu
lugem annab `not_calibrated`; kumbki ei kinnita rõhumõõtmist.

Enne iga lubatud upload'i kontrolli build'i:

```bash
pio test -e native
pio run -e atoms3r
python3 tools/verify_bench.py --nm "$HOME/.platformio/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-nm"
```

Kontrollskript loeb ainult lokaalseid `firmware.bin`/`firmware.elf` faile.
Ta nõuab bench-markerit, nelja NVS-guard'i ja kontrollib live-kliendi,
store'ide, STA-kliendi ning NTP sümbolite puudumist. Salvesta väljastatud
SHA-256 enne upload'i; marker üksi ei asenda lähtekoodi ja symbol-table'i
kontrolli. Ta kontrollib ka SDK konfiguratsiooni ja flash-coredump sümboleid.
Praeguse SDK puhul annab ta `ISOLATION PASS`, seejärel `NOT READY` ja exit 2.
Isolatsiooni kontrolli läbimine ei ole upload-luba. Hostitestid kasutavad
sünteetilisi seadeid, RNG tõrkeid ja job-olekuid. 23.10.26 upload tugines
kasutaja eraldi riskinõusolekule; kontrollskripti `NOT READY` jäi nähtavaks.

Alles pärast coredump-otsust, uut review'd ja eraldi upload-luba tuvasta port
uuesti ning kasuta ainult `atoms3r`:

```bash
pio device list
pio run -e atoms3r -t upload --upload-port <ACTUAL_PORT>
```

Ära kasuta erase'i ega `uploadfs` käsku. Kontrolli LCD-d, serialit, AP parooli,
read-only lehte ning HTTP 423 vastuseid. Ära käivita station-adapterit ega
sisesta production-võtit. NVS-i säilimist ja AP tööd peab tudeng kontrollima
eraldi riistvarakatses; native-testid seda ei tõenda.

Tavalise režiimi juurde naasmiseks on vaja eraldi luba ja build'i
`pio run -e atoms3r_normal`. Selle environment'i upload võib kohe kasutada
varem salvestatud Wi-Fi/postkontori seadeid, saata pending result'i või
claim'ida töö. Bench ei kustuta neid. Planeeri enne normaalrežiimi upload'i
võrgu ja station'i isolatsioon; veebilehel puudub režiimi enable-nupp.

11.10.2026 kontrollis `pio run` AtomS3 keskkonna edukalt: RAM 50 168 / 327 680
baiti (15,3%) ja flash 1 122 541 / 3 342 336 baiti (33,6%). Native Unity
testides läbis 12/12 testi. 12.10.2026 laaditi püsivara päris AtomS3R-i ning
pärast puuduva `activeId` NVS-lugemise parandust läbis uus build ja upload;
native suite läbis 13/13 testi. 13.10.2026 läbis AP+STA recovery muudatus
21/21 native-testi ning päris AtomS3R-il kontrolliti setup/settings,
autentitud lokaalset pollingut, reboot-persistence'it ja Wi-Fi reconnect'i.
See ei tõenda production HTTPS-i ega station/MG400 integratsiooni.

Arduino IDE ei ole selle repo põhitöövoog. `platformio.ini`, lähtekood ja
sõltuvused peavad jääma reprodutseeritavaks. Kui XIAO ESP32S3 Sense püsivara
lisatakse siia reposse, tehakse see eraldi PlatformIO projektina.

## Projekti püsivara taastamine pärast UIFlow2

Vanas AtomS3R-is oli 13.10.26 ekraanikontrolli järel
`UIFlow2.0 AtomS3R v2.5.3`. Projekti polling, station bridge ja pressure page
pole selle püsivaraga saadaval. Asendusseadmes kontrolliti 23.10.26
BENCH_MODE=1 ja seejärel eraldi HEALTH_ONLY püsivara; allolev UIFlow2
taastamisjuhend käsitleb vana seadme olukorda. Vaata
[ekraani diagnostikat](../docs/atom_display_diagnostic.md).

Alusta taastamist isoleeritud bench-püsivaraga repo juurkaustast.
Allolev upload vajab eraldi luba; see ei taasta veel projektipollingut:

```bash
cd smart-solutions/lab2/firmware
pio device list
pio run -e atoms3r
pio run -e atoms3r -t upload --upload-port <ACTUAL_PORT>
```

`<ACTUAL_PORT>` tuvastatakse vahetult enne laadimist; varasem
`/dev/cu.usbmodem101` ei ole püsiv aadress. Eraldi flash/NVS erase'i ega
filesystem upload'i ei ole taastamiseks ette nähtud.

Pärast bench-upload'i kontrolli serial startup'i ja kaitstud AP-d eespool
kirjeldatud viisil. Alles eraldi lubatud normaalrežiimis kontrolli serveri URL-i, Wi-Fi seadeid ja Atomi
võtit: nende säilimist pärast UIFlow2 ei saa eeldada. Paroole ega API-võtmeid
ei kirjutata Git'i või diagnostikalogi. Käivita kohalik postkontori test,
kontrolli autentitud pollingut ja `last_seen` uuenemist ning vajadusel korda
Wi-Fi reconnect-katset.

Bench'i read-only pressure-leht ja G5 lugemine ilma andurita on 23.10.26
kontrollitud. Normaalrežiimi pressure-extension, päris sensor/op-amp ahel,
Andmehõive Lab 2 koefitsiendid, kalibratsiooni NVS/reboot-püsivus ja kalibreeritud
pressure test button jäävad TODO-ks.

## Kinnitatud BENCH-katse — 23.10.2026

Katse toimus asendus-AtomS3R-il (ESP32-S3-PICO-1, 8 MB flash), ainult USB
kaudu MacBookiga ühendatult. Välised andurid, LM358, station, MG400 ja pump
olid lahti ühendatud. Lab 1 täis-flash backup jäi Macis väljapoole Git'i:
`8 388 608` baiti, SHA-256 kontrollitud. Lab 1 ekraan töötas pärast backup'i;
backup'i sisu ega paroole ei avaldatud.

BENCH puhas build oli `SUCCESS`, native `43/43`, Python `480 passed`.
Üks `atoms3r` BENCH_MODE=1 upload lõppes `SUCCESS` ja esptool kontrollis
kirjutatud andmete hash'i. `erase_flash` ega `uploadfs` käsku ei kasutatud.
LCD näitas `BENCH`, `execution disabled`, `Lab2AtomBench`, `192.168.4.1`
ja ajutist parooli. MacBook ühines kaitstud AP-ga; Safari avas
`http://192.168.4.1` eestikeelse read-only lehe. Save- ja postkontori
testinupud olid keelatud. Esialgu kinnitasid HTTP 423 jõustamist ainult
software-testid. Nikita Teterev saatis hiljem 23.10.26 MacBookist curl'iga
üle `Lab2AtomBench` Wi-Fi kaks päringut ilma paroolide ja API-võtmeteta ning
kontrollis seejärel kolmandana `/pressure/settings` POST-i:

| Päring päris Atomile | Tulemus |
| :--- | :--- |
| `POST http://192.168.4.1/settings` | `HTTP/1.1 423`, `{"error":"bench_read_only"}` |
| `POST http://192.168.4.1/test/post-office` | `HTTP/1.1 423`, `{"error":"bench_read_only"}` |
| `POST http://192.168.4.1/pressure/settings` | `HTTP/1.1 423`, `Content-Type: application/json`, `{"error":"bench_read_only"}` |

Atom jäi BENCH_MODE'i ja välisest riistvarast lahti ühendatuks; production
HTTPS-i/pollingut ei kasutatud. Kõik kolm safety-route'i on nüüd päris
seadmel kontrollitud. Need tulemused ei kinnita NVS-i täielikku säilimist.

Kohalik G5 test ilma andurita tagastas `status=not_calibrated`, `raw_adc=7`,
`calibrated=false`, `sensor_connected=not_verified`, `voltage_v=null` ja
`pressure_kpa=null`. See on ujuva ADC sisendi vaatlus, mitte rõhumõõtmine.

PlatformIO USB Serial Monitor ühendas kiirusel 115200. Reset'i järel näitas
macOS serial-porti korraks lahtiühendatuna ja siis taas ühendatuna; LCD naasis
BENCH-kuvale. Rakenduse diagnostilisi serial-teateid ei salvestatud ega
kinnitatud. See vaatlus ei tõenda panic'u või NVS-vea puudumist.

Selles katses ei kontrollitud production HTTPS-i/pollingut, station-adapterit,
MG400-t, pumpa, kaameraid, päris rõhuanduri/op-amp ahelat ega füüsilist NVS-i
säilimist. Järgmiseks jäävad serial-diagnostika ja NVS-i säilimise katseplaan;
normaalrežiim vajab eraldi luba.
Täielik sessioonikanne on [Lab 2 arenduspäevikus](../README.md#arenduspäevik).

## Moodulid ja vastutus

- `src/main.cpp` — M5Unified, Wi-Fi/setup-AP, minimaalne seadete/testide
  veebileht ja core 0 võrgutask;
- `post_office_settings.*` — serveri URL-i, Atomi võtme, pollinguintervalli ja
  lokaalse HTTP arenduslipu valideerimine ning Preferences/NVS salvestus;
- `post_office_client.*` — väljuv poll, töö valideerimine ja tulemuse retry;
- `pressure_model.*` — Arduino-vaba ADC → V → kPa mudel, range-check ja
  fail-closed kalibratsiooni valideerimine;
- `pressure_settings.*` — valideeritud koefitsientide eraldi Preferences/NVS
  salvestus;
- `persistent_state.*` — aktiivse töö ja saatmata terminaltulemuse püsiolek;
- `station_bridge.*` — Lab 1-ga ühilduv kohalik serial-JSON piir;
- `core/post_office_model.cpp` — Arduino-vaba valideerimis- ja claim-loogika,
  mida kontrollivad `test/` hostitestid.

Põhitsükkel kasutab `millis()` ajastust. Võrgutöö jookseb core 0 task'is ning
nupu/serial-piir core 1 Arduino tsüklis; põhitsüklis ei ole pikka blokeerivat
pollinguviivitust.

## Seaded ja transport

Minimaalne seadeteleht sisaldab Wi-Fi SSID/parooli, postkontori baasaadressi,
Atomi bearer-võtit, pollinguintervalli 250–60 000 ms ja eraldi `Allow local
HTTP development` lippu. Võtit ega Wi-Fi parooli ei tagastata seadete
GET-vastuses ega logita; tühi võtmeväli jätab olemasoleva võtme muutmata.
Kui SSID puudub, käivitub kohe lokaalne `Lab2AtomSetup` seadistus-AP. Kui
salvestatud SSID-ga STA-ühendus ei teki 15 sekundi jooksul, läheb püsivara
samasse setup-AP režiimi ilma Wi-Fi või postkontori NVS-seadeid kustutamata.
Fallback kasutab AP+STA režiimi: setup-leht jääb avatuks ning salvestatud
STA-seadistust proovitakse iga 20 sekundi järel uuesti, iga katse timeout on
endiselt 15 sekundit. Eduka STA-ühenduse järel peatatakse retry ja setup-AP,
seejärel jätkub tavaline polling ilma restartita.

Production URL peab algama `https://`. Päris hosti usaldusahel lisatakse
ignoreeritud faili `include/post_office_ca_private.h`, kus defineeritakse
`POST_OFFICE_ROOT_CA`. Repos ei ole võltssertifikaati ning kood ei kasuta
`setInsecure()`. Ilma CA-ta keeldub klient HTTPS-päringust. `http://` on
lubatud ainult eraldi arenduslipuga kohalikuks testiks.

Normaalrežiimis ootab HTTPS-kliendi ajakontroll selle käivituse SNTP
sünkroonimise teadet ja UTC-d vahemikus 2024–2036. Ilma selleta keeldub
transport veaga `https_time_unavailable`; pollingu üldolek võib olla
`poll_failed`. ESP-IDF 4.4.7 eelkompileeritud mbedTLS-is puudub
`MBEDTLS_HAVE_TIME_DATE`, seega kontrollib klient lisaks CA-le ja hostname'ile
valitud sertifikaadiahela `notBefore`/`notAfter` aega, kaasa arvatud usaldatud
juursertifikaat. HTTPClient saab ühenduse õnnestumise alles pärast seda
kontrolli; enne seda ei saada klient bearer-päist, polli ega tulemust.
Ümbersuunamised on keelatud. SNTP on olemasoleva võrgukella usaldusallikas,
kuid see ei paku autenditud aega; CRL/OCSP kontrolli siin ei lisata.

Nupp `TEST SERVER HEALTH` teeb ainult ühe `GET /health` päringu. See ei polli,
claim'i tööd, kutsu station'it ega liiguta robotit.

Samal lehel olev rõhuosa salvestab neli lineaarset teisenduskoefitsienti ning
`TEST PRESSURE SENSOR` loeb lokaalselt G5 ADC sisendit. Vaikimisi ja vigase
NVS konfiguratsiooni korral on olek `not_calibrated`: raw ADC võib olla
nähtav, kuid voltage ja kPa on `null`. Tegelikud koefitsiendid, ADC wiring ja
kõik füüsilised tulemused peavad tulema Andmehõive Lab 2 katsest.

Normaalrežiimis peab kasutaja samal rõhuseadete lehel kinnitama kontrollitud
anduriühenduse märkeruuduga `sensor_confirmed`. Kinnitus kehtib ainult RAM-is
kuni taaskäivituseni. Ilma kinnituseta tagastab test `sensor_not_confirmed`,
raw ADC ning `null` pinge/kPa ka varem salvestatud kehtivate koefitsientidega.
Üks ADC väärtus ei tõenda anduri olemasolu. Kinnitamine ei asenda wiring'u,
sisendpinge ega Andmehõive kalibratsiooni füüsilist kontrolli.

## Production TLS ettevalmistus — 20.10.2026

Nikita kontrollis Macis `https://narva2.roboarena.org` TLS-ahelat: Let's
Encrypt YE2, Root YE ja ISRG Root X2. OpenSSL andis
`Verify return code: 0 (ok)`. Ta laadis ISRG Root X2 juursertifikaadi
Let's Encrypti ametlikult veebilehelt ja kontrollis SHA-256 fingerprint'i:

`69729b8e15a86efc177a57afb7171dfc64add28c2fca8cf1507e34453ccb1470`

CA on lokaalses `include/post_office_ca_private.h` failis.
`git check-ignore` kinnitas faili ignoreerimist. Header'it, PEM-i ega
`firmware.bin` faili Git'i ei lisata; repos säilib CA ettevalmistuse kirjeldus.

`pio run -e atoms3r` läbis tulemusega `SUCCESS`: RAM 15,4%, flash 34,5%,
aeg 20,98 s. Eraldi kontroll kinnitas ISRG Root X2 PEM-sertifikaadi olemasolu
`firmware.bin` failis. `bash smart-solutions/lab2/check.sh` lõpetas teatega
`All software-only regression checks passed.`

Need on Maci TLS- ja lokaalse build'i kontrollid. Päris AtomS3R-i ühendust
production HTTPS serveriga ega pollingut selle katsega ei kontrollitud.
Järgmine samm on [projektipüsivara taastamine](#projekti-püsivara-taastamine-pärast-uiflow2)
ja eraldi seadmekatse: production URL, seadme seaded, autentitud polling
ning `last_seen` uuenemine. Pressure-extension ja ülejäänud riistvarakatsed
jäävad lahti.

## Poll, station-piir ja püsiolek

Klient saadab bearer-autentimisega:

- `POST /api/atom/poll` — heartbeat ja maksimaalselt ühe töö küsimine;
- `POST /api/atom/result` — sama ID-ga `done` või `refused` tulemuse retry.

Lubatud on `letter` ühe suurtähega `A`–`Z` ja `pick_place` täpselt routine'iga
`source_to_finished`. Tundmatu routine või töö, lisaväljad,
koordinaadid/liikumiskäsud, kiirus, pump/DO, trajektoor, vigane või aegunud töö
lükatakse tagasi. See püsivara ei saada MG400 käske.

Enne station'ile edastamist salvestatakse aktiivne töö ID NVS-i. Station'ile
saadetakse `letter` puhul Lab 1-ga ühilduv JSON-rida väljadega `letter`,
`session:"post-office"`, `seq`, `atom_sent_ms` ning stabiilne `job_id`.
`pick_place` real on selle asemel `job:"pick_place"` ja
`routine:"source_to_finished"`; koordinaate ega actuator-käske ei saadeta.
Käesolev alus ootab station'ilt terminalvastust:

```json
{"post_office_result":{"id":"job-id","status":"done"}}
```

Lab 2 software-adapter rakendab selle lepingu kaustas `../src/` ning kasutab
mock executor'it. See ei muuda Lab 1 station'it ega tõenda päris USB või MG400
integratsiooni; riistvara otsast lõpuni kontroll on TODO.

Terminaltulemuse salvestamisel kontrollib klient iga NVS-kirjutuse tulemust
ja loeb väärtuse tagasi. `resultReady=true` avaldatakse pärast kohustuslikke
välju; `activeId` jääb alles kuni serveri HTTP 200 kinnituseni. Alles siis
kirjutab klient lisamarkeri `ackedId` ja koristab tulemuse. Katkenud koristuse
lõpetab ta järgmisel käivitusel selle markeri järgi. Võrgu taastumisel saadab
klient sama ID-ga salvestatud tulemust uuesti. Uut tööd vahepeal ei küsita.
NVS-viga blokeerib selle käivituse pollingu ja tulemuste saatmise olekuga
`nvs_state_error`. Vigane või ilma claim'ita poolik kirje vajab kohalikku
ülevaatust; automaatset kustutamist ei tehta. Vanad terviklikud terminalkirjed
sobivad ka ilma `activeId`-ta. Pooleli `ackedId` koristusega seadmele ei tohi
taastada vana firmware'it enne oleku ülevaatust.

Serial-tulemuse ja võrgukliendi NVS-üleminekud kasutavad sama lukku.
Hilinenud terminalvastus ei saa pärast kinnitatud koristust claim'i uuesti
luua. Ka serverist saadud vigase töö keeldumine vajab enne kohalikku claim'i.
Kui allesolev `resultId` erineb `ackedId`-st, jätab klient kirjed alles ja
keeldub koristamisest.

Kui seade taaskäivitub ebaselge aktiivse claim'iga,
ei saadeta tähte uuesti: töö muudetakse `ambiguous_after_reboot` põhjusega
`refused` tulemuseks, mis vajab serverisse saatmist.

Need normal-režiimi parandused on tarkvaralised. Native-testid kontrollivad
TLS-aja ja andurikinnituse loogikat; pytest kompileerib tegeliku
`persistent_state.cpp` sünteetilise Preferences-asendusega ning katkestab
kirjutusi ja kustutusi. Need testid ei tõenda päris NVS-i käitumist
toitekatkestusel ega uut production HTTPS ühendust. BENCH jääb vaikimisi
environment'iks; HEALTH_ONLY ja varasemad riistvaratulemused jäävad alles.

## Veel kontrollimata

- [x] asendus-AtomS3R BENCH upload, LCD, kaitstud AP ja Safari read-only leht
  23.10.2026; G5 ainult ilma andurita;
- [x] Nikita Teterev kontrollis `/settings`, `/test/post-office` ja
  `/pressure/settings` POST-i HTTP 423 vastuseid päris BENCH Wi-Fi kaudu
  23.10.2026;
- [ ] BENCH rakenduse diagnostilised serial-teated ja füüsiline NVS-i säilimine;
- [x] püsivara laadimine päris AtomS3R-i PlatformIO kaudu 12.10.2026;
- [x] Wi-Fi/setup-AP ja seadete püsimine taaskäivituse järel;
- [x] production hosti TLS-ahel Macis kontrollitud; ISRG Root X2 CA-ga
  lokaalne build ja sertifikaadi olemasolu binaaris kontrollitud 20.10.2026;
- [ ] päris AtomS3R production HTTPS ühendus ja autentitud polling;
- [x] HEALTH_ONLY upload, LCD/USB, telefoni hotspot ja `WIFI CONNECTED` /
  `TLS VERIFIED` 23.10.2026; katse lõppes `HEALTH ERROR`;
- [ ] HEALTH_ONLY `/health` HTTP 200 ja oodatud JSON; üldise veateate
  täpne põhjus vajab eraldi diagnostikat;
- [ ] päris USB-ga AtomS3 → station ning Lab 1 MG400 executor'i otsast lõpuni tulemus;
- [ ] võrgu katkestus ja NVS retry päris seadmel;
- [ ] pollingu latentsus ja valitud production-intervall;
- [x] rõhuanduri seadete, NVS valideerimise ja kohaliku ADC/pinge/kPa testi
  software-only alus;
- [ ] Andmehõive Lab 2 päris koefitsiendid, sensor/op-amp wiring ning raw
  ADC/pinge/kPa riistvarakontroll;
- [ ] Lab 1 pildi-, captive-portali ja pumba funktsioonide kontrollitud ühendus.
