# Lab 2 kohalik kaamera-arhitektuur

> **Olek:** station'i tarkvarakiht, mock-allikad ja automaattestid on valmis.
> Päris USB- ja XIAO-kaamera, vaateväli, jõudlus ning kinnitused on veel
> kontrollimata. Selles failis ei ole laborimõõtmiste tulemusi.

## Rollid ja süsteemipiir

- **Table camera** on USB UHD-kaamera, mille tulevane ülesanne on näidata kogu
  tööala, ruudustikku ja robotit.
- **Tool camera** on XIAO ESP32S3 Sense, mille tulevane ülesanne on näidata
  tööriista otsikut ja selle all olevat detaili. Station saab temalt JPEG-pildi
  kohaliku Wi-Fi kaudu.

Mõlemat pilti näitab ainult station-arvuti lokaalne leht. Dropleti
postkontoris ei ole kaamera route'e, proxy't ega voogu. Lab 2 ei loo selleks
VPN-i, WireGuardi ega pöördtunnelit.

```text
USB UHD camera -------- USB ----------> station camera worker ---+
                                                               |--> local page
XIAO Sense -- local Wi-Fi JPEG/HTTP --> station camera worker ---+

droplet post-office <--- Atom outbound polling     (eraldi rada)
```

Kaamerakood ei impordi station'i job-adapterit, executor'it ega MG400 klienti.
Ühe kaamera rike ei muuda tööde vastuvõtmise või täitmise rada.

## Ühine allikaliides

`src/cameras/base.py` määrab kõigile allikatele sama liidese:

- `start()` käivitab ühe taustal töötava capture worker'i;
- `get_frame()` loeb viimast täielikku JPEG-kaadrit ega ava seadet;
- `status()` annab oleku, vea, resolutsiooni, konfiguratsiooni ja loendurid;
- `stop()` peatab worker'i ja vabastab allika.

HTTP kliendid jagavad sama worker'it ja viimast kaadrit. Seetõttu ei ava iga
brauser ega iga stream request USB-seadet uuesti. Allika lugemise või JPEG-i
viga märgib allika `unavailable`, kuid Flaski leht jääb tööle. Worker ootab
enne uut katset seadistatava retry-intervalli, et vältida tight loop'i.

## USB UHD backend

`UsbCamera` kasutab GUI-ta OpenCV paketti `opencv-python-headless`. Seadistatav
on seadme indeks või failitee, capture-resolutsioon, brauserivoogu skaleeritav
resolutsioon, FPS-siht, JPEG kvaliteet ja retry-intervall. `VideoCapture`
avatakse worker'i kohta üks kord ning vabastatakse nii stop'i kui vea järel.

Tarkvara arendusvaikeväärtused on capture `3840 × 2160`, stream `1280 × 720`
ja siht `10 FPS`. Need **ei ole mõõtmistulemus ega lõplik laborivalik**.
Lõplik capture/stream kombinatsioon valitakse päris vaatevälja, ruudustiku
loetavuse, viite ja koormuse katse järel.

## XIAO ESP32S3 Sense backend

`XiaoCamera` küsib seadistatavalt HTTP- või HTTPS-snapshot URL-ilt täieliku
JPEG-i. XIAO eraldi PlatformIO projekt `firmware-xiao-camera/` annab täpselt
`GET /snapshot.jpg` endpoint'i koos `image/jpeg` content type'i ja no-cache
päisega. IP-aadressi ega URL-i ei ole kummagi poole lähtekoodi kirjutatud.
Tühja URL-iga on station'i allikas ohutult `unavailable`; võrguviga käivitab
piiratud sagedusega uue katse. Vastuse suurus on piiratud ja poolik või
mitte-JPEG vastus lükatakse tagasi.

XIAO `GET /status` annab camera/Wi-Fi oleku, kohaliku IP, driver'i tuvastatud
sensorimudeli, väljastatud kaadrite loenduri ja uptime'i, kuid mitte Wi-Fi
parooli. Firmware SSID/parool tuleb ignored `wifi_private.h` failist. Station'i
status API näitab ainult seda, kas snapshot URL on seadistatud, ega tagasta
URL-i ennast.

Firmware kasutab ametlikku Seeed pin mapping'ut, boardi 8 MB PSRAM-i ja
`esp_camera` automaatset sensorituvastust. Driver toetab nii varasemat OV2640
kui uuemat OV3660 revision'it; meeskonna päris revision on veel TODO. Pidevat
XIAO MJPEG handler'it ei lisatud, sest olemasolev station backend vajab ainult
snapshot'i ning loob lokaalse MJPEG voo ise. See hoiab XIAO status endpoint'i
diagnostiliselt kasutatavana ja capture ownership'i üheselt mutex'i taga.

## Mock-režiim ja lokaalne leht

Käivita Lab 2 juurkaustast:

```bash
python -m src.camera_server --mock
```

Leht avaneb vaikimisi ainult loopback-aadressil
`http://127.0.0.1:5002/`. Brauserit automaatselt ei avata. Mõlemad allikad
genereerivad standardteegi abil sünteetilist JPEG-i; JPEG comment sisaldab
rolli (`TABLE` või `TOOL`), kaadriloendurit ja ajatemplit. Mock ei loo võrgu-,
dropleti-, serial- ega MG400 ühendust. Mock-andmeid ei kirjutata mõõtmiste CSV-sse.

Lokaalsed route'id:

| Route | Otstarve |
| :--- | :--- |
| `GET /` | kaks kõrvuti kaamerasektsiooni ja perioodiline olek |
| `GET /api/cameras` | mõlema allika kohalik status ja software-loendurid |
| `GET /snapshot/{table|tool}.jpg` | viimane täielik JPEG |
| `GET /stream/{table|tool}.mjpg` | MJPEG multipart-voog |

Need route'id kuuluvad eraldi `src.camera_server` protsessile, mitte avalikku
`server.app` postkontorisse. Päris laborivõrgus tuleb station'i lehele lisada
sama lokaalne autentimispiir nagu station'i juhtimislehel; selle kontroll on TODO.

Praegu autentimist camera route'idel ei ole ja vaikebind `127.0.0.1` hoiab need
ainult station-arvutis. Kui päris laborikatse nõuab hiljem station'i lehe
sidumist LAN-aadressile, otsustatakse enne seda eraldi, kas lisada lokaalne
autentimispiir. See ei ole praeguse tarkvaraaluse valmimise väide ega ametliku
Lab 2 eraldi nõue. Ka XIAO `/status` ja `/snapshot.jpg` on kohaliku Wi-Fi-võrgu
endpoint'id; neid ei port-forward'ita ega lisata Caddy konfiguratsiooni.

## Tarkvaraloendurid

Iga allikas loendab:

- capture worker'i loodud kaadrid (`frames_captured`);
- HTTP kaudu väljastatud kaadrid (`frames_served`);
- JPEG payload'i väljastatud baidid (`bytes_served`);
- protsessi uptime'i;
- uptime'i põhjal arvutatud keskmise capture/served FPS-i;
- keskmise bytes/s ja ligikaudse Mbit/s väärtuse.

Need on protsessi tarkvaraloendurid. Eriti `served_fps` ja `mbit_per_s`
sõltuvad ühendatud brauseritest; need ei ole füüsiline camera latency ega
valmis hinnatav tulemus.

## Tulevane mõõtmismetoodika

### Kaamera viide

USB ja XIAO jaoks kasutatakse sama protseduuri. Kaamera vaatevälja pannakse
selgelt muutuv taimer või LED-sündmus. Ühes ajabaasis salvestatakse korraga
füüsiline sündmus ja brauseris kuvatud vastav kaader. Iga katse puhul leitakse
`physical event → displayed frame` vahe millisekundites. Korratakse piisav arv
kordi sama võrgu, resolutsiooni, FPS-sihti ja brauserit dokumenteerides. XIAO
puhul märgitakse lisaks Wi-Fi tingimused. Tegelikud tulemused lisatakse alles
pärast päriskatset faili `camera_metrics.csv`.

### FPS ja ribalaius

Kindla mõõteakna alguses ja lõpus loetakse `frames_served` ning
`bytes_served`. Tegelik served FPS on kaadrite vahe jagatud sekunditega;
keskmine ribalaius on baitide vahe × 8 / sekundid / 1 000 000. Mõõtmise ajal
fikseeritakse brauseriklientide arv, capture- ja stream-resolutsioon ning
JPEG kvaliteet. Mock-tulemusi graded CSV-sse ei lisata.

### Juhtimislatentsus 0 / 1 / 2 kaameraga

Sama valideeritud töö ja samad station'i seaded käivitatakse kolmes tingimuses:
kaamerateta, ainult ühe aktiivse vooga ja kahe aktiivse vooga. Igas tingimuses
kasutatakse sama sündmuse algus- ja station'i vastuvõtu/lõpetamise timestamp'i,
tehakse mitu kordust ning dokumenteeritakse klientide arv ja kaameraseaded.
Kaamerakood ei lisa job/executor rajale callback'e; võrdlus mõõdab eraldi
protsesside tegelikku koormusmõju. Tulemused lähevad pärast päriskatset faili
`control_latency_cameras.csv`.

## Labori kontrolliplaan

Järgmised sammud tehakse ainult päris riistvaraga. Mock-kaadreid ega software
loendureid ei kanta mõõtmistulemustena CSV-failidesse.

1. Kontrollida laboris USB UHD-kaamera ja XIAO ESP32S3 Sense olemasolu ning
   täpsed seadmerevisionid. Kontrollida eraldi USB-pikendust, XIAO toidet ja
   station'i vabu USB-/võrguühendusi.
2. Paigaldada 3D Printing Lab 2 kinnitused: laua kaamera robotist kõrgemale ja
   tööriistakaamera iminapa kõrvale. Enne kinnitamist kontrollida kaabli
   tegelik marsruut, liikumisvaru ja strain relief.
3. Kontrollida laua kaamera vaatevälja: kogu laud, Gridfinity ruudustik servast
   servani, robot ja hoidikud peavad olema samas kaadris; ruutude nimed peavad
   valitud kuvamisresolutsioonis loetavaks jääma.
4. Laadida olemasolev PlatformIO firmware päris XIAO-sse ja kontrollida
   `/status`, tuvastatud sensorit, PSRAM-i, Wi-Fi reconnect'i ning
   `/snapshot.jpg` JPEG-vastust. Salajast `wifi_private.h` faili reposse ei
   lisata ja XIAO endpoint'i internetti ei avaldata.
5. Kontrollida tööriistakaamera vaatevälja: otsik ja detail otse selle all
   peavad olema nähtavad kogu vajaliku robotiliikumise jooksul.
6. Käivitada mõlemad pärisallikad station'i lehel ja kontrollida, et Table
   camera ning Tool camera on samaaegselt eristatavad. Kui leht peab olema
   avatav teistest LAN-i seadmetest, otsustada ja dokumenteerida enne bind'i
   muutmist kohalik ligipääsupiir.
7. Mõõta kummagi kaamera kohta eraldi capture- ja kuvamisresolutsioon,
   sündmusest kuvatud kaadrini viide, tegelik FPS ning ribalaius. Fikseerida
   katse aeg, trial, klientide arv, seaded ja meetod failis
   `camera_metrics.csv`.
8. Korrata sama valideeritud robotitöö juhtimislatentsuse katset võrreldavates
   tingimustes: 0 aktiivset kaamerat, ainult 1 aktiivne kaamera ja mõlemad ehk
   2 aktiivset kaamerat. Kanda iga trial faili
   `control_latency_cameras.csv`; kokkuvõte ja valitud kaameraseaded tehakse
   alles pärisandmete põhjal.
9. Kontrollida lõpuks, et camera route'e ei ole postkontori Caddy
   konfiguratsioonis, droplet ei proxy pilte ning pildid jäävad ainult
   ettenähtud station'i/labori kohaliku võrgu piirile.

## Riistvara TODO

- ühendada ja identifitseerida päris UHD USB-kaamera;
- valida vaatevälja ja loetavuse põhjal capture- ja stream-resolutsioon;
- laadida valmis XIAO PlatformIO firmware päris seadmesse, kontrollida sensor
  ning määrata lokaalne URL ja võimalik autentimine;
- kontrollida mõlema allika reconnect'i päris katkestustega;
- mõõta viide, FPS, ribalaius ning 0/1/2 kaamera juhtimislatentsus;
- paigaldada kaamerad ja lisada ainult päriskatses saadud tulemused/fotod.
