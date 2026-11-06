# Kontrollitud Lab 2 letter-katse

See on käivitusjuhend, mitte päriskatse tulemus. Live-rada kasutab ainult
olemasolevat Lab 1 jaama: Atom → Lab 2 adapter → Lab 1 HTTP → MG400.
Vaikimisi on täitmine keelatud; `--allow-mock-jobs` jääb ainult mock-režiimiks.
USB terminaltulemuse taastamist ei ole lisatud. Internetikatkestuse järel
kordab Atom juba NVS-i salvestatud tulemuse saatmist olemasoleva retry kaudu.

## Enne käivitamist

1. Nimetatud vastutaja on ruumis füüsilise E-stopi juures; tööala on tühi ja
   kogu robot ning tööala üldkaameras nähtav. Järgi [ohutuskokkulepet](safety.md).
   Enne liikumist öeldakse „liigub“; käed jäävad 440 mm ulatusest välja.
2. Peata Lab 1 Atom bridge, teised Lab 2 adapterid, slot-picker, jog/teach,
   tekstijoonistamine ja teised CLI/programmid, mis võivad liikumiskäske saata.
   Jäta ainult üks lokaalne mg400-base server ja üks Lab 1 jaam. mg400-base
   UI/teised brauserid ei tohi samal ajal käske saata; välista teiste arvutite
   otsene ligipääs robotile. MG400 ühendamine ja lubamine toimub ainult kohapeal.
3. Kontrolli käesoleva paigalduse kalibratsiooni. Esimene katse on ilma
   proovitükita, 20% kiirusel ja tööriist kogu teekonnal vähemalt 20 mm
   tööpinnast kõrgemal. Mõõda ja kasuta eraldi kontrollitud õhukatse
   kalibratsioonifaili, kus ka `pen_down_z` jääb õhku. Repos olevad 03.10
   koordinaadid ja `pen_down_z` ei tõenda tänase õhukatse ohutust.
4. Kontrolli Atomil NORMAL-püsivara, aktiivse claim'i ja pending result'i
   puudumist ning jaama tegelikku USB-porti. Sulge Serial Monitor ja muud
   pordi kasutajad. See juhend ei anna luba firmware upload'iks ega NVS reset'iks.
5. Kontrolli postkontori järjekorda: ainult eelnevalt kokku lepitud kehtiv
   `letter A`, mitte vanad või mitu ootavat tööd. Esimest tööd ei looda enne,
   kui vastutaja on kogu ahela valmisolekut kinnitanud.

`--confirm-local-safety` ja `--confirm-exclusive-control` on operaatori
selgesõnalised kohalikud kinnitused, mitte automaatne roboti või teiste
protsesside kontroll. Kui ainujuhtimist ei saa kinnitada, live-katset ei alustata.
Faililukk kaitseb ainult sama kanoniseeritud SQLite-teega koostöötavaid
adaptereid ühes arvutis; see ei lukusta Lab 1, mg400-base'i ega teist arvutit.

## Laboriarvuti käivituskäsud

Aktiveeri ettevalmistatud Python-keskkond, kus on Lab 1 ja Lab 2 sõltuvused.
Järgmised PowerShelli käsud on ainult kohapealseks, eraldi lubatud katseks.
mg400-base peab olema juba kontrollitult käivitatud lokaalsel aadressil
`http://127.0.0.1:8000`; kui port erineb, kasuta tegelikult kontrollitud porti.

Esimene terminal, repo juurkaustast:

```powershell
cd smart-solutions/lab1
$airCalibration = Read-Host "Kontrollitud ohukatse kalibratsiooni absoluutne failitee"
python src/station.py --host 127.0.0.1 --port 5000 --execute --mg400-url http://127.0.0.1:8000 --calibration "$airCalibration"
```

Lab 1 peab kasutama selle tööpuu uut `GET /api/letter/status` endpoint'i,
üht protsessi ja väljalülitatud reloader'it. Ära käivita teist execute-jaama.
Lab 1 kontrollib enne täitmist kalibratsiooni ja MG400 safe/ready olekut;
jaama `--execute` ei ole roboti automaatne enable.

Teine terminal, sama repo juurkaustast ja aktiveeritud keskkonnaga:

```powershell
cd smart-solutions/lab2
$atomPort = Read-Host "AtomS3R tegelik USB-port, naiteks COM4"
python -m src.station_adapter --port "$atomPort" --database data/station_jobs.sqlite3 --allow-live-letter --confirm-local-safety --confirm-exclusive-control --lab1-url http://127.0.0.1:5000
```

Kasuta iga kord sama püsivat SQLite-baasi; ära loo interlock'i vältimiseks uut
baasi ega kustuta olemasolevat. OS-lukk saadakse enne SQLite recovery't ja
säilib USB-tsükli ning HTTP session'i sulgemise lõpuni. Ilma mõlema kohaliku
kinnituseta live-käivitus keeldub enne baasi või USB avamist. Aktiivne SQLite
interlock blokeerib live-käivituse; sama töö ID ei käivitu uuesti.

Live-režiimis on ainult `letter`. `pick_place` keeldub ja pumpa ei juhita.
HTTP-klient kasutab päris `requests.Session` objekti, ainult loopback-aadressi,
ilma proxy, redirect'i ja automaatse retry'ta. Üks POST kinnitab ainult
vastuvõtmise; `done` tuleb alles vastava execute-režiimi `completed` GET-i ja
eduka SQLite commit'i järel. Timeout, ühenduse kadu või muu ebaselgus jätab
interlock'i alles; uus töö ei tohi liikuda.

## Tulemused ja katkestused

- Kontrolli esimest `A` jada kohapeal. HTTP 202 ega Serial write ei tõenda
  füüsilist lõpetamist või Atomi poolt tulemuse vastuvõtmist.
- Internetikatkestuse katseks jäta USB ja kohalik robotivõrk ühendatuks.
  Pärast kohalikku vastuvõttu peab jaam töö lõpetama ning Atom hoidma tulemust
  NVS-is kuni võrgu taastumiseni. [Ohutuskokkulepe](safety.md) nõuab kolme
  päriskatset; tulemused, aeg ja töö ID tuleb alles laboris kirja panna.
- USB katkestuse või reboot'i järel ära saada liikumise JSON-i uuesti ega
  tõlgenda puuduvat vastust kui täitmata tööd. Terminaltulemuse USB recovery
  puudub; peata uute katsete ettevalmistus ja kontrolli kohapeal robotit,
  SQLite tulemust ja Atomi aktiivset/pending olekut. Atom võib pärast reboot'i
  salvestada `ambiguous_after_reboot` keeldumise.

## Interlock'i kohalik vabastamine

Automaatset vabastamist pärast viga ei ole. Sulge adapter ning kinnita
füüsiliselt, et robot on peatunud ja ootel liikumisi ei ole; kontrolli ka
Lab 1 taustatöötajat. Alles siis kasuta Lab 2 kataloogis kohalikku Pythonit:

```python
from src.station_process_lock import StationProcessLock
from src.station_store import StationJobStore

with StationProcessLock("data/station_jobs.sqlite3") as lock:
    store = StationJobStore(lock.database_path)
    job_id = store.interlock_job_id()
    print(job_id, store.get(job_id) if job_id is not None else None)
    confirmation = input("Robot peatunud, ootel liikumisi pole; kirjuta KINNITAN: ")
    if job_id is not None and confirmation == "KINNITAN":
        store.confirm_safe(job_id, local_confirmation=True,
                           robot_stopped=True, no_pending_motion=True)
```

See ei kontrolli robotit automaatselt, ei kustuta ajalugu, ei taasta USB
tulemust ega korda vana tööd. Vabastamine ei ole luba uut katset alustada,
kuni Atomi ja jaama eelmise töö olekud pole selged. Avalikku unlock/enable
endpoint'i ei ole.
