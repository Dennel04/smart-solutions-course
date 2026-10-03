# Teksti joonistamine: fondid, suurus ja A4 leht

Jaam oskab lisaks Atomi ühele tähele joonistada terve teksti valitud fondi ja
suurusega paberilehele. Kõik arvutused (paigutus, ulatuse kontroll, plaan)
käivad ilma robotita; robot liigub ainult `--execute` režiimis pärast samu
ohutuskontrolle nagu tähe puhul.

## Kasutamine

```sh
cd smart-solutions/lab1
python src/station.py            # dry-run, robot ei liigu
```

Ava brauseris `http://127.0.0.1:5000/`: tekst, font, suurtähe kõrgus mm-des või
„Sobita suurim suurus lehele“, joondus, lehe suurus/suund, ala ja veeris.
**Eelvaade** näitab lehte, punasega roboti ulatusest välja jäävat osa, sinise
katkendjoonega joonistusala ja hallide punktiiridega pliiatsi õhusõite.

## Fondid

Ühejoonelised (single-stroke) Hersheyi fondid: iga joon joonistatakse üks
kord, nagu plotteril. TTF-fondid on kontuurid ja pliiatsiga ei sobi.

| Nimi | Kirjeldus |
|---|---|
| `futural` | Sans, lihtjoon — kiireim, vaikimisi |
| `futuram` | Sans, topeltjoon (paksem, ~2× aeglasem) |
| `timesr` | Serif (Times) |
| `scripts` | Käekiri, lihtjoon |
| `cursive` | Kursiiv |
| `gothiceng` | Gooti (palju punkte, aeglane) |

Allikas: Hersheyi fondid (A. V. Hershey, 1967, avalik omand) paketi
`Hershey-Fonts` 2.1.0 (MIT) kaudu. JSON-failid `config/fonts/` on genereeritud
skriptiga `tools/build_fonts.py`; jaam ise seda paketti ei vaja.

Hersheyi andmetes pole eesti tähti, seega **Õ Ä Ö Ü Š Ž** (ja väiketähed)
koostatakse põhitähest ja joonistatud märgist. Kirillitsat praegu pole: täht,
mida font ei oska, annab selge vea, mitte vaikset vahelejätmist.

## Suurus

`size_mm` = suurtähe kõrgus (mõõda joonlauaga „H“ tähte). Reavahe on
`line_spacing × size_mm` (vaikimisi 1,6). Sõnu ei poolitata: kui sõna ei mahu
reale, tuleb viga ja tuleb valida väiksem suurus või „sobita“. Alla 5 mm
tähtede kohta antakse hoiatus (pliiatsi joon on ~0,5–1 mm).

„Sobita“ otsib binaarotsinguga suurima suuruse (0,1 mm täpsusega), mille
juures kogu tekst mahub alasse; mõõdetakse tegelikku tinti, nii et Õ/Ä märgid
ja käekirja sabad jäävad ala sisse.

## Miks mitte terve A4

MG400 tööraadius on andmelehe järgi 440 mm, aga sisemine piir sõltub Z-st.
Labori roboti liigese-/parallelogrammimudeli järgi (mg400-base `kinematics.check`):

| Z, mm | Ulatus raadiuses, mm |
|---|---|
| −60 | 206 … 444 |
| −80 | 202 … 444 |
| −100 | 194 … 440 |
| −120 | 212 … 432 |

A4 (210 × 297 mm) ei mahu tervikuna ühte rõngasse. Seepärast on vaikimisi
alaks **„roboti ulatuses“**: suurim lehe servadega paralleelne ristkülik, mille
iga punkt on ohutus rõngas 215 … 430 mm (205 … 440 mm miinus 10 mm varu).
Kontrollitakse ka sirgeid lõike, sest kahe ulatuses punkti vaheline sirge võib
minna läbi siserõnga.

Enne päris joonistamist küsib jaam lisaks mg400-base `/api/check` kaudu iga
punkti pliiatsi all- ja ülakõrgusel. Kui see punkt tabaks liigese piiri, ei
liigu robot üldse (HTTP 503). Ametlikus mg400-base'is `/api/check` puudub;
siis kehtib ainult rõngakontroll ja logisse tuleb hoiatus.

## Lehe kalibreerimine (kaks punkti)

Lehe asukoht ja pööre robotis on failis `config/robot_calibration.json`,
sektsioonis `paper`. Väärtused on `null`, kuni need on laboris mõõdetud.

1. Kinnita leht teibiga lauale, nii et kogu ala oleks roboti ees (keskel
   umbes 300 mm robotist).
2. Pliiats üleval, juhi pliiatsi ots mg400-base lehel jog-nuppudega **lehe
   alumise vasaku nurga** kohale (nii, nagu teksti loetakse). Loe X ja Y →
   `corner_x`, `corner_y`.
3. Juhi pliiats **sama alumise serva** mõnda punkti paremal (vähemalt 50 mm,
   parem 150+ mm nurgast). Loe X ja Y → `edge_x`, `edge_y`.
4. Täida `size` (`A4`, `A5`, `A3`, `Letter`), `orientation`
   (`portrait`/`landscape`) ja `margin_mm`.

Kaks punkti annavad lehe asukoha ja nurga, seega tekst on loetav ka siis,
kui leht on roboti telgede suhtes viltu. Teksti jaoks on vaja ka
`pose.r`, `pose.pen_up_z`, `pose.pen_down_z` ja `motion.speed_percent`
(vt `robot_calibration.md`); `workspace` on ainult Atomi ühe tähe jaoks.

## Kiirus

Iga punkt on roboti peatus (mg400-base järgija kiirendab ja pidurdab), seega
aja hinnang = lõigud trapetsprofiiliga + ~0,15 s punkti kohta. Näide: 3 rida
20 mm `futural` A4-l ≈ 370 punkti ≈ 5–6 min 20% kiirusel. Teekonna
optimeerija eemaldab ühel sirgel olevad punktid, järjestab jooned lähima
naabri järgi (vajadusel tagurpidi) ja liidab kokku puutuvad jooned, et
pliiats ei tõuseks asjata.

## HTTP API

| Meetod | Tee | Mida teeb |
|---|---|---|
| GET | `/` | veebileht |
| GET | `/api/fonts` | fondide nimekiri |
| POST | `/api/text/preview` | paigutus + SVG, robotit ei puuduta |
| POST | `/api/text/draw` | dry-run: plaan stdout'i; execute: ohutuskontroll ja joonistamine (202) |
| GET | `/api/text/<job>` | töö olek: `started`, `completed`, `failed` |

Päringu keha: `{"text": "Tere", "font": "futural", "size_mm": 20}` või
`"fit": true`; valikulised `align`, `line_spacing`, `letter_spacing_mm`,
`area` (`reachable`/`sheet`), `size`, `orientation`, `margin_mm`.

Tekstitööd logitakse faili `data/text_events.csv`, mitte
`data/letter_events.csv`-i, et Atomi 30 vajutuse latentsuse mõõtmine jääks
puhtaks.

## Atomi tähed

`letters.json` sisaldab käsitsi tehtud A, L ja N. Muud tähed A–Z võetakse nüüd
fondist `futural` ja skaleeritakse samasse 0..1 kasti (`--letter-font`,
`--letter-font none` taastab vana käitumise: tundmatu täht → 422).
