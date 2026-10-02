# MG400 tähejoonistuse runbook Denysile

See juhend on mõeldud kasutamiseks roboti juures olevas arvutis. Ära sisesta
oletuslikke koordinaate ega Z-kõrgusi. Kõik kalibratsiooniväärtused mõõdetakse
reaalselt ja esimene katse tehakse 20% kiirusel.

## A. Uuenda Smart Solutions repo

```sh
cd ~/Developer/Nutilahendused
git remote set-url origin git@github.com:Dennel04/smart-solutions-course.git
git pull --ff-only
```

## B. Paigalda jaama sõltuvused

macOS/Linux:

```sh
cd ~/Developer/Nutilahendused
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r smart-solutions/lab1/src/requirements.txt
```

Windows PowerShell samas repo kaustas:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r smart-solutions/lab1/src/requirements.txt
```

## C. Käivita mg400-base

Eraldi terminalis:

macOS/Linux:

```sh
cd ~/Developer/mg400-base
source .venv/bin/activate
mg400 serve
```

Windows PowerShell mg400-base kaustas:

```powershell
.\.venv\Scripts\Activate.ps1
mg400 serve
```

`mg400 serve` peab olema ainus programm, mis juhib MG400 TCP ühendusi.
Smart Solutions jaam kasutab ainult selle HTTP API-t ega ühendu otse Doboti
portidesse.

## D. Ühenda ja luba brauseris

Ava mg400-base leht aadressil `http://127.0.0.1:8000`, seejärel vajuta:

1. **Connect**
2. **Enable**

Jaam ei kutsu automaatselt `EnableRobot` käsku. Kui robot pole lubatud, peab
jaam liikumisest keelduma.

## E. Kontrolli olekut

Kasuta ühte neist:

```sh
mg400 status
curl -s http://127.0.0.1:8000/api/status
```

Enne jätkamist kontrolli, et robot on lubatud ning puuduvad `error`,
`fault_label`, `link_error`, `servo_error` ja `stalled` olekud. Lisaks peavad
`connected`, `feedback_ok` ja `servo_active` olema tõesed.

## F. Käivita kõigepealt dry-run

Uues terminalis:

```sh
cd ~/Developer/Nutilahendused/smart-solutions/lab1
source ../../.venv/bin/activate
python src/station.py
```

Teises terminalis kontrolli tarkvarateed:

```sh
cd ~/Developer/Nutilahendused/smart-solutions/lab1
source ../../.venv/bin/activate
python src/mock_atom.py --url http://127.0.0.1:5000 --letter A
```

Vastuses peavad olema `dry_run: true` ja `robot_started: false`. See režiim
ei tohi saata mg400-base serverile käske.

Windows PowerShellis kasuta sama `src/station.py` ja `src/mock_atom.py` käsku
pärast repo kausta avamist ning `.\.venv\Scripts\Activate.ps1` käivitamist.

## G. Täida kalibratsioon ainult mõõdetud väärtustega

Peata dry-run station ja ava:

```text
smart-solutions/lab1/config/robot_calibration.json
```

Mõõda ning sisesta `origin_x`, `origin_y`, `width`, `height`, `r`,
`pen_up_z`, `pen_down_z` ja `speed_percent`. Ära asenda `null` väärtust enne,
kui vastav suurus on roboti juures päriselt mõõdetud.

## H. Valmista ette esimene õhukatse

- Hoia füüsiline E-stop käeulatuses.
- Veendu, et liikumiskäske saadab ainult üks programm.
- Sea ja mõõda esimese katse kiiruseks 20%.
- Mõõda õhukatse Z nii, et pliiats jääb ligikaudu 20 mm paberi kohale.
- Esimeses õhukatses ei tohi `pen_down_z` viia pliiatsit paberini.

## I. Käivita execute station

Kui kõik kalibratsiooniväljad sisaldavad reaalselt mõõdetud õhukatse väärtusi:

```sh
cd ~/Developer/Nutilahendused/smart-solutions/lab1
source ../../.venv/bin/activate
python src/station.py --execute --mg400-url http://127.0.0.1:8000
```

Ilma `--execute` liputa jääb station alati dry-run režiimi.
HTTP `202` ja `robot_started=true` kinnitavad ainult seda, et jaam võttis
töö vastu ning käivitas taustatöötaja. Kontrolli pärast liikumist jaama
sündmuslogist, kas olek on `executed` või `execution_error`.

Windows PowerShellis pärast repo kausta avamist ja virtuaalkeskkonna
aktiveerimist:

```powershell
cd smart-solutions/lab1
python src/station.py --execute --mg400-url http://127.0.0.1:8000
```

## J. Seadista Atomi jaama aadress

Sisesta Atomi seadete lehel `station address` väljale robotiarvuti tegelik
võrguaadress ja port `5000`. Ära kasuta oletuslikku IP-aadressi; kontrolli see
robotiarvutis enne sisestamist.

## K. Saada testtäht

Kasuta kõigepealt Atomi lehe nuppu **TEST LETTER SEND**. Kui see õhukatse on
ohutult edukas, kontrolli füüsilise nupu pika vajutuse saatmisteed.

Pärast edukat õhukatset mõõda pliiatsi tegelik joonistamise Z, lisa varasema
õhukatse väärtuse juurde kuupäevaga parandus dokumentatsiooni ning alles siis
kasuta uut mõõdetud `pen_down_z` väärtust. Ära märgi tähte joonistatuks enne
reaalset kontrolli.

## Ohutus

- E-stop peab olema käeulatuses.
- Liikumiskäske saadab korraga ainult üks programm.
- `mg400 serve` peab olema ainus MG400 controller.
- Esimene jooks toimub 20% kiirusel.
- Pliiats on esimeses jooksus ligikaudu 20 mm paberi kohal.
