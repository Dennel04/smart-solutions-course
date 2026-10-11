# Lab 2 AtomS3 püsivara alus

See on eraldiseisev PlatformIO projekt Lab 2 postkontori kliendi jaoks. See
kasutab sama AtomS3 board'i, Arduino raamistikku, M5Unified'i ja ArduinoJsoni
sõltuvust nagu Lab 1, kuid Lab 1 suurt `main.cpp` faili ei ole siia kopeeritud.
Pildiserveri, pumba/rõhu ja täieliku Lab 1 kasutajaliidese ühendamine selle
alusega on eraldi TODO.

## Ehitus ja hostitestid

Käivita selles kaustas:

```bash
pio run
pio test -e native
```

11.10.2026 kontrollis `pio run` AtomS3 keskkonna edukalt: RAM 50 168 / 327 680
baiti (15,3%) ja flash 1 122 541 / 3 342 336 baiti (33,6%). Native Unity
testides läbis 12/12 testi. Need on tarkvaratulemused; käsku `pio run -t upload`
ei ole käivitatud ja päris AtomS3 kontroll on endiselt TODO.

Arduino IDE ei ole selle repo põhitöövoog. `platformio.ini`, lähtekood ja
sõltuvused peavad jääma reprodutseeritavaks. Kui XIAO ESP32S3 Sense püsivara
lisatakse siia reposse, tehakse see eraldi PlatformIO projektina.

## Moodulid ja vastutus

- `src/main.cpp` — M5Unified, Wi-Fi/setup-AP, minimaalne seadete/testide
  veebileht ja core 0 võrgutask;
- `post_office_settings.*` — serveri URL-i, Atomi võtme, pollinguintervalli ja
  lokaalse HTTP arenduslipu valideerimine ning Preferences/NVS salvestus;
- `post_office_client.*` — väljuv poll, töö valideerimine ja tulemuse retry;
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

Production URL peab algama `https://`. Päris hosti usaldusahel lisatakse
ignoreeritud faili `include/post_office_ca_private.h`, kus defineeritakse
`POST_OFFICE_ROOT_CA`. Repos ei ole võltssertifikaati ning kood ei kasuta
`setInsecure()`. Ilma CA-ta keeldub klient HTTPS-päringust. `http://` on
lubatud ainult eraldi arenduslipuga kohalikuks testiks.

Nupp `TEST SERVER HEALTH` teeb ainult ühe `GET /health` päringu. See ei polli,
claim'i tööd, kutsu station'it ega liiguta robotit.

## Poll, station-piir ja püsiolek

Klient saadab bearer-autentimisega:

- `POST /api/atom/poll` — heartbeat ja maksimaalselt ühe töö küsimine;
- `POST /api/atom/result` — sama ID-ga `done` või `refused` tulemuse retry.

Lubatud on ainult `letter` ühe suurtähega `A`–`Z`. `pick_place`, tundmatu töö,
lisaväljad, koordinaadid/liikumiskäsud, vigane või aegunud töö lükatakse tagasi.
See püsivara ei saada MG400 käske.

Enne station'ile edastamist salvestatakse aktiivne töö ID NVS-i. Station'ile
saadetakse Lab 1-ga ühilduv JSON-rida väljadega `letter`,
`session:"post-office"`, `seq`, `atom_sent_ms` ning lisaks stabiilne `job_id`.
Käesolev alus ootab station'ilt terminalvastust:

```json
{"post_office_result":{"id":"job-id","status":"done","reason":""}}
```

See vastus on lokaalse station-adapteri leping, mitte väide, et Lab 1 station
on juba muudetud. Päris otsast lõpuni integratsioon on TODO.

Terminaltulemus salvestatakse enne aktiivse claim'i kustutamist ja seda
korratakse pärast võrgu taastumist sama ID-ga kuni server vastab edukalt.
Uut tööd vahepeal ei küsita. Kui seade taaskäivitub ebaselge aktiivse claim'iga,
ei saadeta tähte uuesti: töö muudetakse `ambiguous_after_reboot` põhjusega
`refused` tulemuseks, mis vajab serverisse saatmist.

## Veel kontrollimata

- [ ] püsivara laadimine päris AtomS3-le;
- [ ] Wi-Fi/setup-AP ja seadete püsimine taaskäivituse järel;
- [ ] päris hosti CA ja HTTPS-polling;
- [ ] Lab 1 station-adapter ning `letter` otsast lõpuni tulemus;
- [ ] võrgu katkestus ja NVS retry päris seadmel;
- [ ] pollingu latentsus ja valitud production-intervall;
- [ ] rõhuanduri ADC/pinge/kPa hook'id ja kalibratsioon;
- [ ] Lab 1 pildi-, captive-portali ja pumba funktsioonide kontrollitud ühendus.
