# AtomS3 lehe Lab 2 laiendus

Lab 2 PlatformIO projektis on nüüd minimaalne `Settings & tests` veebileht,
postkontori klient, rõhuanduri seadete/testi tarkvaraalus ja lokaalse kanali
piir. Labori 1 pildi saatmise, pumba ning täieliku captive-portali lehe
ühendamine on veel TODO; Lab 1 püsivara ei ole tervikuna kopeeritud.

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
Neid väärtusi ei hinnata ega leiutata siin. Lehel on nüüd väljad nelja
lineaarse teisendusparameetri jaoks, kuid vaikimisi on olek teadlikult
`not calibrated`.

| Väli | Ühik | Olek |
| :--- | :--- | :--- |
| `volts_per_count` | V / ADC count | TODO — Data Acquisition Lab 2 result required |
| `voltage_offset_v` | V | TODO — Data Acquisition Lab 2 result required |
| `kpa_per_volt` | kPa / V | TODO — Data Acquisition Lab 2 result required |
| `pressure_offset_kpa` | kPa | TODO — Data Acquisition Lab 2 result required |

Firmware arvutab samast raw proovist:

```text
voltage_v = raw_adc × volts_per_count + voltage_offset_v
pressure_kpa = voltage_v × kpa_per_volt + pressure_offset_kpa
```

Nii saab Andmehõive Lab 2 lõplikud lineaarse kalibratsiooni koefitsiendid
sisestada ilma püsivara ümber kirjutamata. Kõik neli välja peavad olema lõplikud
arvud ja moodustama piiratud teisendusvahemiku. Nulline skaleerimistegur,
`NaN`, lõpmatus, tekstijääk ning vahemikust väljas teisendus lükatakse tagasi;
vigase sisendi korral jääb eelmine kehtiv NVS seadistus alles.

Kalibratsioon asub eraldi Preferences namespace'is `pressure`. Laadimisel
valideeritakse koefitsiendid uuesti. Puuduv, osaliselt kirjutatud või vigane
NVS konfiguratsioon muutub fail-closed `uncalibrated` olekuks. See tarkvaraline
püsivusmudel on builditud; reboot-püsivus tuleb veel päris Atomil kontrollida.

## Rõhu test

Nupp `TEST PRESSURE SENSOR` kuvab ühe ja sama proovi kohta korraga:

| Raw ADC | Voltage (V) | Pressure (kPa) |
| :--- | :--- | :--- |
| TODO — real measurement required | TODO — real measurement required | TODO — real measurement required |

Kolm väärtust peavad pärinema samast proovist, et eristada ADC-/ühendusviga
teisendusvalemi või kalibratsiooni veast. Leht ei tohi näidata arvutatud kPa-d
kehtiva kalibratsiooni puudumisel. Praegune endpoint keskmistab kaheksa G5 raw
ADC lugemit ja tagastab `status: not_calibrated`, raw väärtuse ning `null`
pinge/kPa. Kehtiva kalibratsiooniga arvutatakse pinge ja kPa sama keskmistatud
raw väärtuse põhjal. Vahemikuviga annab error-vastuse, mitte arvulise rõhu.
ADC rail-koodid `0` ja `4095` käsitletakse samuti veana, sest need võivad
tähendada saturatsiooni, lühist või kasutuskõlbmatut tööpunkti.

Test on täielikult kohalik: see ei pöördu dropleti poole, ei polli töid, ei
kutsu station'it ega saa käivitada MG400-t või pumpa. Tarkvara ei saa ujuva
või valesti ühendatud analoogsisendi põhjal kindlalt tuvastada, kas füüsiline
andur on olemas; seetõttu ei tõenda edukas HTTP vastus sensor chain'i korrasolekut.

## Tarkvaraline kontroll enne laborit

- [x] Serveri aadressi skeem ja pikkus valideeritakse.
- [x] Polling-intervalli tüüp ja piirid valideeritakse.
- [x] Võtit ei tagastata seadete GET-vastuses ega logita.
- [x] Testpäring ei polli/claim'i tööd ega kutsu jaama/MG400 täitmisrada.
- [x] Rõhukonstandid salvestatakse ainult täieliku valideerimise järel.
- [x] Puuduv või vigane kalibratsioon ei tekita arvulist kPa tulemust.
- [x] Rõhutest arvutab raw ADC, V ja kPa samast keskmistatud proovist.
- [x] Native-testid katavad kalibreerimata oleku, korrektse teisenduse,
  vigased koefitsiendid, vigase raw ADC ja malformed seadete keeldumise.

## Riistvarakontroll

- [ ] Seaded püsivad pärast AtomS3 taaskäivitust.
- [ ] Production-hostile tehakse päris HTTPS polling.
- [ ] Vale või puuduva võtme vastus kuvatakse saladust avaldamata.
- [ ] `TEST SERVER HEALTH` vastus ja round-trip aeg on kontrollitud.
- [ ] Kiire ja aeglane polling-intervall on päriselt kontrollitud.
- [ ] Rõhu raw ADC, V ja kPa kuvatakse korraga ning vastavad mõõtmismeetodile.
- [ ] Andmehõive Lab 2 tegelikud kalibratsioonikonstandid on kasutusel.
- [ ] Hardware validation: TODO — real AtomS3 and sensor required.

## Labori kontrolliplaan

1. Ühendada Andmehõive Lab 2 päris sensor/op-amp chain ainult kontrollitud
   wiring'u järgi ning kinnitada, et väljund läheb Atomi G5 ADC sisendisse ja
   jääb lubatud pingevahemikku.
2. Salvestada testnupu raw ADC lugemid enne kalibratsiooni; kPa peab sellel
   etapil jääma `not calibrated`.
3. Mõõta sama tööpunkti op-amp väljundpinge multimeetriga ning võrrelda seda
   raw ADC ja Andmehõive mõõteahelaga.
4. Sisestada ainult Andmehõive Lab 2 pärisandmetest saadud
   `volts_per_count`, `voltage_offset_v`, `kpa_per_volt` ja
   `pressure_offset_kpa`.
5. Kontrollida mitut referentsrõhu punkti kogu kasutatavas vahemikus: raw ADC,
   multimeetri pinge, software voltage ja software kPa dokumenteeritakse sama
   proovi kohta.
6. Võrrelda software kPa tulemust referentsiga ning mitte märkida kriteeriumi
   tehtuks, kuni mõõteviga ja kasutatav vahemik on kinnitatud.
7. Taaskäivitada Atom, avada sama leht ja kontrollida NVS kalibratsiooni
   püsivust ilma koefitsiente uuesti sisestamata.
8. Korrata `TEST PRESSURE SENSOR` nuppu ning kinnitada, et raw ADC, voltage ja
   kPa kuvatakse koos; ühendus-/vahemikuviga peab olema error, mitte usutav
   võltsrõhk.
