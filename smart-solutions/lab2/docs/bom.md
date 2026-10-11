# Lab 2 BOM ja tellimiseelne kontroll

**Tellimise kuupäev:** 16.10.26

See fail ei kinnita ühegi komponendi olemasolu ega puudumist. Iga rida tuleb
enne tellimist füüsiliselt laboris üle kontrollida. Droplet ja domeen tulevad
õppejõu kontolt ega lähe meeskonna riistvaratellimusse.

| Kontrollitav osa | Nõue / miks vaja | Tegelik olemasolu | Tellitav kogus või tegevus |
| :--- | :--- | :--- | :--- |
| USB UHD veebikaamera | laua üldvaade: kogu ruudustik ja robot | TODO — physical inventory required | TODO |
| USB pikenduskaabel | ulatub kaamerapostist jaamani ilma pingeta | TODO — measure required length | TODO |
| XIAO ESP32S3 Sense, tootekood 113991115 | tööriista lähikaamera | TODO — physical inventory required | TODO |
| Tööriistakaamera toide | toide kogu roboti tööalas; meetod ei tohi liikumist takistada | TODO — design decision required | TODO |
| Lauakaamera post/kinnitus | kaamera robotist kõrgemale | TODO — 3D Printing Lab 2 dependency | TODO |
| Tööriistakaamera kinnitus | kaamera iminapa/tööriistahoidiku juurde | TODO — 3D Printing Lab 2 dependency | TODO |
| Kinnituselemendid | kruvid, mutrid, vahedetailid ja muud valitud kinnituse osad | TODO — mounting design required | TODO |
| Kaablite marsruutimine | liikumisulatus, painutusraadius ja takerdumise vältimine | TODO — physical route inspection required | TODO |
| Strain relief | USB-/toitepistikule ei mõju roboti liikumisjõud | TODO — physical design required | TODO |
| Atomi Wi-Fi levi | postkontori polling kavandatud tööasendis | TODO — real network test required | TODO |
| Tööriistakaamera Wi-Fi levi | videovoog kogu roboti tööalas | TODO — real network test required | TODO |
| Jaama USB pordid/hub | veebikaamera, Atom ja võimalikud adapterid korraga | TODO — station inspection required | TODO |
| Jaama võrguadapterid | roboti Ethernet ning vajalik labori-/internetivõrk | TODO — station inspection required | TODO |
| USB-/toitekaablid ja adapterid | mõlema kaamera ja Atomi ühendamine | TODO — cable inventory required | TODO |

## Enne tellimuse kinnitamist

- [ ] Märgi iga rea juurde kontrollimise kuupäev ja tegelik tulemus.
- [ ] Mõõda USB pikenduse vajalik pikkus mööda päris kaabliteed.
- [ ] Kooskõlasta mõlemad kinnitused 3D Printing Lab 2 meeskonnatööga.
- [ ] Kontrolli tööriistakaamera toidet ja kaablit kogu roboti liikumisulatuses,
  robot välja lülitatud.
- [ ] Kontrolli strain relief'i ja kokkupõrke-/takerdumisohtu.
- [ ] Mõõda Atomile ja tööriistakaamerale Wi-Fi levi kavandatud asukohtades.
- [ ] Kontrolli jaama vabad pordid ning kõik vajalikud hub'id/adapterid.
- [ ] Lisa tellimusse ainult füüsiliselt kinnitatud puuduvad osad ja iga osa põhjus.
