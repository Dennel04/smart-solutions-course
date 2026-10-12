## Nutikad Lahendused: Labor 3 — Ruuter ja VPN

**Töömaht:** 30 tundi | **Hindamine:** 20 punkti | **Meeskond:** 3 tudengit | **Välja antud:** 28.10.26 | **Tellimise kuupäev:** 06.11.26 | **Esimene kaitsmine:** 17.11.26, veebis

### Kuidas see dokument töötab

* Repo ja töökord on Laborist 1 olemas ja samad.
* Too sellest dokumendist oma projekti repo juurde see, mida vaja: selle labori kaust, `README.md`, kuhu lähevad su enda numbrid, otsused ja KAARDISTA ISE vastused, ja failid, mida kontrollnimekiri nimetab. Tervet dokumenti üle kopeerida ei ole vaja.
* Skeemid ja simulatsioonid lähevad dokumenti pildina, pildi juurde link elavale failile, et teine saaks selle lahti teha ja edasi muuta.

### Eesmärk

Laboris 2 käis kaugjuhtimine läbi postkontori: kasutaja jättis sõnumi, roboti Atom tuli ja küsis, robot tegi töö ära. See on aeglane ja pime. Sõnum ootab järgmist postilkäiku, tellida saab ainult terve töö nimekirjast, ja kasutaja ei näe, mis laual toimub. Nüüd tuleb otsetee.

Teid on kaks ja nad jäävad lahku:

* **Postkontor** on avalik veebileht Laborist 2. Sealt saab jätta sõnumi ja vaadata vastust. Otse sealt robotit ei liigutata, ja kaamerapilti seal ei ole.
* **Otsetee** on VPN. Kes on tunnelis, on justkui labori võrgus: näeb jaama lehte ja kaameraid ja liigutab robotit kohe, mitte järgmise postilkäiguga. Kes ei ole tunnelis, ei näe midagi — isegi mitte seda, et seal midagi on.

Selleks on vaja kahte asja, mida seni ei olnud.

**Ruuter.** Seni oli su sülearvuti käsitsi pandud aadressiga otse roboti küljes ja Atom labori WiFi-s. See töötas, sest seadmeid oli kaks. Nüüd on neid viis — robot, jaam, Atom, kaameramoodul, telefon — ja nad peavad olema ühes võrgus, mille plaan on sinu oma. Ruuter on seade, kus alamvõrk, aadresside jagamine, NAT, tulemüür ja ruutimistabel päriselt elavad. Neid mõisteid ei saa õppida ära lugedes; neid saab õppida ühe karbi peal, mille sa ise valesti seadistad ja siis korda teed.

**VPN.** Tunnel sinu ruuteri ja dropleti vahel. Asümmeetria on sama, mis Laboris 2: labori võrku sisse ei saa, välja saab. Seega võtab ruuter ise dropletiga ühendust ja hoiab tunnelit üleval. Telefon on tunneli teine osaline. Droplet on ainus aadress, mida mõlemad teavad.

Ja kui robot on kaugelt kättesaadav, muutub ohutus teistsuguseks, kui ta seni oli. Seni oli robot ruumis, kus sa ise olid. Nüüd ta enam ei ole.

Labori 1 lubadus kehtib edasi. Andmehõive Labor 3 paneb Atomi külge solenoidklapi ja UV LED-i. Mõlemad saavad Atomi lehele oma seaded ja testinupu.

Selles laboris on viis asja:

1. **Ruuter.** Aadressiplaan paberil, siis karbis. Robot, jaam, Atom ja kaameramoodul ühes võrgus.
2. **Ruutimistabel ja NAT.** Kuhu pakett päriselt läheb. Ennusta enne, kui mõõdad.
3. **VPN.** Tunnel ruuterist dropletini, telefon tunnelis. Jaama leht avaneb mobiilse andmesidega.
4. **Kaugelt.** Latentsus, kaamerad läbi tunneli, ja mis juhtub, kui ühendus katkeb keset liigutust.
5. **Atomi leht.** Klapp ja UV LED saavad seaded ja testinupu.

Esimesel päeval uusi osi ei ole. Ehita sellest, mis riiulil on, ja kirjuta puuduv tellimuseks, mis läheb välja 06.11.

*See on elav dokument. Uuenda eesmärke, kui need töö käigus muutuvad — uued teadmised teevad vanad eesmärgid vahel mõttetuks. Mõte on hoida meeskond kogu aeg sihil, et ei eksitaks detailide metsa ja põhiprobleem ei jääks lahendamata.*

**KAARDISTA ISE — eesmärk nii, nagu ta tegelikult välja tuli.**

### Kontrollnimekiri

**Peab olema tehtud**

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

### Sisendid

* Laborist 1: jaam, MG400 baaspakett, aadressiplaan, Atomi leht.
* Laborist 2: droplet ja domeen, postkontor ja Atomi postilkäimine, lubatud tööde nimekiri, ohutuskokkulepe, kaks kaamerat jaama lehel, kaamerate ja juhtimise latentsuse numbrid labori võrgus.
* Õppejõult: ruuter meeskonna kohta ja selle admin-ligipääs; labori võrgu pistik, kuhu ruuter käib.
* Andmehõive L3-st: solenoidklapp ja UV LED Atomi küljes, koos käskudega, millega neid juhitakse.
* 3D printimise L3-st: tööriist, mille küljes on napp, süstal ja UV-lamp, ja tööriista nihked iga otsiku kohta.

### Vahendid

1. Labori 1 ja 2 jaam, Atom, kaamerad
2. Ruuter õppejõult, LAN kaablid
3. Droplet Laborist 2
4. WireGuard: dropletis, ruuteris ja telefonis
5. Telefon mobiilse andmesidega
6. Käsurea tööriistad: `ping`, `traceroute`, ruutimistabeli vaatamine oma operatsioonisüsteemis
7. Python 3, Flask; git; draw.io

*Kui plaan muutub, uuenda ka vahendeid, või tee draw.io skeem, mis näitab, kuidas asjad omavahel töötavad.*

**KAARDISTA ISE — mida sa päriselt kasutasid.**

### Taustainfo

* **Mis on VPN**
  [https://www.youtube.com/watch?v=15amNny_kKI&t=230s](https://www.youtube.com/watch?v=15amNny_kKI&t=230s)
* **WireGuard** — tunnel kahe masina vahele, väike ja kiire
  [https://www.wireguard.com/quickstart/](https://www.wireguard.com/quickstart/)
* **Kuidas droplet turvaliselt seadistada**
  [https://www.youtube.com/watch?v=L8e_eAm4fFM](https://www.youtube.com/watch?v=L8e_eAm4fFM)
* **Alamvõrk ja mask**
  (link puudu — YouTube: "subnet mask explained")
* **NAT**
  (link puudu — YouTube: "NAT explained network address translation")
* **Ruutimistabel**
  (link puudu — YouTube: "routing table explained default gateway")
* **WireGuard ruuteris**
  (link puudu — sõltub ruuteri mudelist)
* **VPN konsultatsioon** — WireGuard samm-sammult, võtmepaari loogika, töö NAT-i taga, tunneli kontroll. Aeg lepitakse meeskondadega jooksvalt kokku. Tule sinna oma aadressiplaaniga.
  [Ainepassi kontakttunnid](../../Smart%20Solutions/SVNC.00.321_SO%20EST%20v2.md#kontakttundide-ajakava)

*Lisa siia oma allikaid ja kasulikku infot, mis aitaks sul projektist aru saada ka aastaid hiljem, kui selle uuesti lahti teed.*

**KAARDISTA ISE — sinu allikad.**

### Osad

#### 1. Ruuter

Plaan tuleb enne karpi. Joonista paberile kõik, millel on aadress: robot, jaam, Atom, kaameramoodul, telefon, ruuter ise, ja labori võrk ruuteri taga. Iga seadme juurde aadress, mask, ja kes selle aadressi andis — kas keegi trükkis selle käsitsi sisse või jagas ruuter.

Üks asi on plaanis juba ees: robotil on aadress 192.168.1.6 ja see on tal sees. Kas ehitad oma võrgu selle ümber või muudad roboti aadressi, on sinu otsus. Mõlemal on hind; kirjuta üles, kumma sa maksid.

Siis seadista ruuter plaani järgi.

* **Seadmed saavad iga kord sama aadressi.** Atom ja kaameramoodul küsivad aadressi ruuterilt. Kui ruuter annab neile homme teise, on su jaama seaded valed. Ruuter oskab aadressi seadme külge kinni panna.
* **Ruuteril on kaks poolt.** Üks vaatab sinu võrku, teine labori võrku. Sinu seadmed on nüüd kahe ruuteri taga: sinu oma ja labori oma. Pane see joonisele.
* **Tulemüür.** Mis tohib väljast sisse tulla? Vaikimisi mitte midagi, ja nii see jääb.
* **Admin-parool.** Ruuter, mille parool on kleebisel põhja all, ei ole sinu ruuter.

Siis kontrolli, et midagi ei läinud katki. Jaam liigutab robotit. Atom käib Labori 2 postkontoris ja sõnum paneb roboti tööle. Mõlemad kaamerad on jaama lehel. Kui miski neist enam ei tööta, on põhjus peaaegu alati aadress, mis oli kuskil käsitsi sisse kirjutatud.

Kirjuta üles: aadressiplaan tabelina ja draw.io joonisena; kumba teed sa roboti aadressiga läksid ja miks; ruuteri seadistus ekraanipiltide või eksporditud failina; mis läks võrgu vahetamisel katki ja mis selle parandas.

#### 2. Ruutimistabel ja NAT

Igal masinal, millel on rohkem kui üks tee välja, on tabel, mis ütleb, milline pakett kuhu läheb. Su jaamal on see tabel olemas ja ruuteril ka. Tee mõlemad lahti ja kirjuta iga rea kõrvale üks lause oma sõnadega: millised aadressid, mis liidese kaudu, kelle kätte.

Siis kolm teekonda. **Kirjuta ennustus enne, kui käsu käivitad:** mitu hüpet ja läbi kelle.

* jaamast robotini,
* jaamast dropletini,
* jaamast mõne aadressini internetis.

Käivita ja võrdle. Seal, kus ennustus ja tulemus lahku läksid, on koht, kus sa võrgust valesti aru said. See on selle osa kõige kasulikum rida.

Siis NAT. Logi dropletis, mis aadressi pealt Atomi kõne tuleb. See ei ole Atomi aadress ega su ruuteri aadress sinu võrgus. Kelle aadress see on, ja mitu korda vahetati aadressi teel sinna? Ja miks tuleb vastus ikka õigesse kohta tagasi?

Kirjuta üles failis `docs/routing.md`: jaama ja ruuteri tabel, iga rea kohta üks lause; kolm teekonda, ennustus ja tulemus kõrvuti; aadress, mida droplet näeb, ja seletus, kust see tuli.

#### 3. VPN

Tunnelil on kaks otsa ja kummalgi on võtmepaar. Privaatne võti ei lahku kunagi seadmest, kus ta tehti: ei meili, ei vestlusse, ei reposse. Teisele poolele antakse avalik võti. Sellest piisab, et kumbki pool teaks, kellega ta räägib.

Droplet on kindel punkt: tal on avalik aadress ja tema kuulab. Ruuter võtab ise ühendust ja hoiab tunnelit üleval, ka siis, kui parajasti midagi ei saadeta — muidu unustab labori ruuter, et selline ühendus oli, ja sisse ei pääse enam keegi. Telefon on kolmas osaline, oma võtmepaariga.

Kõige tähtsam seadistus on see, **millised aadressid kumbki pool tunnelisse saadab ja tunnelist vastu võtab.** See on korraga marsruut ja luba. Liiga kitsas, ja pakett ei leia teed. Liiga lai, ja sa lasid dropleti kaudu oma võrku rohkem, kui tahtsid. Otsusta teadlikult: kas telefon peab pääsema jaamani? Robotini otse? Atomini? Iga "jah" kohta põhjus.

Kui su ruuter WireGuardi ei oska, lõpeb tunnel jaamas. Kirjuta üles, kummas ta lõpeb ja mida see muudab: kui tunnel on jaamas, siis kes veel peale jaama on kaugelt kättesaadav?

Kaks testi, mida ei saa võltsida.

* **Seest.** Võta telefon, **lülita WiFi välja**, lülita tunnel sisse, ava jaama leht. Kui leht tuleb ja nupud liigutavad robotit, on tunnel olemas. Ruumis on sel ajal inimene, kelle käsi on hädastopi juures.
* **Väljast.** Lülita tunnel välja ja proovi sama. Midagi ei tohi avaneda. Proovi ka dropleti aadressi peal neid porte, mida sa ei ole lahti teinud.

Siis taaskäivita ruuter ja ära puutu midagi. Tunnel peab ise tagasi tulema. Mõõda, kui kaua see võtab.

Ja lõpuks tee üks marsruut meelega katki. Kirjuta enne üles, mis kolmest asjast — robot, droplet, internet — lakkab töötamast. Siis vaata, kas sul oli õigus.

Kirjuta üles: tunneli skeem draw.io-s, igal otsal aadress; kus tunnel lõpeb ja miks; millised aadressid tunnelisse lähevad ja iga kohta põhjus; ekraanipilt telefonist, kus on näha, et WiFi on väljas; mida väljast proovisid ja mis vastas; aeg taaskäivitusest tunnelini; katki tehtud marsruut, ennustus ja tulemus. Seadistusfailid lähevad reposse ilma võtmeteta.

#### 4. Kaugelt

Nüüd, kui tee on olemas, mõõda, mida see maksab.

30 nupuvajutust labori võrgus ja 30 läbi tunneli. Iga vajutuse kohta aeg vajutusest liigutuseni. Keskmine ja maksimum mõlemas. Vahe ei ole ainult number: ta ütleb sulle, kas kaugjuhtimine on selle süsteemi jaoks üldse mõistlik või ainult vaatamiseks.

Siis kaamerad. Labori 2 numbrid on sul labori võrgus mõõdetud. Mõõda samad kolm asja — viide, kaadreid sekundis, ribalaius — läbi tunneli, mobiilse andmesidega. Kaamerad ja juhtimine käivad nüüd ühe ja sama kitsa toru kaudu. Kui juhtimine jäi kaamerate pärast aeglaseks, on sul samad valikud, mis Laboris 2, ainult et nüüd on nad päris: väiksem pilt, vähem kaadreid, üks kaamera korraga.

Ja siis kõige tähtsam osa selles laboris. **Ühendus katkeb keset liigutust.** See juhtub, ja mitte harva — mobiilne andmeside kaob, tunnel jookseb kokku, droplet käib ümber. Laboris 1 on sul see reegel väiksemalt juba olemas: kui rida ei tule 500 ms jooksul, pump seisab. Nüüd on sama küsimus roboti kohta, ja vastus ei ole sama, mis Laboris 2. Postkontori kaudu tellitud töö tehti lõpuni, sest robotil oli kõik käes. Otsejuhtimisel ei ole: järgmine käsk on alles teel, ja inimene, kes pidi "stopp" vajutama, ei saa seda enam teha.

Otsusta, mis juhtub. Tee see ära. Ja lülita siis telefonis tunnel välja keset liigutust, et näha, kas see päriselt nii läks. Kolm korda, sest esimene kord võib vedada.

Tunnel peab püsima ka siis, kui keegi ei vaata. Droplet on ainus masin, mis on alati üleval, seega logib tema: iga 10 sekundi tagant üks ping läbi tunneli, 48 tundi järjest. Loe üle, mitu korda tunnel katkes, kui kauaks, ja kas sa tead, miks.

Kirjuta üles: latentsuse tabel, labor ja tunnel, keskmine ja maksimum; kaamerate numbrid Labori 2 omade kõrval; mis juhtub ühenduse katkemisel ja mis päriselt juhtus kolmel korral; `data/tunnel_48h.csv`, kättesaadavus protsentides ja pikim katkestus sekundites.

#### 5. Atomi leht

Andmehõive Labor 3 paneb Atomi külge solenoidklapi, mis valib, kas pump töötab napaga või süstlaga, ja UV LED-i, mis liimi kõvendab. Labori 1 reegel: mõlemad saavad seaded ja testinupu Atomi lehele. Uut lehte ei tehta.

* **Klapp:** impulsi pikkus millisekundites ja testinupp, mis teeb ühe impulsi.
* **UV LED:** põlemise aeg ja selle ülempiir, ja testinupp.

Lepi Andmehõive poolega kokku, mis käsud need on, enne kui kumbki pool koodi kirjutab. Ja üks asi ei ole läbiräägitav: **LED kustub ise.** Ta ei jää põlema sellepärast, et leht pandi kinni, telefon kaotas ühenduse või keegi unustas. Aja loeb Atom, mitte brauser.

Kirjuta üles: Atomi lehe seadete ja testide nimekiri failis `docs/atom_page.md`; mis juhtub LED-iga, kui ühendus lehega kaob keset põlemist, ja kuidas sa seda proovisid.

**KAARDISTA ISE — vastused.** Iga osa kohta: numbrid, ühikud, kus fail on. Tegemata asja kohta üks rida, miks.

### Ohutus

* **Robot, mille juurde saab internetist, saab liikuma panna keegi, keda ruumis ei ole.** Enne, kui tunnel esimest korda püsti läheb, võtate Labori 2 ohutuskokkuleppe lahti ja kirjutate juurde: kes tohib tunneli kaudu otse juhtida, ja mida ta peab enne seda tegema. Otsetee lubab rohkem kui postkontor — iga liigutust, mitte ainult tööd nimekirjast.
* **Hädastopp on roboti alusel.** Kodus seda nuppu ei ole. Seega: kaugelt ei jooksutata midagi, mille ajal ruumis ei ole inimest, kes hädastoppi ulatub. Kui ruumis ei ole kedagi, on robot välja lülitatud, mitte ainult keelatud.
* **Kaamera ei ole mugavus, vaid ohutusvahend.** Kui laua kaamera pilti ei tule, ei käsutata. Tööriista kaamera üksi ei loe: ta ei näe, kuhu käsi liigub.
* Üks ohutusseade selles ruumis töötab ka siis, kui kedagi kohal ei ole, ja tasub teada, milline. MG400 seisab kaldseinaga aluses: kui robot millegi vastu läheb, ronib ta alusest välja ja jääb seisma. Tarkvara seda ei tee ja internet seda ei takista. Aga tagasi alusesse paneb ta ainult inimene — ehk kaugelt sa pärast seda enam midagi käima ei pane. Kirjuta üles, kuidas sa kaugelt aru saad, et see juhtus: mille pealt sa seda lehel või kaameras näed.
* **Tunneli võti on ruumi võti.** Privaatne võti ei lähe reposse ega vestlusse. Kui telefon kaob, võetakse tema võti dropletist maha samal päeval.
* **Ühenduse katkemine keset liigutust on läbi mängitud enne, kui robot kaugelt esimest korda liigub.** Mitte pärast.
* **UV LED-i ei lülitata kaugelt.** 405 nm valgus ja silmad: testinuppu vajutab inimene, kes on ruumis, kellel on kaitseprillid ees ja kes näeb, kuhu lamp on suunatud. LED kustub alati ise.
* Postkontor ja tunnel jäävad lahku. Avalik server ei saa tunnelisse midagi saata.
* MG400 reeglid Laborist 1 kehtivad edasi: käed ei ole laual, kui robot on sisse lülitatud; uue jada esimene jooks 20 % kiirusel; käsklusi saadab robotile korraga ainult üks programm.

### Komponendid selle labori jaoks

Ruuteri annab õppejõud ja droplet on Laborist 2 olemas. Neid sa oma tellimusse ei pane.

Sinu tellimusse läheb see, mis võrgu juures puudu on. Tellimus läheb välja 06.11.26, faili `docs/bom.md`, iga rea juures üks lause, milline osa seda küsib.

Tellimine käib ühisest tellimistabelist: [https://moodle.ut.ee/mod/url/view.php?id=1535601](https://moodle.ut.ee/mod/url/view.php?id=1535601). Kanna oma read sinna enne tellimise kuupäeva; mida tabelis ei ole, seda ei tellita. Fail `docs/bom.md` jääb sinu reposse põhjenduseks, miks sa just neid asju küsisid.

Mõtle näiteks: kas LAN kaableid on nii palju ja nii pikki, kui su plaan tahab; kas jaamal on vaba Etherneti port või adapter; kas ruuteri WiFi ulatub Atomini ja kaameramoodulini, kui nad on käe otsas; ja kas telefonis on piisavalt mobiilset andmesidet, et kaameraid läbi tunneli mõõta.

### Hindamiskriteeriumid

| Kategooria | Punktid |
| :--- | :--- |
| Tööfailid — ruuteri seadistus, tunneli seadistus mõlemas otsas ilma võtmeteta, jaama kood, Atomi lehe uued osad | 5 p |
| Analüüs — ruutimistabelid seletatud, kolm teekonda ennustuse ja tulemusega, NAT, latentsus laboris ja läbi tunneli, kaamerad läbi tunneli, 48 tunni logi | 5 p |
| Prototüüp — jaama leht avaneb telefonist mobiilse andmesidega ainult läbi tunneli ja liigutab robotit, tunnel tuleb pärast taaskäivitust ise tagasi, katkenud ühendus viib roboti ohutusse olekusse, klapp ja LED on Atomi lehel | 5 p |
| Dokumentatsioon — README, arenduspäevik, aadressiplaan, `routing.md`, ohutuskokkulepe, `atom_page.md`, `bom.md`, AGENTS.md | 5 p |
| **Kokku** | **20 p** |

### Kaitsmine

Link git repole, tag `smart-solutions-lab3`.

Kaitsmine on lihtne suuline 15 minuti jutuajamine. Avad oma telefonist mobiilse andmesidega läbi tunneli jaama lehe, liigutad robotit ja näed seda mõlemas kaameras. Lülitad tunneli välja ja näitad, et leht enam ei avane ja mis robotiga juhtus. Näitad oma ruutimistabelit ja ütled ühe rea kohta, mida see teeb. Avad oma arenduspäeviku. Õppejõud küsib umbes viis küsimust selle kohta, kuidas sa selle tegid. Kui esimesel korral ei õnnestu, tuled uuesti.

Repos on kaustas `smart-solutions/lab3/`:

* `src/` jaama kood
* `firmware/` Atomi PlatformIO projekt uuendatud lehega
* `data/tunnel_48h.csv`, latentsuse CSV-d
* `docs/`: aadressiplaan ja võrgu skeem draw.io-s, ruuteri seadistus, tunneli seadistus ilma võtmeteta, `routing.md`, ohutuskokkulepe, `atom_page.md`, ekraanipildid, `bom.md`
* `README.md` selle labori kohta
* `AGENTS.md` uuendatud

### Arenduspäevik

**KAARDISTA ISE — päevik.** Üks sissekanne iga töösessiooni kohta, kirjutatud iseendale, nii et inimene, kes seal ei olnud, saab aru. Sissekandeid lisatakse, mitte ei muudeta.

**PP.KK.AA — kes olid kohal**
* Tegime:
* Juhtus (numbrid):
* Otsustasime, ja miks:
* Lahti järgmiseks korraks:

### Väljundid ja tulemused

**Väljundid**
* Andmehõive L3: Atomi leht, kust klappi ja LED-i saab seadistada ja proovida.
* 3D printimine L3: kaugelt nähtav pilt sellest, mida tööriist teeb.
* Nutikad Lahendused L4: võrk, tunnel ja droplet, mille peale tuleb ühine andmebaas.

**KAARDISTA ISE, lõpus.**
* Git repo ja tag:
* Numbrid, mille see labor andis, ühikutega:
* Mida me teeksime teisiti:
* Mida järgmine labor peaks enne alustamist teadma:

### Tagasiside
