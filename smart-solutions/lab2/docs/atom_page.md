# AtomS3 lehe Lab 2 laiendus

Lab 2 PlatformIO projektis on nüüd minimaalne `Settings & tests` veebileht,
postkontori klient ja lokaalse kanali tarkvaraline piir. Labori 1 pildi saatmise,
pumba/rõhu ning täieliku captive-portali lehe ühendamine on veel TODO; Lab 1
püsivara ei ole tervikuna kopeeritud.

AtomS3 püsivara kohustuslik projektitöövoog on PlatformIO: reprodutseeritav
`platformio.ini`, lähtekoodipuu ja sõltuvused ning build/upload PlatformIO
kaudu. Arduino IDE ei ole selle repo peamine firmware-töövoog. XIAO ESP32S3
Sense püsivara asub eraldi PlatformIO projektis `../firmware-xiao-camera/`.
AtomS3 ja XIAO buildid on tarkvaraliselt kontrollitud; seadmetele laadimine on
veel TODO.

> Siin eristatakse teostatud tarkvaraalust ja kontrollimata riistvaratööd.
> Ükski allolev punkt ei tõenda päris AtomS3, station'i ega MG400 integratsiooni.

## Uued postkontori seaded

| Väli | Eesmärk | Salvestamine ja turve |
| :--- | :--- | :--- |
| `Post-office server address` | production HTTPS baasaadress | seadmes; valideerida skeem ja pikkus |
| `Atom authentication key` | Atomi API autentimine | seadmes; UI ei loe olemasolevat võtit tagasi ega logi seda |
| `Polling interval` | tööde küsimise intervall millisekundites | seadmes; tarkvarapiir 250–60 000 ms, lõplik väärtus vajab võrgukatset |
| `Allow local HTTP development` | lubab teadlikult ainult lokaalse `http://` arenduse | production'is väljas; HTTPS vajab päris hosti CA-d |

Serveri aadress ei ole sama mis Labori 1 lokaalse jaama aadress. Atom pollib
dropletit väljamineva HTTPS-ühendusega ja edastab saadud kõrgtaseme töö
Labori 1 lokaalsesse kanalisse.

Salvestusvastus ei tohi sisaldada autentimisvõtit. Tühi võtmeväli tähendab
„jäta olemasolev võti muutmata“, kui serveri aadressi/seadme identiteeti ei
muudeta. Võtme teadlikuks eemaldamiseks peab olema eraldi kinnitatav tegevus.

## Postkontori test

Lehel on nupp `TEST SERVER HEALTH`, mis teeb ühe `GET /health` testpäringu ilma
polli või claim'ita. Firmware lisab seadistatud bearer-päise, kuid praeguse
serveri `/health` endpoint on avalik ega valideeri Atomi võtit. Seega kontrollib
nupp aadressi, TLS-i ja HTTP tervisevastust; Atomi autentimist kontrollivad
poll/result päringud. Minimaalne alus näitab HTTP tulemust ja turvalist
lühivastust. Round-trip aja ning viimase õnnestunud polli kuvamine on veel TODO.

- päringu olekut ja HTTP tulemust;
- serveri vastuse lühikest turvalist sisu või veakoodi;
- saladusi ega täielikku autoriseerimispäist ei näidata.

Testnupp ei loo ega claim'i `letter`/`pick_place` tööd ja ei käivita MG400 rada.

## Rõhuanduri seaded

Andmehõive Lab 2 annab rõhuanduri koos astmega ja kalibratsioonikonstandid.
Neid väärtusi ei hinnata ega leiutata siin.

| Väli | Väärtus |
| :--- | :--- |
| ADC → pinge teisenduse parameetrid | TODO — Data Acquisition Lab 2 result required |
| nullpunkt / offset | TODO — Data Acquisition Lab 2 result required |
| tõus / scale kPa jaoks | TODO — Data Acquisition Lab 2 result required |
| võimalikud piirid ja ühikud | TODO — Data Acquisition Lab 2 result required |

Konstantidele tuleb näidata nimi, arvväärtus ja ühik. Sisendit tuleb
valideerida ning vigase väärtuse korral jätta eelmine kehtiv seadistus alles.

## Rõhu test

Nupp `TEST PRESSURE SENSOR` kuvab ühe ja sama proovi kohta korraga:

| Raw ADC | Voltage (V) | Pressure (kPa) |
| :--- | :--- | :--- |
| TODO — real measurement required | TODO — real measurement required | TODO — real measurement required |

Kolm väärtust peavad pärinema samast proovist, et eristada ADC-/ühendusviga
teisendusvalemi või kalibratsiooni veast. Leht ei tohi näidata arvutatud kPa-d
kehtiva kalibratsiooni puudumisel; selle asemel näidatakse selget TODO/error olekut.

## Tarkvaraline kontroll enne laborit

- [x] Serveri aadressi skeem ja pikkus valideeritakse.
- [x] Polling-intervalli tüüp ja piirid valideeritakse.
- [x] Võtit ei tagastata seadete GET-vastuses ega logita.
- [x] Testpäring ei polli/claim'i tööd ega kutsu jaama/MG400 täitmisrada.
- [ ] Rõhukonstandid salvestatakse ainult täieliku valideerimise järel.
- [ ] Rõhutest seob raw ADC, V ja kPa sama proovi ID/ajaga.

## Riistvarakontroll

- [ ] Seaded püsivad pärast AtomS3 taaskäivitust.
- [ ] Production-hostile tehakse päris HTTPS polling.
- [ ] Vale või puuduva võtme vastus kuvatakse saladust avaldamata.
- [ ] `TEST SERVER HEALTH` vastus ja round-trip aeg on kontrollitud.
- [ ] Kiire ja aeglane polling-intervall on päriselt kontrollitud.
- [ ] Rõhu raw ADC, V ja kPa kuvatakse korraga ning vastavad mõõtmismeetodile.
- [ ] Andmehõive Lab 2 tegelikud kalibratsioonikonstandid on kasutusel.
- [ ] Hardware validation: TODO — real AtomS3 and sensor required.
