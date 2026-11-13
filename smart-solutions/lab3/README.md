# Nutikad Lahendused: Labor 3 — Ruuter ja VPN

**Töömaht:** 30 tundi | **Hindamine:** 20 punkti | **Meeskond:** 3 tudengit

**Välja antud:** 28.10.26 | **Tellimise kuupäev:** 06.11.2026 | **Esimene kaitsmine:** 19.11.2026, veebis

[Ametlik ülesanne](assignment-EST.md) · [Praegune seis](#praegune-seis-13112026) ·
[Tõendid](#tõendid-ja-tulemused) · [Arhitektuur](#süsteemi-arhitektuur) ·
[Tööplaan](#tööplaan) · [Kiirstart](#kiirstart-ilma-riistvarata) ·
[Kaitsmine](#kaitsmise-juhend) · [Kontrollnimekiri](#kontrollnimekiri) ·
[Arenduspäevik](#arenduspäevik).

## Ülevaade

Laboris 3 ühendame roboti, jaama, Atomi ja kaameramooduli ühte
laborivõrku. Seejärel kavandame telefonile privaatse tee jaamani,
mõõdame ühenduse mõju juhtimisele ja kaamerapildile ning kontrollime,
kuidas süsteem käitub ühenduse katkemisel. Atomi lehele on kavas lisada
klapi ja UV LED-i seaded ning kohalikud testinupud.

| Osa | Roll Lab 3-s |
| --- | --- |
| Labori ruuter | Ühendab seadmed kohalikku võrku, jagab aadresse ja valib tee teistesse võrkudesse. Tulemüür piirab ühendusi. |
| Droplet | Internetis kättesaadav virtuaalserver, kuhu Lab 2-s paigaldati HTTPS-postkontor. Lab 3 plaanis vahendab droplet eraldi WireGuardi ühendusi. |
| WireGuard ja telefon | WireGuard loob krüpteeritud tunneli seadmete vahel. Telefon liitub oma võtmega ja kasutab katsel mobiilset andmesidet, et proovida jaama lehte väljastpoolt laborivõrku. |
| Jaam ja MG400 | Jaam on laboriarvuti, kus jookseb roboti juhtimistarkvara ja kuvatakse kaamerapilti. MG400 on robot, mis täidab jaamast saadetud liikumiskäske. |
| AtomS3R | Ekraaniga mikrokontroller, mis küsib postkontorilt lubatud töid. Klapi ja UV juhtimine on kavandatud Atomi olemasolevale lehele. |
| Kaamerad | USB-lauakaamera peab näitama kogu tööala. XIAO tööriistakaamera on mõeldud otsiku lähivaateks. Mõlemat pilti kuvab plaani järgi jaam. |

Avalik HTTPS-postkontor on tööde tellimiseks. Privaatne VPN on
kavandatud volitatud ligipääsuks labori jaamale ja kaameravaatele.

## Praegune seis (13.11.2026)

- **Tarkvara.** Olemas on WireGuardi logija ja võrguühenduseta analüüs,
  klapi ja UV olekumudel ning alarmisündmuste puhver. Testid kasutavad
  sünteetilisi andmeid, asendatud käsuvastuseid ja loogilisi väljundeid.
- **Varasemad päriskatsed.** Lab 1-s joonistas MG400 tähti. Lab 2-s
  kontrolliti 20.10 avalikku HTTPS-i, 06.11 ühe Atomi LCD-d kohaliku
  HTTP kaudu ning 13.11 Atomi oleku- ja seadete päringuid telefoni
  pääsupunktis ja eraldi dropleti SSH-ligipääsu. Need katsed käisid
  varasemate laborite seadistuste kohta. [Lab 1 tõend](../lab1/docs/letters.md) ·
  [Lab 2 seis](../lab2/README.md#praegune-seis-13112026).
- **Ettevalmistus.** Aadressiplaani, marsruutide ja WireGuardi tööfailid,
  inventuurimall, ohutuskokkuleppe mustand ning mõõtemetoodika on olemas.
  Neljas mõõte-CSV-s on ainult päised. [Tööplaan](#tööplaan).
- **Lab 3 päriskatsed.** Ruuteri ja tunneli seadistus, jaama ja kaamerate
  ligipääs, roboti katkestuskäitumine, 48 tunni seire ning klapi ja UV
  füüsiline juhtimine ootavad katseid. Lab 3 füüsilised tulemused on TODO.

## Tõendid ja tulemused

| Tõend | Tulemus ja selle ulatus | Kust vaadata |
| --- | --- | --- |
| WireGuardi logija ja analüüs | Kõik 23 Python-testi õnnestusid sünteetiliste ridade ja asendatud käsuvastustega. Testid katavad liidese ja marsruudi kontrolli, logi jätkamist ning puuduvaid andmeid. Lab 3 päris tunneliseire on ootel. | [Logija ja analüsaator](tools/tunnel_monitor.py) · [Testid](tests/test_tunnel_monitor.py) · [Metoodika](docs/measurements.md#tunneli-48-tunni-logi) |
| Klapi ja UV C++17 olekumudel | 19 hostitesti kontrollivad muu hulgas klapi ühe impulsi piirangut, UV kohalikku luba ja loogilise väljundi väljalülitumist. GPIO, relee, elektrilised tasemed ja tegelik väljalülitus ootavad kinnitust. | [Mudel](../lab2/firmware/src/core/actuator_model.cpp) · [Testid](../lab2/firmware/test/test_actuator_model/test_main.cpp) · [Integratsiooni seis](docs/atom_page.md#tarkvaramudel-ja-integratsiooni-seis) |
| Alarmisündmuste edastus | 13 hostitesti kontrollivad, et lühike häire jääb meelde, häirel on taimeri ees eelis ning vana seansi sündmus ei lõpeta uut toimingut. Päris katkestusrutiini (ISR) sidumine on ootel. | [Sündmuste puhver](../lab2/firmware/include/actuator_events.h) · [Testid](../lab2/firmware/test/test_actuator_events/test_main.cpp) |
| Varasem püsivara regressioon, 07.11.2026 | Päevikus on kirjas 104 läbitud native-testi ja kolm edukat PlatformIO koostet. Koostetulemus näitab, et projekt kompileerus. | [Arenduspäevik](#arenduspäevik) · [Platvormi seadistus](../lab2/firmware/platformio.ini) |
| Varasem Lab 2 päriskatse, 06.11.2026 | Ühe Atomi LCD näitas kaht pilti. Kohalik HTTP-testserver sai mõlemale tööle oleku `done / local_display`. | [LCD-katsete raport](../lab2/docs/display_image_evidence.md) |
| Füüsiliste mõõtmiste mallid | Latentsuse, kaamerate ja VPN-i mõõteridu veel pole. 17 280 on 48 tunni jooksul kavandatud 10-sekundiliste intervallide arv. | [Kohalik latentsus](data/latency_local.csv) · [VPN-latentsus](data/latency_vpn.csv) · [Kaamerad](data/camera_vpn_metrics.csv) · [Tunneli logi](data/tunnel_48h.csv) |

## Allikad ja tõendite piirid

[Ametliku ülesande täpne koopia](assignment-EST.md) vastab 25.10.2026
[õppejõu algallikale](https://github.com/KKallas/Narva-subjects/blob/main/EST/2026-27/Smart%20Solutions/Smart%20Solutions%20%5BLab%203%5D%20EST.md):
Git blob SHA `2d991551f8edd69751cf8a6940b77a6231e60d51`.
[Ametlik kokkuvõte](https://github.com/KKallas/Narva-subjects/blob/main/EST/2026-27/Smart%20Solutions/Smart%20Solutions%20%5BLabor%203%20kokkuv%C3%B5te%5D%20EST.md)
on abiallikas. Täielik ametlik ülesanne on varasemate plaanide suhtes ülimuslik.
Originaalkoopia ainepassi suhteline viide on säilitatud muutmata ja ei ole
selle repo kohalik faililink; siin navigeerimiseks kasuta allolevaid tööfailide
ning kontrollitud algallikate linke.

## Süsteemi arhitektuur

### Avalik HTTPS-postkontor

Brauser jätab HTTPS-i kaudu järjekorda lubatud töö. Atom küsib töid
korrapäraselt väljamineva HTTPS-päringuga. Robotitöö kavandatud rada läheb
Atomist kohaliku jaama kaudu MG400-ni. Avaliku teenuse roll piirdub
tööjärjekorra ja tulemustega. Lab 2 skeem näitab ka USB- ja kaameraühendusi.
[Skeem](../lab2/docs/system.svg) · [Muudetav draw.io fail](../lab2/docs/system.drawio).

```text
Kasutaja --HTTPS--> avalik postkontor <--väljaminev polling-- Atom
                                                             |
                                                        kohalik kanal
                                                             v
                                                           jaam --> MG400
```

### Privaatne WireGuardi tee (plaan)

Telefon ja ruuter algatavad kumbki dropleti poole oma WireGuardi ühenduse.
Telefon avab plaani järgi jaama lehe. Jaam jääb kaamerate ja MG400
kohalikuks ühenduspunktiks.

```text
Telefon --WireGuard--> droplet <--WireGuard-- labori ruuter
                                              |
                                              +-- jaam --> MG400
                                              |     ^
                                              |     +-- USB lauakaamera
                                              |     +-- kohalik HTTP XIAO kaamera
                                              +-- AtomS3R
```

Tegelik aadressiplaan ja lubatud teed on TODO. Kui ruuter WireGuardi ei
toeta, lubab õppejõud varuvariandina tunneli jaamas lõpetada. Igal tunneli
osalejal ehk peer'il on oma võtmepaar. `AllowedIPs` seob sihtvõrgud
peer'iga ja piirab temalt vastu võetavaid lähteaadresse. Ligipääsu
piiravad lisaks tulemüür ja teenuse autentimine.
Avaliku postkontoriprotsessi eraldamine tunneli juhtimisrajast ja
videovoogudest tuleb rakendada ning kontrollida. [WireGuardi plaan](docs/wireguard/README.md#ligipääs-ja-tulemüür).

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

## Tööplaan

Punktinumbrid viitavad [ametliku kontrollnimekirja](#kontrollnimekiri)
järjekorrale. Kasuta etappe töö korraldamiseks ja tõendite leidmiseks.
Kõik 17 punkti on avatud.

### A. Inventuur ja aadressiplaan

- **Eeldus ja alus (punktid 1, 16).** Vaja on õppejõu ruuterit,
  admin-ligipääsu, labori võrgupesa ja seadmete loendit. Alusta olemasoleva
  aadressi- ja inventuurimalli põhjal.
- **Järgmine töö.** Kontrolli laboris ruuteri mudelit, WireGuardi tuge,
  kaableid ja jaama Etherneti ühendust. Pane paberile ja draw.io-sse
  seadmed, alamvõrgud ning kes aadressid määrab. Põhjenda roboti aadressi
  säilitamise või muutmise otsus. Tellimuse tegelik seis vajab kinnitamist.
- **Tõend ja failid.** Kanna kontrollitud seadmed, LAN/WAN piirid ja
  aadresside allikad aadressiplaani. Lisa skeemi pilt koos muudetava
  draw.io viitega. Märgi inventuur ja kinnitatud tellimus BOM-i.
  Mallide ülevaatus sobib võrguühenduseta, inventuur ja kinnitamine
  vajavad ligipääsu laborile ja tellimuse andmetele.
  [Aadressiplaan](docs/network_plan.md) · [BOM](docs/bom.md).

### B. Ruuter, marsruudid ja NAT

- **Eeldus ja alus (punktid 2–5).** Vajalikud on kinnitatud aadressiplaan
  ja ruuteri ligipääs. Jaama ning ruuteri tabelite jaoks on väljad olemas.
- **Järgmine töö.** Seadista püsivad aadressid kinnitatud plaani järgi ja
  vaheta ruuteri vaikimisi admin-parool. Kontrolli Lab 1 ja 2 töövooge uues
  võrgus ohutuskokkuleppe järgi. Ennusta jaama teed robotini, dropletini
  ja internetti ning võrdle ennustusi vaatlustega. Selgita, millist
  lähteaadressi droplet näeb. NAT tähendab aadressi teisendamist võrgu piiril.
- **Tõend ja failid.** Salvesta saladusteta ruuteriseadistus, mõlema
  ruutimistabeli seletused, kolm ennustust koos mõõtetulemusega ning
  NAT-i vaatlus ja selle allikas. Ennustused saab kirja panna enne katset.
  Tabelite ja teekondade kinnitamine vajab päris võrku, NAT-i vaatlus
  dropleti ligipääsu. [Aadressiplaan](docs/network_plan.md) ·
  [Ruutimine ja NAT](docs/routing.md).

### C. WireGuard ja võrgu eraldus

- **Eeldus ja alus (punktid 6–9).** Vaja on kinnitatud tunneli
  lõpp-punkte ja volitatud ligipääsu. WireGuardi plaanis on peer'ide
  rollid ning lubatud teede kontrolli väljad.
- **Järgmine töö.** Kinnita iga lubatud tee eesmärk, jaama ligipääsupiir
  ja avaliku postkontori eraldus. Kontrolli tunnelit pärast ruuteri
  taaskäivitust ja ligipääsu väljast ilma tunnelita. Pane enne
  marsruudikatset kirja ennustus ja taastamisplaan. Seejärel võrdle
  tulemust ennustusega ja kinnita taastumine. Telefoni jaama- ja
  liikumiskatse eeldused on etapis D.
- **Tõend ja failid.** Lisa võtmeteta tunneli skeem ja seadistuse ülevaade,
  taastumisaeg, välise ligipääsu kontroll ning marsruudikatse tulemus.
  Ligipääse ja taastamist saab kavandada võrguühenduseta. Katseteks on
  vaja ruuterit, dropletit ning telefoni mobiilset andmesidet.
  [WireGuardi plaan](docs/wireguard/README.md#tulevased-kontrollid) ·
  [Marsruudikatse](docs/routing.md#tahtlikult-katkine-marsruut).

### D. Jaama leht ja kaamerapildi ohutus

- **Eeldus ja alus (punktid 3, 7, 11, 14).** Lab 2-s on jaama leht ja
  kaameratestid näidisvoogudega. Vaja on kaitstud jaamavaadet, kogu
  tööala näitavat kaamerat ja meeskonna ohutuskokkulepet.
- **Järgmine töö.** Kinnita kohapeal mõlema kaamera pilt ning vaateväljad.
  Kontrolli jaama lehte telefonis mobiilse andmesidega, Wi-Fi välja
  lülitatud. Enne kaugliikumist rakenda ja kontrolli katkestuskäitumist
  kohapeal. Süsteem peab ühenduse kadumisel jõudma kokkulepitud
  ohutusse olekusse. Kaugjuhtimine eeldab isiklikku volitust
  ja kohaliku vastutaja luba. Liikumiskatsel peab vastutaja nägema kogu
  tööala ning ulatuma füüsilise hädastopini. Iga liige kinnitab
  kokkuleppe ise.
- **Tõend ja failid.** Lisa jaamavaate ja ligipääsu tõendid, mõlema kaamera
  vaate kinnitused ning meeskonna nõusolekud. Mõõdud kogutakse etapis E.
  Plaani saab lugeda võrguühenduseta, vaate ja juhtimise kontroll toimub
  laboris. [Kaameraplaan](../lab2/docs/cameras.md#labori-kontrolliplaan) ·
  [WireGuardi kontrollid](docs/wireguard/README.md#tulevased-kontrollid) ·
  [Ohutuskokkulepe](docs/safety.md#otsejuhtimise-eeltingimused).

### E. Latentsus, katkestused ja 48 tunni seire

- **Eeldus ja alus (punktid 10–13).** Olemas on mõõtemetoodika,
  CSV-päised ja testitud logija. Mõõtmiseks on vaja toimivat tunnelit,
  võrreldavaid katsetingimusi ning kohapeal kinnitatud ohutut
  katkestuskäitumist.
- **Järgmine töö.** Mõõda 30 vajutust kohalikus võrgus ja 30 läbi tunneli
  ning võrdle kummagi seeria keskmist ja maksimumi. Mõõda mõlema kaamera
  viidet, kaadrisagedust ja ribalaiust. Pärast kohalikku ohutuskontrolli
  dokumenteeri kolm katkestuskatset koos taastumisega. Kogu dropletilt
  48 tunni logi ja arvuta vaadeldud katkestused ning andmekatvus.
- **Tõend ja failid.** Salvesta tingimused, ajabaas ja toortõendid koos
  mõõteridadega. Katkestuskatsete käitumine ja taastamine lähevad
  ohutuskokkuleppesse. Analüsaator töötab võrguühenduseta. Mõõteridade
  kogumine vajab laborit ning 48 tunni seire ka päris dropletit.
  [Metoodika](docs/measurements.md) · [Kohalik latentsus](data/latency_local.csv) ·
  [VPN-latentsus](data/latency_vpn.csv) · [Kaamerad](data/camera_vpn_metrics.csv) ·
  [Tunneli logi](data/tunnel_48h.csv) · [Katkestuskatsed](docs/safety.md#vpn-i-kadumine-liikumisel).

### F. Atomi klapi- ja UV-liides

- **Eeldus ja alus (punktid 14–15).** Olemas on C++ olekumudel,
  sündmuste puhver ja Atomi lehe plaan. Andmehõivega tuleb kokku leppida
  käsud, vahemikud ja elektriline liides. Tööriista katsed eeldavad
  kontrollitud sobivust ja nelja flantsinihet.
- **Järgmine töö.** Ühenda ja kontrolli laboris GPIO, relee, ISR ja
  LED-draiver. Lisa klapi impulsi ning UV kestuse ja ülempiiri seaded
  koos kohalike testinuppudega. Kinnita süstlaharu ohutu vooluta olek,
  UV sõltumatu blokeering ja automaatne kustumine ka ühenduse kadumisel.
  UV aktiveerimine on kohalik, 405 nm kaitseprillidega ja läbipaistmatu
  katte all.
- **Tõend ja failid.** Dokumenteeri Atomi lehel kinnitatud käsuleping ja
  katsete tulemused ning lisa viited püsivarale ja mõõtetõenditele.
  Mudeli hostitestid sobivad võrguühenduseta. Elektrilised,
  pneumaatilised ja UV kontrollid vajavad kohapealset riistvara.
  [Atomi lehe plaan](docs/atom_page.md) · [UV ja süstlaharu](docs/safety.md#uv-ja-süstlaharu) ·
  [Seotud kursused](#vajalikud-sisendid-varasematest-laboritest).

Punkti 17 jaoks kogu tööfailid ja päris töö kuupäevaga päevikukanded.
Esitamise tag kuulub lõplikule esitamisele.

## Kiirstart ilma riistvarata

Ava macOS-is või Linuxis terminal repo juurkaustas. Järgmised käsud
kasutavad Python 3 standardteeki. Testid kasutavad ajutisi faile ja
asendatud võrguvastuseid. Analüsaator avab CSV ainult lugemiseks.

```sh
cd smart-solutions/lab3
python3 -B -m unittest discover -s tests -v
python3 -B tools/tunnel_monitor.py analyze \
  --log data/tunnel_48h.csv --start 2026-01-01T00:00:00Z
```

Esimene käsk pärast kausta vahetamist käivitab 23 testi. Vaata näiteks,
kuidas test käsitleb kadunud marsruuti teadmata olekuna ja kuidas logija
väldib pärast taaskäivitust kordusmõõtmist. Teises käsus on algusaeg
näidis. Päisereaga mall annab `expected_checks: 17280`,
`recorded_checks: 0`, `missing_intervals: 17280` ja
`known_availability_percent: null`. Kättesaadavuse arvutamiseks
puuduvad vaatlused. [Testid](tests/test_tunnel_monitor.py) ·
[Analüüsi metoodika](docs/measurements.md#tunneli-48-tunni-logi).

Klapi ja UV osa saad näidata mudeli ja testide järgi.
PlatformIO hostitestide käsk ning projekti eeldused on Lab 2 juhendis.
[Hostitestide juhend](../lab2/firmware/README.md#ehitus-ja-hostitestid) ·
[Mudel](../lab2/firmware/src/core/actuator_model.cpp).

## Kaitsmise juhend

19.11.2026 kaitsmiseks valmista ette seitsmeminutiline ülevaade, mida
saab esitada ka ilma tunneli ja MG400-ta. Õppejõu 15-minutilise kaitsmise
kirjeldus sisaldab ka päriskatseid. Ava enne esitlust README,
ruutimisplaan ja terminal. [Ametlik kaitsmine](assignment-EST.md#kaitsmine).

| Aeg | Mida näidata ja öelda |
| --- | --- |
| 0:00–1:00 | Näita [arhitektuuri](#süsteemi-arhitektuur). Selgita, kuidas Atom küsib avalikust järjekorrast töid ja kuidas telefon kasutaks eraldi privaatset teed jaama lehele. |
| 1:00–2:00 | Ava [aadressiplaan](docs/network_plan.md) ja [teekonnad](docs/routing.md#teekondade-ennustus-ja-mõõtmine). Osuta LAN/WAN piirile ning selgita ühe kavandatud teekonna ennustust ja tulevast tõendit. |
| 2:00–3:00 | Ava [WireGuardi plaan](docs/wireguard/README.md). Näita telefoni, ruuteri ja dropleti rolle. Põhjenda minimaalseid lubatud teid ning postkontori eraldamist tunnelist. |
| 3:00–4:30 | Käivita [kiirstardi](#kiirstart-ilma-riistvarata) testid ja analüüs. Näita 23 testi kokkuvõtet, 17 280 oodatud intervalli, nulli logirida ja määramata kättesaadavust. |
| 4:30–5:30 | Ava [Atomi lehe plaan](docs/atom_page.md#tarkvaramudel-ja-integratsiooni-seis). Selgita ühe impulsi piirangut, UV kohalikku luba, alarmilukku ja puhvri rolli. Osuta [tarkvaratõenditele](#tõendid-ja-tulemused). |
| 5:30–6:30 | Ava [mõõtemetoodika](docs/measurements.md) ja [ohutuseeldused](docs/safety.md#otsejuhtimise-eeltingimused). Nimeta päris võrgu-, kaamera-, liikumis- ja väljundikatsed, mille tõendid on veel puudu. |
| 6:30–7:00 | Näita [kontrollnimekirja](#kontrollnimekiri) ja [päevikut](#arenduspäevik). Järjesta järgmised katsed [tööplaani](#tööplaan) järgi, alustades inventuurist ja kohalikest kontrollidest. |

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

Enne Atomi lehe ja riistvara ühendamist tuleb kooskõlastada klapi ja UV
LED-i käsud, vahemikud, riistvaraliides, ohutuskäitumine ning sündmuste
vorming. JSON-käsud on näited. Ühine C++ mudel ja testide ulatus on
kirjeldatud [Andmehõive püsivaraplaanis](https://github.com/Dennel04/data-acquisition-course/blob/b4b6a08aafc643e2345c66a2168da18e135640b3/data-acquisition/lab3/src/README.md#olemasolev-tarkvaramudel).
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

**07.11.2026: Step 1, klapi ja UV ohutusmudel**

* Tegime: lisasime Lab 2 PlatformIO projekti C++17 olekumudeli klapi, UV ja alarmiluku jaoks. Mudel nõuab enne väljundi lubamist ühekordset taimerit. UV käivitamiseks ja alarmiluku vabastamiseks on vaja uut kohalikku kinnitust.
* Kontroll: pärast operatsiooni-ID käsitluse täpsustamist läbisid 19 mudelitesti. In-place lähtestus säilitab viimase aktsepteeritud ID; uue käivituse pakettide eristamine jääb tulevase USB-adapteri ülesandeks.
* Järgmine samm: kinnitada GPIO-d, elektrilised tasemed ja sõltumatu UV-blokeering. Mudel ei juhi füüsilisi väljundeid. [Step 1 ja Step 2B commit](https://github.com/Dennel04/smart-solutions-course/commit/5fc4fbf76653ef1a0e92037cb38ebd10012faf00).

**07.11.2026: Step 2B, sündmuste edastuse simulatsioon**

* Tegime: lisasime sündmuste puhvri, mis säilitab lühikese komparaatorihäire ja edastab selle mudelile enne taimeri aegumise teadet. Kontrollime seansi- ja operatsiooni-ID-d, et eelmise käivituse või toimingu teade ei lõpetaks uut toimingut.
* Kontroll: läbisid 13 sündmuste testi ja kõik 104 native-testi. PlatformIO koosted `atoms3r_normal`, `atoms3r` ja `atoms3r_health` õnnestusid.
* Järgmine samm: lahendada sündmuste ohutu üleandmine katkestusrutiinist ja kontrollida väljundi füüsilist väljalülitust. Simulatsioon ei kasuta päris GPIO-d ega taimerikatkestusi.

**07.11.2026: Step 3A, WireGuardi logimise ettevalmistus**

* Tegime: lisasime 48 tunni tunneli logija ja võrguühenduseta analüüsi. Pärast ülevaatust lisasime WireGuardi liidese ja marsruudi kontrolli ning 48 tunni akna valideerimise. Logija salvestab alustatud kontrolli tähise enne päringut, et taaskäivitus ei kordaks sama kontrolli. Puuduv või teadmata tulemus ei lähe arvesse katkestusena.
* Kontroll: läbisid 23 Python-testi sünteetiliste andmete ja asendatud käsuvastustega. 17 280 on 10-sekundiliste kontrollivahemike kavandatud arv. Ametlik CSV jäi ainult päisega. [Step 3A commit](https://github.com/Dennel04/smart-solutions-course/commit/f13f2d8ba6df99e16f3ffaad3ff75376e6e3ad4b).
* Järgmine samm: kooskõlastada siht, liides ja mõõteaken enne päris seiret. Dropletil logijat ei käivitanud ning VPN-i ega riistvara ei katsetanud.

**07.11.2026, dokumentatsiooni sünkroonimine**

Codex võrdles lähtekoodi, teste, avaldatud commit'e ja Andmehõive Lab 3
kirjeldust. Codex täpsustas Atomi lehe plaanis, mõõtemetoodikas ja README-s
mudeli, sündmuste puhvri ja VPN-logija seisu ning testide ulatust.
Mõlema viidatud commiti autoriks on GitHubis märgitud `Nikikikl`.
Riistvara integreerimine ja päris VPN-seire on TODO.

### Väljundid ja tulemused

Tarkvaratulemused ja nende ulatus on [tõenditabelis](#tõendid-ja-tulemused).

**Väljundid**
* Andmehõive L3: TODO — kontrollitud klapi ja UV LED-i käsud, seaded, testid ning vajaduse korral alarmisündmus.
* 3D printimine L3: TODO — kaugelt nähtav ühendatud tööriist ja kontrollitud tööriistanihked.
* Nutikad Lahendused L4: TODO — kontrollitud võrk, tunnel ja droplet.

**KAARDISTA ISE, lõpus.**
* Git repo ja tag: TODO — tag luuakse alles esitamisel.
* Numbrid, mille see labor andis, ühikutega: TODO — päris mõõtmised.
* Mida me teeksime teisiti: TODO — täita pärast laborit.
* Mida järgmine labor peaks enne alustamist teadma: TODO — täita kontrollitud tulemuste põhjal.
