# Lab 2 BOM ja tellimiseelne kontroll

**Tellimise kuupäev:** 16.10.26

Kaamerate 23.10.26 teadaolev seis pärineb [3D Printing Lab 2-st](https://github.com/Dennel04/3d-printing-course/blob/main/3d-print/lab2/README.md).
Ülejäänud saadavus ja tellimisvajadus tuleb laboris kontrollida. Droplet ja domeen tulevad
õppejõu kontolt ega lähe meeskonna riistvaratellimusse.

| Kontrollitav osa | Nõue / miks vaja | Tegelik olemasolu | Tellitav kogus või tegevus |
| :--- | :--- | :--- | :--- |
| Verbatim AWC-03 (49580), USB veebikaamera | laua üldvaade: kogu ruudustik ja robot | 3D Printingus identifitseeritud; lõplik paigaldus ja kogu laua FOV kinnitamata | TODO — kontrollida paigaldust ja sobivust enne lisatellimust |
| USB pikenduskaabel | ulatub kaamerapostist jaamani ilma pingeta | TODO — kontrollida laboris enne 16.10.26 | TODO — mõõta vajalik pikkus |
| XIAO ESP32S3 Sense, tootekood 113991115 | tööriista lähikaamera | 23.10.26 J4 kinnituses kasutatud; OV3660, JPEG 1600 × 1200 USB Serial COM5 kaudu | Smart Solutions Wi-Fi firmware upload ja HTTP snapshot TODO; uut ostuvajadust pole kinnitatud |
| Tööriistakaamera toide | toide kogu roboti tööalas; meetod ei tohi liikumist takistada | USB-C arvutist kasutati USB diagnostikas; lõplik allikas ja kaablitee TODO | TODO — kinnitada allikas, pikkus ja liikumisvaru |
| Lauakaamera post/kinnitus | kaamera robotist kõrgemale | TODO — kontrollida laboris enne 16.10.26 | TODO — kooskõlastada 3D Printing Lab 2-ga |
| Tööriistakaamera kinnitus | J4 paigutus peab näitama otsikut ja detaili | 3D Printingus dokumenteeritud J4 variant; allika järgi õpetaja suuline luba; XIAO oli kinnituses | TODO — FOV, kaablitee ja liikumisohutus; lõplik sobivus pole kinnitatud |
| Kinnituselemendid | kruvid, mutrid, vahedetailid ja muud valitud kinnituse osad | TODO — kontrollida laboris enne 16.10.26 | TODO — määrata pärast kinnituste valikut |
| Strain relief | USB-/toitepistikule ei mõju roboti liikumisjõud | TODO — kontrollida laboris enne 16.10.26 | TODO — valida pärast füüsilist kontrolli |
| USB-hub / USB-adapterid | veebikaamera, Atom ja võimalikud adapterid korraga | TODO — kontrollida laboris enne 16.10.26 | TODO — määrata pärast jaama portide kontrolli |
| USB-/toitekaablid | mõlema kaamera ja Atomi ühendamine | TODO — kontrollida laboris enne 16.10.26 | TODO — määrata pärast inventuuri |
| AtomS3R varuseade / kontrollseade | teise eksemplariga ekraani ja firmware'i ristkontroll; praegune Atom töötab USB, Seriali ja Wi-Fi kaudu, kuid ekraan ei näita pilti ning lõplik riistvaraviga ei ole kinnitatud | TODO — kontrollida laboris, kas teine AtomS3R on saadaval | TODO — tellida ainult siis, kui laboris sobivat kontrollseadet ei ole ja see on projekti jaoks päriselt vajalik |

## Füüsilised kontrollid enne tellimust

- [ ] Kontrolli laboris, kas teine AtomS3R on ekraani ristkontrolliks saadaval.
- [x] XIAO olemasolu ja diagnostiline USB JPEG on 3D Printingus kinnitatud.
- [ ] Kontrolli identifitseeritud Verbatim AWC-03 lõplikku paigaldust ja FOV-d.
- [ ] Mõõda USB pikenduse vajalik pikkus mööda päris kaabliteed.
- [ ] Kontrolli tööriistakaamera toidet kogu roboti liikumisulatuses,
  robot välja lülitatud.
- [ ] Kooskõlasta mõlemad kinnitused 3D Printing Lab 2 meeskonnatööga.
- [ ] Kontrolli strain relief'i ja kokkupõrke-/takerdumisohtu.
- [ ] Kontrolli kaablite marsruutimist, painutusraadiust ja takerdumise vältimist
  kogu roboti liikumisulatuses, robot välja lülitatud.
- [ ] Mõõda Atomi Wi-Fi levi ja postkontori polling kavandatud tööasendis.
- [ ] Mõõda tööriistakaamera Wi-Fi levi kogu roboti tööalas.
- [ ] Kontrolli Etherneti station PC ligipääsu Wi-Fi XIAO IP-le, alamvõrke,
  marsruutimist ja client isolation'it; võrgu toimimist ei eeldata.
- [ ] Kontrolli jaama vabade USB-portide ning vajalike hub'ide/adapterite sobivust.
- [ ] Kontrolli jaama võrguadapterite sobivust roboti Etherneti ning vajaliku
  labori-/internetivõrgu jaoks.
- [ ] Märgi iga BOM-i rea juurde kontrollimise kuupäev ja tegelik tulemus.
- [ ] Lisa tellimusse ainult füüsiliselt kinnitatud puuduvad osad ja iga osa põhjus.

Valitud XIAO põhipüsivara on selle repo `firmware-xiao-camera/` (Wi-Fi HTTP
`GET /snapshot.jpg`); 3D Printingu USB Serial build jääb diagnostiliseks varuks.
USB-katse ei kinnita Wi-Fi upload'i ega HTTP tööd. Ühendused ja järgmise
laborikatse plaan: [docs/cameras.md](cameras.md). Droplet videovooge ei vahenda.
