# Nutikad Lahendused: Labor 3 — Ruuter ja VPN

> Labor 3 füüsiline töö ei ole veel alanud. See on tulevase labori
> dokumentaalne ettevalmistus. IP-aadressid, marsruudid, seadmevalikud,
> latentsused, kaameramõõdikud ja 48 tunni logi jäävad kuni päris kontrollini
> **TODO**. Varasemate laborite tulemusi kasutatakse ainult kontrollitud
> failiviidetega. Privaatvõtmeid, paroole ja tokeneid ei lisata siia kunagi.

**Töömaht:** 30 tundi | **Hindamine:** 20 punkti | **Meeskond:** 3 tudengit

**Välja antud:** 28.10.26 | **Tellimise kuupäev:** 06.11.2026 | **Esimene kaitsmine:** 19.11.2026, veebis

## Allikad ja tõendite piirid

[Ametliku ülesande täpne koopia](assignment-EST.md) vastab 25.10.2026
[õppejõu algallikale](https://github.com/KKallas/Narva-subjects/blob/main/EST/2026-27/Smart%20Solutions/Smart%20Solutions%20%5BLab%203%5D%20EST.md):
Git blob SHA `2d991551f8edd69751cf8a6940b77a6231e60d51`.
[Ametlik kokkuvõte](https://github.com/KKallas/Narva-subjects/blob/main/EST/2026-27/Smart%20Solutions/Smart%20Solutions%20%5BLabor%203%20kokkuv%C3%B5te%5D%20EST.md)
on abiallikas. Täielik ametlik ülesanne on varasemate plaanide suhtes ülimuslik.
Originaalkoopia ainepassi suhteline viide on säilitatud muutmata ja ei ole
selle repo kohalik faililink; siin navigeerimiseks kasuta allolevaid tööfailide
ning kontrollitud algallikate linke.

| Tõendi liik | Praegune seis ja piir |
|---|---|
| Valmis tarkvaraalus | Lab 2 Flask/SQLite, Atomi polling, XIAO HTTP ja kohalik kaameraserver koos mock-testidega; täpne seis [Lab 2 README-s](../lab2/README.md). See ei tõenda terviklikku robotirada. |
| Modelleerimine ja simulatsioon | Seotud kursuste CAD ja simulatsioonid ei kinnita uue tööriista füüsilist sobivust, võrku ega roboti ohutuskäitumist. |
| Dokumentaalne ettevalmistus | Siin on nõuded, kontrollimata otsuste väljad ja tühjad mõõtemallid. |
| Päris katsed | Lab 2 kuupäevaga kinnitatud tulemusi eristatakse allpool selle TODO-dest. Lab 3 võrgu-, VPN-, liikumis-, klapi- ja UV-katseid pole tehtud. |

## Eesmärk ja arhitektuur

Kaks sõltumatut kanalit jäävad lahku. Avalik HTTPS-postkontor võtab vastu
ainult lubatud kõrgtaseme töid. Atom algatab väljamineva pollingu ja edastab
vastuvõetud töö lokaalsele jaamale. Avalik postkontor ei vahenda otseseid
MG400 käske ega videovooge.

```text
Kasutaja --HTTPS--> avalik postkontor <--väljaminev polling-- Atom
                                                             |
                                                        kohalik kanal
                                                             v
                                                           jaam --> MG400
```

Privaatne WireGuardi kanal võimaldab tulevikus lubatud ligipääsu jaamale,
kohalikele kaameratele ja MG400 juhtimisele. Telefon on omaette peer;
ruuter algatab dropleti poole väljamineva ühenduse.

```text
Telefon --WireGuard--> droplet <--WireGuard-- labori ruuter
                                              |
                                              +-- jaam --> MG400
                                              |     ^
                                              |     +-- USB lauakaamera
                                              |     +-- kohalik HTTP XIAO kaamera
                                              +-- AtomS3R
                                              +-- XIAO ESP32S3 Sense
```

See on kontseptuaalne vaade; tegelik aadressiplaan ja lubatud teed on **TODO**.
WireGuardi lõpetamine jaamas on õpetaja lubatud varuvariant ainult siis,
kui päris ruuteri mudeli ja toe kontroll näitab selle vajadust.
Avalikul veebirakendusel ei tohi olla võimalust tunneli kaudu robotit juhtida ega kaameraid vahendada. Selle piirangu tegelik rakendamine ja kontroll on TODO.

**KAARDISTA ISE — eesmärk nii, nagu ta tegelikult välja tuli.**

TODO — täita pärast meeskonna tegelikke otsuseid ja katseid.

## Kontrollnimekiri

Järgmised 17 punkti on ametlikust ülesandest sõna-sõnalt ja samas järjekorras.
Dokumentatsiooni sünkroonimine ei täida neid kriteeriume.

- [ ] Aadressiplaan paberil ja draw.io-s: iga seade, aadress, alamvõrk, kes aadressi andis.
- [ ] Ruuter seadistatud: robot, jaam, Atom ja kaameramoodul on tema võrgus ja saavad iga kord sama aadressi. Ruuteri vaikimisi parool on vahetatud.
- [ ] Labori 1 ja 2 asjad töötavad uues võrgus edasi: jaam liigutab robotit, Atom käib postkontoris ja sõnum paneb roboti tööle, kaamerad on jaama lehel.
- [ ] Ruutimistabel loetud jaamas ja ruuteris, iga rea kohta üks lause. Kolm teekonda ennustatud ja siis mõõdetud.
- [ ] NAT nähtud: mis aadressi pealt droplet sind näeb, ja miks see ei ole su jaama aadress.
- [ ] Tunnel üleval ruuteri ja dropleti vahel. Tuleb pärast ruuteri taaskäivitust ise tagasi.
- [ ] Telefon on tunnelis: jaama leht avaneb telefonist, mille WiFi on välja lülitatud, ja nupud liigutavad robotit.
- [ ] Ilma tunnelita ei pääse jaamani ega robotini väljast keegi. Kontrollitud väljast.
- [ ] Üks marsruut meelega katki tehtud: ennustus, mis lakkab töötamast, ja mis päriselt lakkas.
- [ ] Latentsus mõõdetud: 30 vajutust labori võrgus ja 30 läbi tunneli.
- [ ] Mõlemad kaamerad läbi tunneli: viide, kaadrisagedus, ribalaius.
- [ ] Ühenduse katkemine keset liigutust otsustatud, tehtud ja kolm korda läbi proovitud.
- [ ] Tunneli logi 48 tundi dropleti poolt, katkestused üles loetud.
- [ ] Labori 2 ohutuskokkulepe otsejuhtimise jaoks täiendatud ja kõigil meeskonnaliikmetel loetud.
- [ ] Klapi ja UV LED-i seaded ja testinupud Atomi lehel, `docs/atom_page.md` uuendatud.
- [ ] Tellimus 06.11 failis `docs/bom.md`.
- [ ] Repo ja arenduspäevik täidetud, tag `smart-solutions-lab3`.

**KAARDISTA ISE — kuupäevad ja sinu enda sammud.**

TODO — täita päris töö käigus.

## Vajalikud sisendid varasematest laboritest

### Smart Solutions Lab 2

Kontrollitud lähteallikad: [README](../lab2/README.md),
[kaamerad](../lab2/docs/cameras.md) ja [ohutuskokkulepe](../lab2/docs/safety.md).

- Tarkvaraalus sisaldab Flask/SQLite postkontorit, lubatud `letter` ja
  `pick_place` töid, Atomi pollingut, station-adapterit ning USB/XIAO
  kaameraserverit. `pick_place` executor on mock.
- 20.10.2026 on dokumenteeritud päris dropleti, avaliku HTTPS-i ja
  autentitud lehe kontroll mobiilse andmesidega; need pole Lab 3 VPN-testid.
- Atomi lokaalne autentitud polling, reboot-püsivus ja Wi-Fi recovery on
  varasemate kuupäevadega dokumenteeritud. 23.10 HEALTH_ONLY kinnitas Wi-Fi
  ja TLS-i, kuid HTTP/JSON ebaõnnestus; production-polling on TODO.
- XIAO diagnostiline USB JPEG teises kursuses ei kinnita Smart Solutions
  Wi-Fi firmware upload'i ega HTTP snapshot'i station'is.
- Mõlemad füüsilised kaamerad station'i lehel, kogu laua vaade, kaitstud
  LAN-ligipääs, station'i integreerimine ja MG400 tervikahel on TODO.
  Eraldi kaameraserveri vaikebind on loopback ja autentimine puudub;
  seda ei avata VPN/LAN-i enne kohaliku ligipääsupiiri otsust.
- Kaamera- ja juhtimislatentsuse lähteväärtused ning iga liikme isiklik
  ohutuskinnitus tuleb võtta ainult kinnitatud Lab 2 tõenditest; puuduv jääb TODO.

### Andmehõive Lab 3

[Kontrollitud dokumentatsioon, commit 74764e6](https://github.com/Dennel04/data-acquisition-course/blob/74764e6dc8a83f868b90862edb48158d3619b595/data-acquisition/lab3/README.md):
`pump → Y1 → iminapp / 3/2 klapp → süstal`.
Napp jääb otse pumba harusse. Klapp juhib ainult süstlaharu: voolu all pump
süstlasse, vooluta pump lahutatud ja süstal atmosfääri. See ei ole pumba
ümberlüliti napa ning süstla vahel. Tööjärjekord on
**doseerimine → klaasi tõstmine → kõvendamine → väljund**.

Klapi ja UV LED-i käsud, riistvaraliides, vahemikud, ohutuskäitumine ning
alarmi-/sündmuseleping kooskõlastatakse enne koodi kirjutamist.
Dokumenteeritud JSON-käsud on seni näited, mitte kinnitatud teostus.
**TODO — füüsiline teostus ja liidese kokkulepe pole veel kinnitatud.**

### 3D printimise Lab 3

[Kontrollitud dokumentatsioon, commit 6068053](https://github.com/Dennel04/3d-printing-course/blob/6068053f90d09fa301889ee4476e139a78dd82ad/3d-print/lab3/README.md):
ühine tööriist iminapa, süstla, UV-lambi ja kaameraga; sama Y-pneumaatika ning
musta katte all kõvendamine. Vajalikud on neli kontrollitud flantsinihet:
iminapp, süstla otsik, UV-laigu keskpunkt ja kaamera pildi keskpunkt.
Uue tööriistaga õpetatakse/kontrollitakse punktid uuesti.
**TODO — uus tööriist, neli nihet ja füüsiline sobivus pole veel kinnitatud.**

## Tööfailid

- [Aadressiplaan](docs/network_plan.md) — LAN/WAN, seadmed ja tõendite allikad.
- [Ruutimine ja NAT](docs/routing.md) — tabelid, ennustused ning päris tulemuste väljad.
- [WireGuardi plaan](docs/wireguard/README.md) — peer'id, lubatud teed ja tulevased kontrollid.
- [Ohutuskokkulepe](docs/safety.md) — otsejuhtimine, katkestused ja UV.
- [Atomi leht](docs/atom_page.md) — olemasoleva lehe klapi/LED-i seaded ja testid.
- [BOM](docs/bom.md) — inventuur ja põhjendatud tellimisvajadus.
- [Mõõtemetoodika](docs/measurements.md) — ühikud, ajabaas ja analüüsi plaan.
- [Kohalik latentsus](data/latency_local.csv) ja [VPN-latentsus](data/latency_vpn.csv).
- [VPN-kaamerad](data/camera_vpn_metrics.csv) ja [48 tunni tunneli logi](data/tunnel_48h.csv).

### Arenduspäevik

**KAARDISTA ISE — päevik.** Üks sissekanne iga töösessiooni kohta, kirjutatud nii, et inimene, kes kohal ei olnud, saab aru. Sissekandeid lisatakse, mitte ei muudeta.

**PP.KK.AA — kes olid kohal**
* Tegime:
* Juhtus (numbrid):
* Otsustasime, ja miks:
* Lahti järgmiseks korraks:

**12.10.26 — Nikita**
* Tegime: valmistasime ette tulevase Labori 3 kaustastruktuuri, salvestasime õppejõu ametliku ülesande muutmata kujul ning koostasime README, dokumentatsiooni ja andmete mallid. Füüsilisi katseid ei tehtud; ruuterit, VPN-i, dropletit, MG400-t ega Atomi riistvara ei kasutatud.
* Juhtus (numbrid): valmis 4 ainult päisega CSV-malli. Ülesande ametlik väljaandmiskuupäev on 28.10.26, tellimise tähtaeg 06.11.26 ja esimene kaitsmine 17.11.26; need on ajakava, mitte katsetulemused.
* Otsustasime, ja miks: IP-aadresse, ruute, võtmeid ega mõõtetulemusi ei täideta enne päris süsteemi kontrollimist, et ettevalmistust ei esitletaks tehtud laborina.
* Lahti järgmiseks korraks: lõpetada kõigepealt Labor 2 ning alustada Labor 3 tööd alles siis, kui selle sõltuvused on päriselt saadaval.

**25.10.2026 — dokumentatsiooni sünkroonimine; osalejad teadmata**

* Tegime: kontrollisime ametlikku ülesannet ja kokkuvõtet ning seotud Andmehõive ja 3D printimise Lab 3 avaldatud dokumente; uuendasime ainult Lab 3 dokumentatsiooni ja juurkausta juhiseid.
* Juhtus (numbrid): ametliku ülesande blob SHA on `2d991551f8edd69751cf8a6940b77a6231e60d51`; 17 kontrollpunkti kopeeriti sõna-sõnalt ja kõik jäid lahti. Esimene kaitsmine on nüüd 19.11.2026; tellimise tähtaeg on 06.11.2026. Need on allika ja ajakava andmed, mitte mõõtmised.
* Otsustasime, ja miks: klapp juhib süstlaharu ning tühjendab selle vooluta atmosfääri; UV kasutamine on ainult kohalik, läbipaistmatu katte all ja Atomi taimeriga. Aadressid, AllowedIPs, ohutu katkestuskäitumise teostus ja kõik päris tulemused jäävad TODO.
* Tegelik tulemus: dokumentaalne ettevalmistus. Füüsilist sessiooni, riistvara koostamist, võrgu seadistamist, firmware laadimist ega mõõtmisi ei toimunud; ruuterit, tunnelit, dropletit, MG400-t, klappi ja LED-i ei katsetatud. Varasem päevikukanne säilitati muutmata; selle 17.11 kuupäev kajastab toonast ülesannet.
* Lahti järgmiseks korraks: kontrollida Lab 2 sõltuvusi, ruuteri mudelit ja inventuuri; kooskõlastada riistvaraliides, otsejuhtimise ohutus ning neli tööriistanihet enne päris Lab 3 tööd.

### Väljundid ja tulemused

**Väljundid**
* Andmehõive L3: TODO — kontrollitud klapi ja UV LED-i käsud, seaded, testid ning vajaduse korral alarmisündmus.
* 3D printimine L3: TODO — kaugelt nähtav ühendatud tööriist ja kontrollitud tööriistanihked.
* Nutikad Lahendused L4: TODO — kontrollitud võrk, tunnel ja droplet.

**KAARDISTA ISE, lõpus.**
* Git repo ja tag: TODO — tag luuakse alles esitamisel.
* Numbrid, mille see labor andis, ühikutega: TODO — päris mõõtmised.
* Mida me teeksime teisiti: TODO — täita pärast laborit.
* Mida järgmine labor peaks enne alustamist teadma: TODO — täita kontrollitud tulemuste põhjal.
