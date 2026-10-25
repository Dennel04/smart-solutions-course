# Lab 3 olemasoleva Atomi lehe laienduse plaan

Kasutatakse olemasolevat AtomS3 seadete/testide lehte; uut lehte ei looda.
Selles etapis ei muudeta käske ega püsivara.

**TODO — käsud ja riistvaraliides tuleb enne teostust Andmehõive Lab 3-ga kokku leppida.**

[Andmehõive avaldatud alus](https://github.com/Dennel04/data-acquisition-course/blob/74764e6dc8a83f868b90862edb48158d3619b595/data-acquisition/lab3/README.md)
sisaldab näidiskäske. Need ei kinnita meeskonna lõplikku käsulepingut,
GPIO-sid, releekontakte, vahemikke ega töötavat riistvara.

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
Kohaliku lubamise mehhanism kooskõlastatakse enne koodi kirjutamist;
seni UV kasutamist ei lubata.

## Tulevase kontrolli väljad

- Käsulepingu versioon, kooskõlastajad ja kuupäev: TODO
- Klapi üks impulss ning sisendi piiride kontroll: TODO
- Voolukatkestusel süstla atmosfääri tühjenemise tõend: TODO
- UV ülempiir, kaugaktiveerimise keeld ning automaatne kustumine: TODO
- Brauseri sulgemise / ühenduse kadumise katse kuupäev, meetod ja tulemus: TODO
- Mõlema testi kohaliku ohutuse tõendid: TODO
