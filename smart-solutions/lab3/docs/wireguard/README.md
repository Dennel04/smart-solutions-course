# Lab 3 WireGuardi dokumentatsiooniplaan

Siin on tulevase seadistuse ja tõendite mall. Tunnelit pole selles
dokumentatsioonitöös paigaldatud, tulemüüri muudetud ega porte avatud.

## Tunneli lõpp-punkti valik

Põhivariant: labori ruuter algatab dropleti suunas väljamineva WireGuardi
ühenduse. Telefon on oma võtmepaariga eraldi peer.
Ruuteri mudel ja WireGuardi tugi: TODO — kontrollida päris ruuterilt.
Kui ruuter seda ei toeta, lubab õpetaja tunneli lõpetada Station PC-s.
Varuvarianti ei valita enne mudeli kontrolli; selle mõju teiste seadmete
kättesaadavusele tuleb eraldi põhjendada.

| Peer | Endpoint või selle leidmise viis | Tunneli aadress | Minimaalsed AllowedIPs / marsruudid | Põhjendus ja tõend |
|---|---|---|---|---|
| Droplet | TODO | TODO | TODO | TODO |
| Labori ruuter; vajadusel kinnitatud station'i variant | TODO | TODO | TODO | TODO |
| Telefon | TODO — kontrollida mobiilse peer'i endpoint'i käitumist | TODO | TODO | TODO |

## Ligipääs ja tulemüür

| Siht | Kas telefon vajab ligipääsu ja miks? | Minimaalne marsruut/AllowedIPs | Vajalik tulemüürireegel ja suund | Kontroll |
|---|---|---|---|---|
| Station'i leht | TODO | TODO | TODO | TODO |
| Lauakaamera station'is | TODO | TODO | TODO | TODO |
| Tööriistakaamera station'is | TODO | TODO | TODO | TODO |
| MG400 otse | TODO — jaama kaudu juhtimine ei eelda automaatselt otseligipääsu | TODO | TODO | TODO |
| AtomS3R | TODO — UV kaugaktiveerimine on keelatud | TODO | TODO | TODO |
| XIAO otse | TODO — station'i pilt ei eelda automaatselt otseligipääsu | TODO | TODO | TODO |

Iga lubatud alamvõrk põhjendatakse eraldi; üldist kogu võrgu luba ei eeldata.
AllowedIPs ei asenda teenuse autentimist ega tulemüüri.
Avalik postkontor jääb ainult kõrgtaseme HTTPS-tööde teenuseks.
Selle protsessi eraldamine tunneli juhtimisrajast ja videovoogudest: TODO.
Valitud port, endpoint, marsruudid ja tulemüür: TODO, tegelikke väärtusi siin
ette ei kirjutata. [Aadressiplaan](../network_plan.md).

## Tulevased kontrollid

| Kontroll | Meetod / ootus | Kuupäev, tulemus ja tõend |
|---|---|---|
| Telefoni positiivne katse | Mobiilne andmeside, Wi-Fi väljas, VPN sees; jaama leht avaneb | TODO |
| Telefoni negatiivne katse | Sama mobiilühendus, VPN väljas; station ja robot pole kättesaadavad | TODO |
| Välise piiri kontroll | Ainult tegelikult lubatud pordid vastavad; katse ulatus enne kokku leppida | TODO |
| Automaatne taastumine | Ruuteri reboot; tunnel taastub sekkumiseta | TODO |
| Taastumisaeg | Reboot'i ja kinnitatud ühenduse ajatemplid, vahe sekundites | TODO |
| Ühenduse hoidmine NAT-i taga | Valitud mehhanism ja põhjendus, katkestuse vaatlus | TODO |
| Katkine marsruut | Ennustus, tulemus ja taastamine [routing.md-s](../routing.md) | TODO |
| Liikumise katkestus | Ohutuskäitumine enne kaugliikumist; kolm füüsilist katset | TODO |

Liikumist sisaldav katse eeldab [ohutuskokkuleppe](../safety.md) täitmist,
ruumis olevat vastutajat ja hädastoppi. Tabel ei ole käivitamisluba.

## Saladusteta dokumentatsioon

Privaatseid WireGuardi/SSH-võtmeid, paroole, tokeneid ega toimivaid salajasi
konfiguratsioone ei panda reposse, tööriista väljundisse ega vestlusse.
Privaatvõti jääb selle loonud seadmesse. Jagatavad väljavõtted kontrollitakse
enne salvestamist ja avaldamist; saladustega QR-koode/ekraanipilte ei lisata.
Seadistusfailide saladusteta ülevaade ja draw.io skeem pildina koos elava
lingiga: TODO pärast päris seadistust. Kadunud telefoni ligipääs tühistatakse
samal päeval.
