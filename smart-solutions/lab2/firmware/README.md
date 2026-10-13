# Lab 2 AtomS3 püsivara alus

See on eraldiseisev PlatformIO projekt Lab 2 postkontori kliendi jaoks. See
kasutab sama AtomS3 board'i, Arduino raamistikku, M5Unified'i ja ArduinoJsoni
sõltuvust nagu Lab 1, kuid Lab 1 suurt `main.cpp` faili ei ole siia kopeeritud.
Rõhuseadete ja ohutu lokaalse testpäringu software-only alus on lisatud;
pildiserveri, pumba ja täieliku Lab 1 kasutajaliidese ühendamine jääb TODO-ks.

## Ehitus ja hostitestid

Käivita selles kaustas:

```bash
pio run
pio test -e native
```

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

Nupp `TEST SERVER HEALTH` teeb ainult ühe `GET /health` päringu. See ei polli,
claim'i tööd, kutsu station'it ega liiguta robotit.

Samal lehel olev rõhuosa salvestab neli lineaarset teisenduskoefitsienti ning
`TEST PRESSURE SENSOR` loeb lokaalselt G5 ADC sisendit. Vaikimisi ja vigase
NVS konfiguratsiooni korral on olek `not_calibrated`: raw ADC võib olla
nähtav, kuid voltage ja kPa on `null`. Tegelikud koefitsiendid, ADC wiring ja
kõik füüsilised tulemused peavad tulema Andmehõive Lab 2 katsest.

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

Terminaltulemus salvestatakse enne aktiivse claim'i kustutamist ja seda
korratakse pärast võrgu taastumist sama ID-ga kuni server vastab edukalt.
Uut tööd vahepeal ei küsita. Kui seade taaskäivitub ebaselge aktiivse claim'iga,
ei saadeta tähte uuesti: töö muudetakse `ambiguous_after_reboot` põhjusega
`refused` tulemuseks, mis vajab serverisse saatmist.

## Veel kontrollimata

- [x] püsivara laadimine päris AtomS3R-i PlatformIO kaudu 12.10.2026;
- [x] Wi-Fi/setup-AP ja seadete püsimine taaskäivituse järel;
- [ ] päris hosti CA ja HTTPS-polling;
- [ ] päris USB-ga AtomS3 → station ning Lab 1 MG400 executor'i otsast lõpuni tulemus;
- [ ] võrgu katkestus ja NVS retry päris seadmel;
- [ ] pollingu latentsus ja valitud production-intervall;
- [x] rõhuanduri seadete, NVS valideerimise ja kohaliku ADC/pinge/kPa testi
  software-only alus;
- [ ] Andmehõive Lab 2 päris koefitsiendid, sensor/op-amp wiring ning raw
  ADC/pinge/kPa riistvarakontroll;
- [ ] Lab 1 pildi-, captive-portali ja pumba funktsioonide kontrollitud ühendus.
