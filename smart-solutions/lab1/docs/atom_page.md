# AtomS3 lehe kirjeldus

Captive portal ning seadete ja ekraanitesti tarkvaraline teostus lisati enne laborikatset. 03.10.26 kontrollitud reaalsed väärtused ja riistvaratesti tulemused on kirjas allpool.

## Võrk ja leht

| Väli | Väärtus |
| :--- | :--- |
| Wi-Fi SSID | `AtomFramer` (SoftAP, kui salvestatud võrku pole) |
| Parool | `atomframer` — vaikimisi, vahetada enne kui Atom laborist lahkub |
| Atom IP | `192.168.4.1` (03.10.26 serial `ip` käsuga) |
| Lehe URL | `http://192.168.4.1/` |

## Captive portal

SoftAP-režiimis käivitab püsivara `DNSServer`-i. Wildcard DNS suunab kõik nimed aadressile `WiFi.softAPIP()`. STA-režiimi lülitumisel DNS peatatakse. Tundmatu URL avab AP-režiimis Atom Frameri avalehe ja annab STA-režiimis vastuse `404 Not found`.

Püsivara suunab avalehele järgmised captive portal probe'i aadressid:

- Android: `/generate_204` ja `/gen_204`
- iPhone/iOS: `/hotspot-detect.html` ja `/library/test/success.html`
- Windows ja muud kliendid: `/connecttest.txt`, `/ncsi.txt`, `/redirect`, `/canonical.html` ja `/success.txt`

- Tarkvaraline teostus: lisatud
- Automaatne avanemine Android-telefonis: tehtud 03.10.26, tulemus allpool
- Automaatne avanemine iPhone'is: TODO
- Käitumine eri operatsioonisüsteemidega: TODO
- 03.10.26 Android-telefon (Denys): leht avanes ise pärast `AtomFramer` võrguga liitumist. Atomi logi (`[atom-log] portal GET …`, sild `src/atom_bridge.py`) näitas, mida telefon küsis: `http://connectivitycheck.gstatic.com/generate_204` (7× ~minuti jooksul, Android kontrollib korduvalt), `…/favicon.ico`, lisaks taustaäpp `http://c.whatsapp.net/chat`. Kõik said vastuseks Atomi lehe.
- 03.10.26 probleem: Androidi sisselogimisaknas laadis lehe ülespoole kerimine lehe uuesti ("tõmba värskendamiseks") ja valitud pilt kadus. Parandus: lehe CSS `overscroll-behavior-y: contain`; pilt saadeti Chrome'ist (`http://192.168.4.1`, "kasuta võrku nii nagu on").
- iPhone: ei kontrollitud (meeskonnas ei olnud iPhone'i käepärast).

## Pildi saatmine

- 128 × 128 pildi saatmise aeg: mõõdetud Atomis, kokku ~0,33 s
- Mõõtmise kuupäev ja tingimused: 03.10.26, Android Chrome, Atomi Wi-Fi
- Reaalne pildi saatmine AtomS3-le: tehtud, pilt kuvati pesas 1
- 03.10.26: pilt saadeti Android-telefonist Chrome'iga, `SEND → SLOT`, pesa 1; pilt ilmus Atomi ekraanile. Atomi logi (aeg mõõdetakse Atomis `millis()` järgi, alates esimesest vastuvõetud tükist):

  | Katse | Tähe nupurežiim | Vastu võetud 32768 B | Salvestus + ekraan |
  |---|---|---|---|
  | 1 | sees (ekraanile ei joonistata) | 77 ms | 246 ms (ainult salvestus) |
  | 2 | väljas | logirida katkes USB-s | — |
  | 3 | väljas | 72 ms | 254 ms |

  Üks 128 × 128 pilt (32 768 B RGB565) üle Atomi Wi-Fi: vastuvõtt ~75 ms, LittleFS-i salvestus + ekraan ~250 ms, kokku ~0,33 s Atomis. Telefoni poolt mõõdetud koguaeg (leht näitab `in N ms`) jäi üles kirjutamata.
- Tähe nupurežiimis ei joonista võrk Atomi ekraanile (`netMayDraw()`): ekraan on tähe nupp. Pildi nägemiseks lülita seadetes režiim välja.
- Teadaolev viga: osa Atomi USB logiridu katkeb (`portal G`, `po`), arvatavasti USB serialli puhvri ületäitumine; tähe JSON read ja mõõtmised ei ole sellest mõjutatud, kuid üks ajamõõtmise rida kadus.

## Seadete osa

Olemasolevale Atom Frameri lehele on lisatud `Settings & tests` osa järgmiste väljadega:

- Wi-Fi name (SSID)
- Wi-Fi password
- Station address

`GET /settings` tagastab salvestatud SSID, jaama aadressi, võrgurežiimi ja IP-aadressi. Salvestatud Wi-Fi parooli vastus ei sisalda ning parooliväli jääb lehe avamisel tühjaks.

Kui SSID ei muutu ja parooliväli on tühi, jätab veebileht salvestatud Wi-Fi parooli muutmata. Uue SSID korral salvestab `POST /settings` sisestatud SSID ja parooli koos.

`POST /settings` võtab vastu `application/x-www-form-urlencoded` väljad `station`, `ssid`, `pass` ja valikulise `connect=1`. Ilma `connect` väljata salvestab Atom seaded ning jääb praegusesse võrgurežiimi. Väärtusega `connect=1` saadab Atom esmalt HTTP-vastuse ja alustab seejärel ühendamist olemasoleva `startSTA` funktsiooni kaudu.

Nupud:

- `SAVE SETTINGS`
- `SAVE + CONNECT`
- `TEST DISPLAY STATUS`
- `TEST LETTER SEND`

Seadetes on eraldi `Letter button mode` valik. Kui see on välja lülitatud,
säilivad olemasolevad sloti short/long/double žestid. Kui valik on sisse
lülitatud, valib lühike vajutus järgmise tähe `A`–`Z` ja pikk vajutus saadab
valitud tähe jaamale. Reaalne nupukäitumine kontrollitakse AtomS3-l.

## Testinupud

`POST /test/display` kutsub välja olemasoleva võrgu ja seadme olekuekraani. Endpoint ei lisa näidisandmeid ega kinnita ekraani füüsilist toimimist.

`POST /test/letter` võtab vastu vormivälja `letter=A`, valideerib vahemiku
`A`–`Z` ning käivitab sama letter sender pipeline'i nagu füüsilise nupu pikk
vajutus. HTTP handler tagastab kohe järjekorda lisamise oleku ega oota
korduskatsete lõppu.

- Ekraani oleku testi tarkvaraline teostus: lisatud
- Ekraani oleku test reaalsel AtomS3-l: TODO
- Tähe saatmise tarkvaraline testitee: lisatud
- Atom ↔ jaam end-to-end test: USB kanaliga tehtud 03.10.26; Wi-Fi kanalit ei kasutatud, sest laboriarvutil puudub Wi-Fi

## Riistvaratesti kontrollnimekiri

- [x] Laadi püsivara reaalsele AtomS3-le. *(03.10.26, PlatformIO, ühendatud püsivara)*
- [x] Märgi kasutatud Wi-Fi SSID, Atom IP ja lehe URL. *(03.10.26)*
- [x] Kontrolli captive portalit Android-telefoniga. *(03.10.26)*
- [ ] Kontrolli captive portalit iPhone'iga.
- [x] Kontrolli pildi saatmist ja kuvamist AtomS3 ekraanil. *(03.10.26, Android Chrome, pesa 1)*
- [x] Mõõda 128 × 128 pildi saatmise aeg. *(Atomis kokku ~0,33 s; telefoni koguaega ei salvestatud)*
- [ ] Kontrolli seadete püsimist pärast taaskäivitust.
- [ ] Kontrolli STA-ühendust labori võrgus.
- [ ] Kontrolli, et `GET /settings` ei tagastaks Wi-Fi parooli.
- [ ] Kontrolli `TEST DISPLAY STATUS` nuppu reaalsel ekraanil.
- [ ] Kontrolli `TEST LETTER SEND` nuppu päris Atomi ja jaamaga.
- [x] Kontrolli lühikese ja pika vajutuse tähe nupurežiimi. *(03.10.26: nupp on ekraan ise; lühike → järgmine täht, pikk → saadab; külgmine nupp on RESET)*
- [ ] Kontrolli, et tähe nupurežiimi väljalülitamisel töötavad sloti žestid endiselt.

## Lisandus 03.10.26: ühendatud püsivara

- Atomil jookseb üks püsivara: see leht + Andmehõive tark pumbakast (rõhuandur G5, pumba
  otsus, JSON telemeetria iga 10 ms). Kontrollitud: telemeetria `t` vahe täpselt 10 ms.
- `Settings & tests` osa ülaosas on rida rõhu, pumba režiimi, pumba oleku ja valitud
  tähega (`GET /state` → `lab`), uueneb iga 1 s. Nutikate lahenduste L2 rõhuanduri lugem
  on sellega juba lehel.
- Tähe nupurežiim on vaikimisi sees: ekraanil suur täht, selle all rõhk ja pump. Saatmise
  olek ekraanil: `SENDING` → `SENT` (HTTP) või `SENT USB` (kui jaama aadressi pole).
- Täht saadetakse ka USB kaudu JSON reana; laboriarvutil pole Wi-Fi-d, seega kasutasime
  03.10.26 USB kanalit (`letter_channel.md`). Atomi captive portalit ja pildi saatmist
  kontrolliti Android-telefoniga; Wi-Fi-põhist tähekanalit ja iPhone'i ei kontrollitud.
- Serial käsk `boot` näitab viimase taaskäivituse põhjust (nt `power-on / EN` = RESET nupp).
