# AtomS3 püsivara

- Alus: KKallas/ESP32-Image-Server, `atom-image-server`
- Kasutatav PlatformIO board: `m5stack-atoms3`
- Framework: Arduino
- Display/library: M5Unified
- Serial: 115200
- Projekti `common/` failid on toodud firmware kausta sisse, et projekt oleks selles repos iseseisvalt ehitatav.
- Algkoodis olnud `../common` include tee muudeti kujule `$PROJECT_DIR/common`.
- Captive portali tarkvaraline teostus on lisatud; kontroll reaalse telefoniga on TODO.
- Settings/test osa tarkvaraline teostus on lisatud; kontroll reaalsel AtomS3-l on TODO.
- Reaalset flashimist ega nende muudatuste riistvaratesti ei ole veel tehtud.

Source: [https://github.com/KKallas/ESP32-Image-Server](https://github.com/KKallas/ESP32-Image-Server)

## Ühendatud püsivara — 03.10.26

Sama AtomS3 teeb nüüd mõlema aine töö: Andmehõive tark pumbakast (rõhuandur
G5, pumba otsus, JSON protokoll iga 10 ms) ja Nutikate lahenduste leht
(Wi-Fi, captive portal, pildid, täht). Andmehõive moodulid on kopeeritud
`src/pump/` ja `include/` alla muutmata (ainult `pollCommand` → `parseCommand`,
sest serial-rida loeb nüüd `main.cpp`).

- **Tuum 1** (`loop()`): nupp, serial-sisend, andur + pump + telemeetria iga
  10 ms, ekraan. Ei blokeeri kunagi, seega PC 500 ms watchdog ei rakendu Wi-Fi
  tõttu.
- **Tuum 0** (`netTask`): Wi-Fi, veebileht, DNS, tähe HTTP saatja, žestide
  tegevused (võivad blokeerida sekundeid).
- Serial: JSON read on andmed (telemeetria, täht, zero); iga inimloetav logi
  algab `# `-ga.
- Tähe nupurežiim (vaikimisi sees): ekraanil suur täht + rõhk + pump. Režiim
  välja: pildid ja sloti žestid nagu varem.
- Lehe „Settings & tests“ osas on rõhu/pumba/tähe olek (uueneb 1 s).

Kontrollitud 03.10.26 reaalsel AtomS3-l: telemeetria 203 rida 2 s jooksul,
`t` vahed täpselt 10 ms; SoftAP `AtomFramer` 192.168.4.1 tõusis; `ip` käsk
töötas USB kaudu. Pumba 10 tõstmist ühendatud püsivaraga: TODO.

Build Windowsis: Arduino-ESP32 käsurida ületab ArduinoJsoni lisamisel
Windowsi 32 767 märgi piiri („CreateProcess: No such file or directory“).
Lahendus ilma adminiõigusteta: lühike junction ja `PLATFORMIO_CORE_DIR`:

```powershell
cmd /c mklink /J C:\Users\<kasutaja>\pio C:\Users\<kasutaja>\.platformio
$env:PLATFORMIO_CORE_DIR = "C:\Users\<kasutaja>\pio"
pio run -t upload --upload-port COM4
```

- RAM: 84 388 / 327 680 B (25,8%), Flash: 1 219 901 / 3 342 336 B (36,5%)

Tagasi Andmehõive püsivarale (kaitsmise varuplaan):
`data-acquisition-course/data-acquisition/lab1/src/firmware` → `pio run -t upload`.

## Kontrollitud build — 12.09.26

- PlatformIO Core: 6.2.0
- environment: `atoms3r`
- board: `m5stack-atoms3`
- build: SUCCESS
- RAM: 83 580 / 327 680 B (25,5%)
- Flash: 1 166 073 / 3 342 336 B (34,9%)
- build tehti ilma AtomS3 ühendamiseta
- uploadi ei tehtud
- selle build'i ajal ei olnud captive portal veel lisatud

## Tarkvaraline build — 13.09.26

- PlatformIO Core: 6.2.0
- environment: `atoms3r`
- board: `m5stack-atoms3`
- build: SUCCESS
- RAM: 83 716 / 327 680 B (25,5%)
- Flash: 1 176 065 / 3 342 336 B (35,2%)
- build sisaldab captive portali ning seadete ja ekraanitesti tarkvaralist teostust
- build tehti ilma AtomS3 ühendamiseta
- uploadi ei tehtud
- kontroll reaalsel AtomS3-l ja telefonidel on TODO
