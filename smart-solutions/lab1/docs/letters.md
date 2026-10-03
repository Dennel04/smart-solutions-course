# Tähtede punktid ja mõõtmised

Fail `config/letters.json` kirjeldab tähtede A, L ja N tarkvaralisi trajektoore. Need trajektoorid ei kinnita, et MG400 on tähti füüsiliselt joonistanud.

## Tarkvaraline trajektoor

Koordinaadid kasutavad suhtelist ala `0,0 .. 1,0`. X kasvab vasakult paremale ja Y alt üles. Väärtused ei ole millimeetrid ega MG400 koordinaadid. Iga `stroke` on eraldi joon; liikumisplaan tõstab pliiatsi joonte vahel üles.

### A

Joon 1:

```text
(0,10; 0,00) -> (0,50; 1,00) -> (0,90; 0,00)
```

Joon 2:

```text
(0,30; 0,45) -> (0,70; 0,45)
```

### L

Joon 1:

```text
(0,20; 1,00) -> (0,20; 0,00) -> (0,85; 0,00)
```

### N

Joon 1:

```text
(0,15; 0,00) -> (0,15; 1,00) -> (0,85; 0,00) -> (0,85; 1,00)
```

## Laboris mõõdetav

- Joonistusala alguspunkt: leht õpetati kahe punktiga 03.10.26 — vasak alumine nurk X 335, Y −118; parem alumine nurk X 335, Y 146 (mm, MG400 baas).
- Joonistusala laius: lehe laius 264 mm (nurkade vahe), veeris 10 mm; roboti ulatuses ala 240 mm.
- Joonistusala kõrgus: lehe kõrgus 210 mm, roboti ulatuses ala 110 mm (alumine pool lehest; ülemine osa on MG400 sisemise piiri sees).
- Normaliseeritud punktide vastendus reaalsele XY-alale: täht 20 × 20 mm lahtrisse, lahtrid lehel järjest vasakult paremale ("kirjutusmasin"), lehe pööre kahe nurga järgi (`docs/text_drawing.md`).
- Pliiats üleval Z: −100 mm.
- Pliiats all Z: −110 mm esimesel katsel; seejärel proovitud −109, −111 ja −112 mm (03.10.26), hetkel −112 mm (serveri Z-piir viidud −112-le).
- R: −28°.
- Kiirus: esimesed katsed 2 % (õhus) ja 4 %, siis 20 %.

## Mõõdetud tulemus

- Täht A: joonistatud 2× Atomi nupuga (03.10.26), `letters.json` trajektoor; joonlauaga mõõtmine TODO.
- Täht L: TODO
- Täht N: 2 katset katkesid jaama 15 s ajapiirangu tõttu (parandatud); uuesti joonistamata.

## Tarkvara ja roboti ühendamine

- Normaliseeritud punkti teisendamine kalibreeritud abstraktseks XY-punktiks: tarkvaraliselt valmis.
- Reaalsed MG400 koordinaadid ja joonistusala mõõdetakse laboris: tehtud 03.10.26 (vt ülal).
- Ohutu pliiatsi tõstmise ja langetamise järjekord: tarkvaraliselt valmis ja mockidega kontrollitud; päris MG400-l kontrollitud 03.10.26.
- Esimene füüsiline joonistus: 03.10.26, K õhus 2 % kiirusel, siis paberil 2 % ja 4 %; Atomi tähed 20 %.

Kalibratsioon on praegu tahtlikult puudulik ja reaalsed väärtused on failis `config/robot_calibration.json` märgitud `null`. Täielik kalibratsioon üksi ei käivita MG400 käske. Liikumiseks peab station olema käivitatud eraldi `--execute` lipuga ning mg400-base safety gate peab läbima kõik kontrollid.

Kalibratsiooni struktuur ja ohutuspiirangud on kirjeldatud failis `docs/robot_calibration.md`.

## Lisandus 03.10.26: joonistatud tähed

Jaama logi `data/letter_events.csv`: 15 tähte jõudis Atomist jaama, 13 joonistati
(A A C D D D D E G G I J J). A on `letters.json`-ist; C, D, E, G, I, J puuduvad `letters.json`-is, need
võttis jaam ühejoonelisest fondist `futural` (`--letter-font`). Enne Atomi teste joonistati
jaamast K ja sõna „hello“.

Meeskonna initsiaalid: **D** (Denys) joonistatud; **N** (Nikita) ja **R** (Raimo) TODO.
Joonlauaga mõõtmine (kavandatud tähe kõrgus 20 mm): TODO.
*Mõõdetud 03.10.26:* joonistatud tähed on joonlauaga umbes 20–25 mm kõrged (kavandatud 20 mm).
*03.10.26 pärastlõuna:* **N** ja **R** joonistatud (seq 19 R, 21–23 N; pärast roboti nihutamist uus lehe kalibreering). Initsiaalid D, N, R olemas. Pärast R-i parandust (mg400-base pöörab R-i `MovJ`-ga) ja uut kalibreeringut mõõtis Denys joonlauaga: tähed **20 mm** kõrged = kavandatud 20 mm.

Esimesel katsel vajus pastakas pliiatsi alla laskmisel ~0,7 mm (2 %) ja ~1,3 mm (4 %)
sihtkõrgusest madalamale, sest järgmine joon algas enne, kui Z oli peatunud. Parandus:
pliiatsi üles/alla liigutus peab enne XY liikumist seisma ±0,15 mm täpsusega.
