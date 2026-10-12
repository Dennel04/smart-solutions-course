# Nutikad Lahendused: Labor 3 — Ruuter ja VPN

> Labor 3 füüsiline töö ei ole veel alanud. See tööleht ja failistruktuur on
> loodud ettevalmistusena. Tegelikud IP-aadressid, ruutimistabelid, VPN-i
> võtmed, latentsused, kaameramõõdikud ja 48 tunni logi jäävad kuni päris
> katseteni märgendiga **TODO**. Laborite 1 ja 2 tulemusi võib siia üle tuua
> ainult pärast vastavate failide kontrollimist.

**Töömaht:** 30 tundi
**Hindamine:** 20 punkti
**Meeskond:** 3 tudengit
**Välja antud:** 28.10.26
**Tellimise kuupäev:** 06.11.26
**Esimene kaitsmine:** 17.11.26, veebis

Õppejõu täielik ülesanne on failis
[`assignment-EST.md`](assignment-EST.md) (originaal, muutmata).

## Eesmärk ja arhitektuur

Labor 2 avalik postkontor jääb kõrgtaseme tööde teeks:

```text
User
  |
HTTPS
  v
Public post-office
  ^
  |
outbound polling
  |
Atom
  |
local
  v
Station -> MG400
```

Labor 3 lisab sellest eraldi VPN-i kaudu otsejuurdepääsu laborivõrgule:

```text
Phone
  |
WireGuard
  v
Droplet
  |
WireGuard tunnel
  v
Lab router
  |
  +-- Station
  +-- MG400
  +-- Atom
  +-- XIAO camera
```

Skeemid on ainult kontseptuaalsed. Alamvõrk, IP-aadressid, ruuteri mudel,
WireGuardi pordid ja võtmed valitakse või kontrollitakse alles päris seadmetega.
Avalik postkontor ei ole VPN-i juhtimistee.

## Kontrollnimekiri

- [ ] Aadressiplaan on paberil ja draw.io-s: iga seade, aadress, alamvõrk ja aadressi allikas.
- [ ] Ruuter on seadistatud ning robot, jaam, Atom ja kaameramoodul saavad tema võrgus püsivad aadressid; vaikimisi admin-parool on vahetatud.
- [ ] Laborite 1 ja 2 funktsioonid töötavad uues võrgus edasi.
- [ ] Jaama ja ruuteri ruutimistabelid on loetud ning iga rida on selgitatud.
- [ ] Jaam → MG400, jaam → droplet ja jaam → internet teekonnad on enne ennustatud ning seejärel mõõdetud.
- [ ] NAT on vaadeldud ja dropleti nähtud lähteaadress on selgitatud.
- [ ] WireGuardi tunnel ruuteri ja dropleti vahel töötab ning taastub pärast ruuteri taaskäivitust.
- [ ] Telefon on VPN-is; jaama leht avaneb väljalülitatud Wi-Fi ja mobiilse andmesidega.
- [ ] Jaama leht ning robot ei ole väljast ilma tunnelita kättesaadavad.
- [ ] Üks marsruut on tahtlikult katki tehtud; ennustus ja tegelik tulemus on dokumenteeritud.
- [ ] Tehtud on 30 kohaliku võrgu latentsusmõõtmist.
- [ ] Tehtud on 30 VPN-i latentsusmõõtmist.
- [ ] Mõlemad kaamerad töötavad VPN-i kaudu ning latentsus, FPS ja ribalaius on mõõdetud.
- [ ] Ühenduse katkemist liikumise ajal on ohutult katsetatud kolm korda.
- [ ] Droplet on kogunud tunneli 48 tunni logi 10-sekundilise kontrollsammuga.
- [ ] Labori 2 ohutuskokkulepet on otsejuhtimise jaoks täiendatud ja kõik liikmed on selle kinnitanud.
- [ ] Atomi lehel on klapi seaded ja testinupp.
- [ ] Atomi lehel on UV LED-i seaded, ülempiir, testinupp ja automaatne väljalülitus.
- [ ] BOM on täidetud failis [`docs/bom.md`](docs/bom.md) hiljemalt 06.11.26.
- [ ] Repo ja arenduspäevik on valmis.
- [ ] Esitamisel on loodud tag `smart-solutions-lab3`.

Kõik punktid on alguses lahti ning märgitakse tehtuks ainult kontrollitava
tulemuse või päris katse järel.

## Vajalikud sisendid varasematest laboritest

### Smart Solutions Lab 2

Vaja on päris dropletit ja HTTPS-i, töötavat postkontorit, päris Atomi
pollingut, lubatud tööde nimekirja, ohutuskokkulepet, mõlemat füüsilist
kaamerat jaama lehel ning kaamera- ja juhtimislatentsuse lähteväärtusi.
Labor 2 on veel töös; selle tegelik lõppseis ja väärtused tuleb võtta ainult
kaustast [`../lab2/`](../lab2/).

### Data Acquisition Lab 3

Vaja on solenoidklapi ja UV LED-i käske, ohutuskäitumist ning vajaduse korral
alarmi-/sündmuselepingut.

**TODO — Data Acquisition Lab 3 physical implementation not available yet**

### 3D Printing Lab 3

Vaja on ühendatud tööriista: iminapp, süstal, UV-lamp ja kaamera, koos
kontrollitud tööriistanihetega.

**TODO — 3D Printing Lab 3 physical implementation not available yet**

## Tööfailid

- [`docs/network_plan.md`](docs/network_plan.md) — tulevane aadressiplaan.
- [`docs/routing.md`](docs/routing.md) — ruutimistabelid, teekonnad, NAT ja katkine marsruut.
- [`docs/safety.md`](docs/safety.md) — Labori 2 ohutuskokkuleppe laiendus.
- [`docs/atom_page.md`](docs/atom_page.md) — klapi ja UV LED-i tulevane leheliides.
- [`docs/bom.md`](docs/bom.md) — inventuur ja võimalik tellimus.
- [`data/latency_local.csv`](data/latency_local.csv) ja
  [`data/latency_vpn.csv`](data/latency_vpn.csv) — latentsuse mõõtmismallid.
- [`data/camera_vpn_metrics.csv`](data/camera_vpn_metrics.csv) — VPN-kaamerate mõõtmismall.
- [`data/tunnel_48h.csv`](data/tunnel_48h.csv) — 48 tunni tunneli logimall.
- `docs/wireguard/` — tulevased võtmeteta WireGuardi dokumendid.

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

### Väljundid ja tulemused

**Väljundid**
* Data Acquisition L3: TODO — kontrollitud klapi ja UV LED-i käsud, seaded, testid ning vajaduse korral alarmisündmus.
* 3D Printing L3: TODO — kaugelt nähtav ühendatud tööriist ja kontrollitud tööriistanihked.
* Smart Solutions L4: TODO — kontrollitud võrk, tunnel ja droplet.

**KAARDISTA ISE, lõpus.**
* Git repo ja tag: TODO — tag luuakse alles esitamisel.
* Numbrid, mille see labor andis, ühikutega: TODO — päris mõõtmised.
* Mida me teeksime teisiti: TODO — täita pärast laborit.
* Mida järgmine labor peaks enne alustamist teadma: TODO — täita kontrollitud tulemuste põhjal.
