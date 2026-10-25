# Lab 3 kaugjuhtimise ohutuskokkuleppe mustand

See laiendab [Lab 2 ohutuskokkulepet](../../lab2/docs/safety.md).
Kinnitusi ega katsetulemusi ei eeldata. Iga liige kinnitab ise pärast lugemist.

## Otsejuhtimise eeltingimused

- VPN-i otsejuhtimist kasutab ainult isiklikult volitatud inimene pärast
  ruumis oleva vastutaja selgesõnalist nõusolekut. Volitatud isikud: TODO.
- Ruumis on inimene, kes näeb kogu tööala ning ulatub roboti aluse füüsilise
  hädastopini. Tema kontrollib tööala ja lubab roboti lokaalselt;
  kaugelt enable-funktsiooni ei lisata.
- Tühjas ruumis on robot voolust välja lülitatud, mitte ainult disabled.
- Laua üldvaatekaamera peab töötama ning näitama kogu tööala ja robotit.
  Tööriistakaamera üksi ei piisa. Pildi puudumisel kaugkäske ei anta.
- Füüsiline hädastopp on ainus usaldatud stop. Veebinupp, tarkvaraline Stop
  ega VPN-i katkestamine ei ole selle ekvivalent.
- MG400 käske saadab korraga ainult üks juhtimisprotsess.
- Uue jada esimene katse tehakse lokaalselt 20% kiirusel, tööriist vähemalt
  20 mm pinnast kõrgemal ja ilma proovitükita. Kehtivad Lab 1 piirid:
  käed väljaspool 440 mm tööala, enne liikumist öeldakse „liigub“.
- 24 V pumbakasti DO-juhtmeid ühendatakse ainult keelatud roboti ja
  vooluta kastiga; Atomi vaikimisi Wi-Fi parool vahetatakse.

## Postkontor ja VPN

Avalik HTTPS-postkontor võtab vastu ainult autentitud whitelist'i
kõrgtaseme töid. Vigane, tundmatu või aegunud töö ei liiguta robotit;
kogu sisend valideeritakse. Avalikku teenusesse ei lisata koordinaate,
trajektoore, DO-käske, otseseid MG400 käske ega kaameraproxy't.

Lab 2 nõue tervikliku lokaalselt vastuvõetud töö lõpetamisele interneti
kadumisel ei määra VPN-i otsejuhtimise katkestuskäitumist: otsejuhtimisel
võib järgmine käsk alles teel olla. Need tuleb eraldi kontrollida.
Lab 3 privaatne tunnel on omaette juurdepääsutee. Dropleti avalikul
postkontoriprotsessil ei tohi olla võimalust saata tunnelisse juhtimiskäske;
isolatsioon ja tulemüür: TODO enne tunneli kasutamist.

Station'i kaameraserver on praegu eraldi loopback-teenus ilma autentimiseta.
Kaitstud LAN/VPN-ligipääsu otsus on TODO; avalikku kaameraportide
edasisuunamist ega postkontori videovahendust ei kasutata.

## VPN-i kadumine liikumisel

Enne esimest päris kaugliikumist tuleb ohutu käitumine kavandada, teostada
ning kontrollida kohaliku vastutaja ja füüsilise hädastopiga. Ühenduse
taastumine ei anna automaatselt luba liikumist jätkata.

- Kaotuse tuvastamise mehhanism ja ajapiir: TODO — põhjendada ja kontrollida
- Oodatud roboti, pumba, klapi ja UV olek: TODO
- Rakendus ja lokaalse kontrolli tõendid enne kaugliikumist: TODO
- Kaugelt puuduv Stop ning kohaliku vastutaja tegevus: TODO
- Taastamise kontroll ja uue kohaliku loa kord: TODO

| Katse | Kuupäev ja kohalik vastutaja | Katkestamise hetk/meetod | Oodatud käitumine | Tegelik käitumine ja tõend | Taastamine |
|---|---|---|---|---|---|
| 1 | TODO | TODO | TODO | TODO | TODO |
| 2 | TODO | TODO | TODO | TODO | TODO |
| 3 | TODO | TODO | TODO | TODO | TODO |

Need on tühjad katseväljad, mitte tehtud katsed.

## MG400 füüsiline kaitsemehhanism

Õppejõu kirjeldatud kaldseinaga aluse kaitsemehhanismi rakendumisel
ei proovita robotit kaugelt uuesti käivitada. Ruumis olev inimene kontrollib
põhjust ja taastab roboti asendi aluses; enne jätkamist uus ohutuskontroll
ning kohalik luba. Märk, mille järgi leht või kaamera rakendumist näitab:
TODO — kinnitada kohapeal, mitte oletada tarkvaralist tuvastust.

## UV ja süstlaharu

- UV LED-i ei aktiveerita kaugelt, ka mitte VPN-i kaudu. Kohalik testnupp
  eeldab ruumis olevat inimest, 405 nm kaitseprille, nähtavat lambi suunda
  ja läbipaistmatut musta kaitsekatet, mille alt valgus välja ei paista.
- Lamp suunatakse laua poole; LED-i ei vaadata ning kätt/nahka katte alla ei
  panda. 405 nm näiv tuhmus ei tõenda ohutust.
- LED kustub alati Atomi taimeriga, ka brauseri sulgemise ja võrgu kadumisel.
  Ülempiir ning kohaliku aktiveerimise tõke: TODO enne kasutamist.
- Klapp juhib ainult süstlaharu. Vooluta on pump lahutatud ja süstal
  atmosfääriga ühendatud; see olek tuleb päriselt mõõta.
- Enne süstla eemaldamist vabastatakse rõhk ja kinnitatakse see kohapeal.
  Järgitakse Andmehõive ja 3D printimise kehtivaid füüsilisi ohutusnõudeid.

## Võtmed ja ligipääs

- WireGuardi/SSH privaatvõtmed, paroolid ja tokenid ei lähe reposse,
  Codexi väljundisse ega vestlusse; privaatvõti jääb selle loonud seadmesse.
- Kadunud telefoni peer'i ligipääs tühistatakse dropletil samal päeval.
- Avalik HTTPS-autentimine ja VPN-i minimaalsed marsruudid/lubatud
  alamvõrgud on eraldi piirid; iga tulemüürireegli eesmärk dokumenteeritakse.
- Jagatavad seadistusdokumendid ei sisalda saladusi.

## Meeskonna kinnitused

| Nimi | Kuupäev | Kinnitus |
|---|---|---|
| Nikita | TODO | TODO — kinnitab isiklikult pärast läbilugemist |
| Denys | TODO | TODO — kinnitab isiklikult pärast läbilugemist |
| Raimo | TODO | TODO — kinnitab isiklikult pärast läbilugemist |
