# AtomS3 lehe Lab 2 laiendus

Lab 2 ei tee uut Atomi lehte. Aluseks jääb Labori 1 püsivara sama
`Settings & tests` osa, pildi saatmine, captive portal, tähe nupurežiim ning
lokaalne Atom → jaam kanal.

AtomS3 püsivara kohustuslik projektitöövoog on PlatformIO: reprodutseeritav
`platformio.ini`, lähtekoodipuu ja sõltuvused ning build/upload PlatformIO
kaudu. Arduino IDE ei ole selle repo peamine firmware-töövoog. Kui XIAO
ESP32S3 Sense püsivara hakkab selles repos elama, peab ka see olema eraldi
PlatformIO projekt. Reaalne build ja seadmetele laadimine on veel TODO.

> Siin kirjeldatakse kavandatavat laiendust. Püsivara muudatusi ja
> riistvarakontrolli ei ole selles etapis tehtud.

## Uued postkontori seaded

| Väli | Eesmärk | Salvestamine ja turve |
| :--- | :--- | :--- |
| `Post-office server address` | production HTTPS baasaadress | seadmes; valideerida skeem ja pikkus |
| `Atom authentication key` | Atomi API autentimine | seadmes; UI ei loe olemasolevat võtit tagasi ega logi seda |
| `Polling interval` | tööde küsimise intervall millisekundites | seadmes; lubatud min/max on TODO — real network test required |

Serveri aadress ei ole sama mis Labori 1 lokaalse jaama aadress. Atom pollib
dropletit väljamineva HTTPS-ühendusega ja edastab saadud kõrgtaseme töö
Labori 1 lokaalsesse kanalisse.

Salvestusvastus ei tohi sisaldada autentimisvõtit. Tühi võtmeväli tähendab
„jäta olemasolev võti muutmata“, kui serveri aadressi/seadme identiteeti ei
muudeta. Võtme teadlikuks eemaldamiseks peab olema eraldi kinnitatav tegevus.

## Postkontori test

Lehele lisatakse nupp `TEST POST-OFFICE REQUEST`, mis teeb ühe autentitud
testpäringu ilma robotit liigutamata. Leht näitab vähemalt:

- päringu olekut ja HTTP tulemust;
- serveri vastuse lühikest turvalist sisu või veakoodi;
- request'i round-trip aega;
- viimase õnnestunud polli aega;
- Atomi raporteeritud online/offline olekut;
- saladusi ega täielikku autoriseerimispäist ei näidata.

Testnupp ei loo `letter` ega `pick_place` tööd ja ei käivita MG400 rada.

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

- [ ] Serveri aadressi skeem ja pikkus valideeritakse.
- [ ] Polling-intervalli tüüp ja piirid valideeritakse.
- [ ] Võtit ei tagastata seadete GET-vastuses ega logita.
- [ ] Testpäring ei loo tööd ega kutsu jaama/MG400 täitmisrada.
- [ ] Rõhukonstandid salvestatakse ainult täieliku valideerimise järel.
- [ ] Rõhutest seob raw ADC, V ja kPa sama proovi ID/ajaga.

## Riistvarakontroll

- [ ] Seaded püsivad pärast AtomS3 taaskäivitust.
- [ ] Production-hostile tehakse päris HTTPS polling.
- [ ] Vale või puuduva võtme vastus kuvatakse saladust avaldamata.
- [ ] `TEST POST-OFFICE REQUEST` vastus ja round-trip aeg on kontrollitud.
- [ ] Kiire ja aeglane polling-intervall on päriselt kontrollitud.
- [ ] Rõhu raw ADC, V ja kPa kuvatakse korraga ning vastavad mõõtmismeetodile.
- [ ] Andmehõive Lab 2 tegelikud kalibratsioonikonstandid on kasutusel.
- [ ] Hardware validation: TODO — real AtomS3 and sensor required.
