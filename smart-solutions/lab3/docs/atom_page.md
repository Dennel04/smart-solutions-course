# Lab 3 olemasoleva Atomi lehe laienduse plaan

Kasutatakse olemasolevat AtomS3 seadete/testide lehte; uut lehte ei looda.
Klapi ja UV seaded ning testinupud Atomi lehel on TODO.

**TODO — lõplik käsuleping ja riistvaraliides tuleb Andmehõive Lab 3-ga kokku leppida.**

[Andmehõive avaldatud alus](https://github.com/Dennel04/data-acquisition-course/blob/74764e6dc8a83f868b90862edb48158d3619b595/data-acquisition/lab3/README.md)
sisaldab näidiskäske. Need ei kinnita meeskonna lõplikku käsulepingut,
GPIO-sid, releekontakte, vahemikke ega töötavat riistvara.

## Tarkvaramudel ja integratsiooni seis

[Step 1 ja Step 2B](https://github.com/Dennel04/smart-solutions-course/commit/5fc4fbf76653ef1a0e92037cb38ebd10012faf00)
lisavad Lab 2 püsivaraprojekti ühise C++17 olekumudeli klapi, UV ja
alarmiluku jaoks ning sündmuste puhvri. 19 mudelitesti ja 13 sündmuste
testi läksid läbi. [Andmehõive Lab 3 lähtekoodi kirjeldus](https://github.com/Dennel04/data-acquisition-course/blob/b4b6a08aafc643e2345c66a2168da18e135640b3/data-acquisition/lab3/src/README.md#olemasolev-tarkvaramudel)
viitab samale mudelile ja testidele.

Atomi kasutajaliidese käsud `dispense`, `uv` ja `clear` on TODO. Töötavat
Lab 3 püsivara pole kinnitatud. GPIO, relee, katkestusrutiini (ISR) ja
LED-draiveri ühendamine ning automaatse riistvaralise väljalülituse kontroll
on TODO. Mudelitestid katavad loogilisi väljundeid. Klapi vooluta olek,
sõltumatu füüsiline UV-blokeering ja UV ohutu kohalik käivitus tuleb päris
seadmel kinnitada.

## Klapp

Pump hargneb Y-liitmikust otse napale ja läbi 3/2 klapi süstlasse.
Klapp ei lülita pumpa napa ja süstla vahel. Voolu all ühendatakse pump
süstlaga; vooluta lahutatakse pump ning süstal ühendatakse atmosfääriga.
Päris ohutu oleku mõõtmine: TODO.

| Väli või tegevus | Nõue | Kokkulepe / katsetõend |
|---|---|---|
| Impulsi pikkus | Millisekundites | TODO |
| Vahemiku kontroll | Lubatud miinimum/maksimum enne käsu saatmist ja Atomis | TODO — määrata kontrollitud liidese põhjal |
| Testinupp | Üks testimpulss; korduse ja alarmi käsitlus kokku leppida | TODO |
| Ajastus ja ohutu olek | Andmehõive riistvarataimer ning vooluta süstal atmosfääri | TODO |
| Käsud ja alarmid | Kooskõlastatud valideeritud leping | TODO |

## UV LED

| Väli või tegevus | Nõue | Kokkulepe / katsetõend |
|---|---|---|
| Põlemise kestus | Millisekundites | TODO |
| Ülempiir | Kontrollitud maksimaalne kestus, kontroll ka Atomis | TODO |
| Kohalik testinupp | Ainult ruumis olevale inimesele; kaugaktiveerimine keelatud ka VPN-ist | TODO — kohaliku lubamise ja ligipääsu tõke |
| Automaatne väljalülitus | Aega loeb Atomi taimer, mitte brauseri JavaScript | TODO |
| Ühenduse kadu | LED kustub Atomi taimeriga ka brauseri sulgemise või ühenduse kadumisel | TODO |
| Ohutus | 405 nm kaitseprillid, lamp laua poole, läbipaistmatu must kaitsekate; valgus ei pääse välja | TODO — kohalik kontroll |

Võrguasukohta või VPN-i kuulumist ei loeta kohaloleku tõendiks.
Kohaliku lubamise mehhanism kooskõlastatakse enne Atomi juhtliidese teostamist;
seni UV kasutamist ei lubata.

## Tulevase kontrolli väljad

- Käsulepingu versioon, kooskõlastajad ja kuupäev: TODO
- Klapi üks impulss ning sisendi piiride kontroll: TODO
- Voolukatkestusel süstla atmosfääri tühjenemise tõend: TODO
- UV ülempiir, kaugaktiveerimise keeld ning automaatne kustumine: TODO
- Brauseri sulgemise / ühenduse kadumise katse kuupäev, meetod ja tulemus: TODO
- Mõlema testi kohaliku ohutuse tõendid: TODO
