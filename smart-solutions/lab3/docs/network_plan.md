# Lab 3 võrguaadresside plaan

Ettevalmistusmall: meeskond täidab plaani enne seadistamist ning kinnitab
tegelikud väärtused päris seadmete ja kuupäevaga tõendite järgi.

| Seade või liides | Roll | IP-aadress | Mask / alamvõrk | Lüüs vajaduse korral | Aadressi määramine | Kinnituse allikas ja kuupäev |
|---|---|---|---|---|---|---|
| Ruuteri LAN | Kohaliku võrgu lüüs | TODO | TODO | TODO | TODO | TODO |
| Ruuteri WAN | Ühendus labori ülemisse võrku | TODO | TODO | TODO | TODO | TODO |
| MG400 | Robot | TODO | TODO | TODO | TODO | TODO |
| Station PC | Kohalik juhtimine ja kaamerad | TODO | TODO | TODO | TODO | TODO |
| AtomS3R | Kohalik liides ja postkontori polling | TODO | TODO | TODO | DHCP reservation: TODO | TODO |
| XIAO ESP32S3 Sense | Tööriistakaamera | TODO | TODO | TODO | DHCP reservation: TODO | TODO |
| Telefon | Eraldi VPN-peer | TODO | TODO | TODO | WireGuardi aadress: TODO | TODO |
| Droplet | Avalik postkontor ja eraldi VPN-i sõlmpunkt | TODO | TODO | TODO | Lab 2 kinnitatud host / VPN: TODO | TODO |
| Labori ülemine võrk | Ruuteri WAN-i ülesvool ja NAT | TODO | TODO | TODO | Õppejõu võrguinfo: TODO | TODO |

Kui seadmel on mitu liidest või eraldi VPN-aadress, lisatakse igaühele oma
rida. Üldvaatekaamera USB-ühendus jaama ei vaja eraldi IP-aadressi.

Õppejõu ülesandes on MG400 algseadistusena `192.168.1.6`; see on enne
kasutamist kontrollitav lähteinfo, mitte meeskonna lõpliku Lab 3 võrgu tõend.

## Enne seadistamist otsustatav

- Ruuteri mudel, püsivara ja WireGuardi tugi: TODO
- Paberplaani autorid ning kuupäev: TODO
- Draw.io lähtefail ja elav muudetav link: TODO
- Eksporditud skeemipilt samas dokumendis: TODO
- LAN, WAN, labori ülemine võrk ja NAT-piirid joonisel: TODO
- Roboti IP säilitamine või muutmine ning põhjendus: TODO
- Staatilised aadressid, DHCP vahemik ja reservation'id ilma konfliktideta: TODO
- Admin-parooli vahetamise kinnitus ilma parooli avaldamata: TODO
- Tulemüüri minimaalsed lubatud teed ja iga erandi põhjendus: TODO
- Station'i kaitstud LAN/VPN-ligipääs ja XIAO IP-ligipääs: TODO
- Lab 1 ja Lab 2 funktsioonide kontroll pärast võrgu vahetust: TODO

Aadressiplaan on meeskonna otsus; selles ettevalmistuses seda ei valita.
VPN-i üksikasjad on [WireGuardi plaanis](wireguard/README.md).
