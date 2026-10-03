# MG400 tarkvara ja võrgu ettevalmistus

## Baaspakett

- Repo URL: [https://github.com/KKallas/mg400-base](https://github.com/KKallas/mg400-base)
- Kloonimine:

  ```sh
  cd ~/Documents
  git clone https://github.com/KKallas/mg400-base.git
  cd mg400-base
  ```

- Python: versioon 3.10 või uuem.
- Virtuaalkeskkonna loomine ja aktiveerimine:

  ```sh
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- Paketi paigaldamine arendusrežiimis:

  ```sh
  python -m pip install --upgrade pip
  pip install -e .
  ```

## Tegelik tööjaotus

### Nikita arvuti

- Tarkvara ettevalmistus.
- `mg400-base` lokaalne paigaldus.
- Fake-MG400 testid.
- Reaalne robot ei ole ühendatud.

### Raimo arvuti

- Füüsiline ühendus MG400-ga.
- `mg400-base` juhendi järgi on juba tehtud reaalse roboti ettevalmistust ja katseid.
- Täpsed tehtud sammud ja tulemused tuleb allpool eraldi kinnitada.

### Denys

- Meeskonnaliige.
- Konkreetne roll selles MG400 etapis: TODO

## Seos Andmehõive Labor 1-ga

- MG400 ja pumbakasti esmane reaalne ühendus ning `mg400-base` kasutamine toimus sama meeskonna ühise laboritöö käigus.
- Andmehõive poolel kasutatakse sama `mg400-base` HTTP API-t pumba juhtimiseks Python loggerist.
- Smart Solutions poolel kasutatakse sama MG400 ühendust roboti liikumise, salvestatud asendite, pick-and-place'i ja hiljem tähtede joonistamise jaoks.
- Ühised ühendusfaktid võivad olla mõlemas repos dokumenteeritud.
- Ainepõhine kood, mõõtmised ja tulemused jäävad oma repo dokumentatsiooni.
- Smart Solutions repo ei kopeeri Andmehõive `logger.py` faili.
- Andmehõive repo: [https://github.com/Dennel04/data-acquisition-course](https://github.com/Dennel04/data-acquisition-course)

## Raimo arvutil juba tehtud

- [x] `mg400-base` kloonitud.
- [x] Python keskkond loodud.
- [x] `pip install -e .`
- [x] Ethernet ühendatud MG400 LAN1 porti.
- [x] Jaama IP seadistatud aadressile `192.168.1.50`.
- [x] `ping 192.168.1.6`
- [x] `mg400 status`
- [x] `mg400 serve`
- [x] Veebilehel **Connect**.
- [x] Veebilehel **Enable**.
- [x] Robotit liigutati veebilehe kaudu.
- [x] Liikumist kontrolliti 20% kiirusel.
- [x] Pumba funktsiooni test tehti.
- [ ] DO-liinide tegelik vastavus kontrollitud.
- [ ] Neli nõutud positsiooni salvestatud.
- [ ] Nõutud 10 järjestikust pick-and-place tsüklit tehtud.

Raimo arvutil tehtud töö on reaalne laboritöö, kuid dokumenti märgitakse tehtuks ainult need sammud, mille tulemus on meeskonnal kinnitatud.

### Pooleli olevad MG400 ülesanded

- DO1/DO2 tegelik vastavus imemisele ja puhumisele: DO2 = imemine, DO1 = puhumine (02.10.26).
- Kontrollimeetod (juhend / multimeeter / CLI): impulsid DO liinidele ja rõhuanduri lugem — imemine annab vaakumi, puhumine rõhu (`data-acquisition-course/.../docs/pump_control.md`, 02.10.26).
- `above_source` koordinaadid: TODO
- `source` koordinaadid: TODO
- `above_finished` koordinaadid: TODO
- `finished` koordinaadid: TODO
- 10 pick-and-place katse tulemused: TODO
- `docs/pick_test.csv` täitmine: TODO
- `data/positions.json` täitmine: TODO

## Võrguplaan

Need väärtused pärinevad baaspaketi juhendist. Meeskond peab need laboris enne roboti kasutamist üle kontrollima.

| Seade või väli | Väärtus |
| :--- | :--- |
| MG400 LAN1 | 192.168.1.6 |
| Jaam | 192.168.1.50 |
| Mask | 255.255.255.0 |
| Gateway | tühi |

## TCP pordid

| Port | Kanal | Otstarve |
| ---: | :--- | :--- |
| 29999 | Dashboard | Käsud, sealhulgas `EnableRobot`, `ClearError`, `DO` ja `GetPose`. |
| 30003 | Liikumine | Liikumiskäsud, sealhulgas `MovL` ja `ServoP`. |
| 30004 | Tagasiside | Roboti oleku, liigeste, tööriista asendi ja DO-bittide tagasiside. |

## Esimese ühenduse järjekord

- [ ] Ühenda võrgukaabel MG400 LAN1 porti.
- [ ] Seadista jaama IPv4 aadress ja mask võrguplaani järgi.
- [ ] Pingi `192.168.1.6`.
- [ ] Kontrolli porte 29999, 30003 ja 30004.
- [ ] Käivita `mg400 status`.
- [ ] Käivita `mg400 serve` või `mg400 serve --port 8080 --locations data/positions.json`.
- [ ] Vajuta lehel **Connect**.
- [ ] Vajuta lehel **Enable**.
- [ ] Tee esimene liigutus 20% kiirusel.
- [ ] Hoia E-stop käeulatuses.

## Pumba DO

Baaspakett eeldab, et DO2 juhib imemist ja DO1 puhumist. See ei ole veel meie laboris kinnitatud. Kontrolli DO-liine pumbakasti juhendi ja multimeetriga enne juhtmete ühendamist. Ühenda juhtmed ainult siis, kui robot on keelatud ja pumbakast ei ole vooluvõrgus.

## Laboris täidetavad tulemused

### Jaama valik

- Reaalses MG400 katses kasutatud arvuti: Raimo arvuti
- Jaama IPv4: `192.168.1.50`
- Ühendus: Ethernet → MG400 LAN1
- Etherneti liidese täpne nimi: TODO
- Mask: TODO
- 03.10.26 laboriarvuti (Denys): liides `Ethernet 2`, IPv4 `192.168.1.40`, mask `255.255.255.0` (/24), gateway tühi. Aadress on .40, mitte juhendi .50 — sama alamvõrk, robotiga töötab. Laboriarvutil Wi-Fi adapterit ei ole.

### MG400 ühendus

- `ping 192.168.1.6`: õnnestus
- `mg400 status`: töötas
- `mg400 serve`: töötas
- Web **Connect**: töötas
- Web **Enable**: töötas
- Liikumine veebilehelt: töötas
- Kontrollitud kiirus: 20%
- Eraldi pordikontroll: TODO
- 03.10.26 pordikontroll (`Test-NetConnection 192.168.1.6 -Port …`): 29999 avatud, 30003 avatud, 30004 avatud. `ping 192.168.1.6`: 4/4, 0–1 ms.

### Pump

- Pumba funktsiooni test: tehtud
- DO1/DO2 täpne vastavus: DO2 = imemine, DO1 = puhumine.
- Kontrollimeetod: DO impulsid + MPX5700AP rõhuandur (02.10.26).

### Muud tulemused

- Võimalikud vead: TODO
- Tehtud parandused: TODO
- 03.10.26: baaspaketis leitud puudused ja meie parandused (fork https://github.com/Dennel04/mg400-base, haru `lab-jog`):
  - liugurid saatsid käsu iga liigutuse ajal → nüüd liigub robot alles liuguri lahtilaskmisel; lisatud jog-nupud ja päris Sync (liugurid võtavad roboti tegeliku asendi);
  - Z põrand ainult koodis → käivitusvõti `--z-floor` ja muutmine töö ajal (meil −105 iminapaga, −112 pastakaga);
  - liigesepiire ei kontrollitud → pöördkinemaatika mudel (`kinematics.py`, L2 = 175,07 mm) peatab käe enne alarme 34 (J3 > 105°) ja 73 (parallelogramm, raadius < ~195 mm Z −16 juures); nupp **Recover** (`/api/recover`: ClearError + Continue); `/api/check` punkti kontrolliks enne liigutust;
  - `localhost` Windowsis proovib enne IPv6 → +200 ms päringu kohta; kasutame `127.0.0.1`.
