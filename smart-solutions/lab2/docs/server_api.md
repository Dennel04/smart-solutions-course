# Lab 2 postkontori API leping

> **Olek:** allpool kirjeldatud API on lokaalses Flask-serveris teostatud ja
> automaattestidega kontrollitud. See ei tõenda dropleti, päris AtomS3,
> lokaalse jaama ega MG400 integratsiooni toimimist.

## Piirid ja usaldusmudel

```text
kasutaja/brauser
      |
   HTTPS + kasutaja autentimine
      v
dropleti postkontor
      ^
      | HTTPS polling + Atomi autentimisvõti
      v
    Atom
      |
   Labori 1 lokaalne kanal
      v
    jaam
      |
   MG400 lokaalne API
```

Põhireeglid:

- droplet ei algata ühendust Atomi, jaama ega MG400-ga;
- droplet ei ole jaama lehe relay/proxy ning Lab 2 arhitektuuris ei ole VPN-i
  ega tunnelit dropleti ja jaama vahel; otsene kaugjuurdepääs jaamale kuulub
  Lab 3 ulatusse;
- Atom algatab kõik postkontori polling- ja tulemuspäringud väljapoole;
- postkontor võtab vastu ainult whitelist'is olevaid kõrgtaseme töid, mitte
  koordinaate, trajektoore, DO väärtusi ega otseseid liikumiskäske;
- jaam teeb kohaliku valideerimise ja on ainus komponent, mis tohib MG400-le
  liikumiskäske saata;
- kaameravood ei lähe postkontorisse; need jäävad kohalikku võrku ja neid
  vahendab vajadusel autentitud jaama leht;
- kasutajaleht ja Atomi API on loogiliselt eraldi marsruutide, autentimise ja
  õigustega;
- Atomi autentimisvõti salvestatakse Atomis, mitte lähtekoodis ega repos;
- kasutajaleht nõuab autentimist;
- production-transpordi siht on HTTPS; HTTP sobib ainult lokaalseks
  arenduseks ilma päris saladuste või robotitäitmiseta.

## Whitelist

| `job` | Lubatud `arg` | Olek |
| :--- | :--- | :--- |
| `letter` | objekt väljaga `letter`, üks suurtäht `A`–`Z` | serveris lubatud ja testitud; hardware integration TODO |
| `pick_place` | tulevane eelnevalt õpetatud lähte- ja sihtkoha sümboolne nimi | FUTURE/HARDWARE-PENDING; server lükkab praegu tagasi |

`pick_place` ei tohi sisaldada kasutaja antud X/Y/Z/R koordinaate. Selle
teostamisel võib jaam vastu võtta ainult eelnevalt lokaalselt õpetatud ja
lubatud positsioonide nimesid. Töö ei ole veel füüsiliselt realiseeritud.

Whitelist'i mittekuuluv `job`, tundmatu argument, lisaväli, liiga pikk tekst,
vale tüüp või lubamatu väärtus lükatakse tagasi. Vaikimisi lubamist ei ole.

## Töö kirje

| Väli | Tüüp | Tähendus |
| :--- | :--- | :--- |
| `id` | läbipaistmatu string | serveri loodud püsiv sõnumi/töö ID |
| `job` | string | whitelist'i töö nimi |
| `arg` | objekt | töö tüübile vastav rangelt valideeritav argument |
| `created_at` | UTC ajatempel | serveris loomise aeg |
| `expires_at` | UTC ajatempel | viimane hetk, millal tööd võib claim'ida |
| `status` | enum | üks allpool määratud olek |
| `result` | objekt või `null` | eduka täitmise tulemus ilma saladusteta |
| `reason` | string või `null` | keeldumise/aegumise/vea masinloetav põhjus |

Ajatemplid on UTC ISO 8601 kujul. Server määrab `id`, `created_at` ja
`expires_at`; kliendi kell ei otsusta TTL-i.

## Elutsükkel

```text
queued --Atom claim--> claimed --lokaalne töö õnnestub--> done
   |                      |
   +-- TTL möödub ------> expired
                          +-- lokaalne station keeldub --> refused
```

| Olek | Tähendus |
| :--- | :--- |
| `queued` | valideeritud töö ootab Atomi polli |
| `claimed` | üks Atom on töö püsiva ID-ga vastu võtnud, kuid jaam ei ole täitmist kinnitanud |
| `done` | jaam lõpetas töö edukalt |
| `refused` | töö ei käivitunud või peatati selge ohutus-/valideerimispõhjusega |
| `expired` | TTL möödus enne täitmise algust; töö ei tohi midagi liigutada |

Terminalolekud on `done`, `refused` ja `expired`. Neist ei minda tagasi
`queued` olekusse. Uus katse vajab uut töö kirjet ja uut kasutaja otsust.

### TTL ja aegumine

- server kontrollib TTL-i nii polli kui claim'i ajal;
- `expires_at <= server_now` muudab veel alustamata töö olekuks `expired`;
- Atom kontrollib saadud `expires_at` väärtust uuesti, kuid serveri otsus on
  autoriteetne;
- jaam kontrollib TTL-i vahetult enne täitmise algust;
- aegunud töö kohta võib saata ACK/result'i, kuid mitte liikumiskäsku;
- juba `claimed` töö TTL ei ole kaugjuhitav stoppsignaal. Kui Atom on töö enne
  aegumist vastu võtnud ja station on selle lokaalselt aktsepteerinud, lõpetab
  station tervikliku töö ka internetikatkestuse korral.

## Teostatud REST endpoint'id

### Kasutaja API

Kasutajaliides ja `/api/jobs*` endpoint'id nõuavad HTTP Basic autentimist.
Parool tuleb keskkonnamuutujast. Production'is peab nende ees olema HTTPS.

| Meetod ja tee | Otstarve |
| :--- | :--- |
| `GET /` | minimaalne kasutajaleht: Atom status, töö loomine ja tööde ajalugu |
| `POST /jobs` | HTML-vormi `letter` töö loomine |
| `POST /api/jobs` | valideeri whitelist'i töö ja lisa see järjekorda |
| `GET /api/jobs/{id}` | kuva ühe töö olek ja tulemus |
| `GET /api/jobs` | kuva hiljutised tööd ja Atomi olek |
| `GET /api/status` | kuva Atomi `last_seen`, online/stale/offline ja serveri aeg |

### Atomi API

Kõik `/api/atom/*` endpoint'id nõuavad päist
`Authorization: Bearer <ATOM_API_KEY>`. Võtit ei saadeta query-stringis ega
logita. Production'is kasutatakse HTTPS-i.

| Meetod ja tee | Otstarve |
| :--- | :--- |
| `POST /api/atom/poll` | heartbeat/status ja järgmise töö atomaarne claim |
| `POST /api/atom/result` | raporteeri idempotentselt `done` või `refused` |
| `GET /api/atom/jobs/{id}` | loe sama töö autoriteetne serveriolek pärast katkestust |

Poll on korraga heartbeat ja töö küsimine. Kui tööd ei ole, vastab server
edukalt `job: null`; see ei ole viga.

## Example: töö loomine

```http
POST /api/jobs
Content-Type: application/json
```

```json
{
  "job": "letter",
  "arg": {"letter": "A"},
  "ttl_seconds": 60
}
```

Example-vastus:

```json
{
  "id": "example-job-id",
  "job": "letter",
  "arg": {"letter": "A"},
  "created_at": "2030-01-01T12:00:00Z",
  "expires_at": "2030-01-01T12:01:00Z",
  "status": "queued",
  "result": null,
  "reason": null
}
```

Kuupäevad ja ID on ainult formaadinäited, mitte mõõtmised ega production-andmed.

## Example: Atomi poll ja heartbeat

```json
{
  "device_id": "example-atom-id",
  "poll_interval_ms": 1000,
  "atom_uptime_ms": 123456,
  "station": {
    "reachable": true,
    "robot_state": "locally_enabled"
  }
}
```

Example-vastus töö olemasolul:

```json
{
  "server_time": "2030-01-01T12:00:10Z",
  "job": {
    "id": "example-job-id",
    "job": "letter",
    "arg": {"letter": "A"},
    "created_at": "2030-01-01T12:00:00Z",
    "expires_at": "2030-01-01T12:01:00Z",
    "status": "claimed"
  }
}
```

`poll_interval_ms` on Atomi tegelik kasutatud väärtus ja salvestatakse
heartbeat'i juurde. Mõõtmistes kirjutatakse tegelik intervall iga rea juurde.
Production-vaikeväärtus on TODO — real test required.

## Heartbeat, `last_seen` ja roboti olek

- server uuendab autentitud polli vastuvõtmisel Atomi `last_seen` väärtuse;
- online/offline tuletatakse serveri kellast, viimasest nähtud ajast ja
  kokkulepitud polling-intervallist;
- offline-piir peab lubama vähemalt ühe ajutise ebaõnnestumise ja määratakse
  pärast päris võrgu katseid;
- `robot_state` on jaama raporteeritud kirjeldav olek, mitte dropleti käsk;
- minimaalsed kavandatud väärtused: `unknown`, `offline`, `locally_disabled`,
  `locally_enabled`, `busy`, `fault`;
- `locally_enabled` saab tekkida ainult ruumis oleva inimese tegevusest;
  droplet ega Atom ei paku remote-enable käsku.

## Idempotentsus ja kordused

1. Server loob ühe püsiva `id` ja muudab `queued → claimed` atomaarse
   andmebaasioperatsiooniga. Sama tööd ei anta paralleelselt teisele pollile.
2. Atom salvestab aktiivse töö ID enne selle edastamist jaamale. Ta kasutab
   kõigis korduskatsetes muutmata ID-d.
3. AtomS3 lisab Labori 1 serial-JSON sõnumile stabiilse `job_id`. Lab 2
   tarkvaraline jaamaadapter hoiab ID ja `session + seq` olekut SQLite'is.
   Kui ID on juba lokaalselt lõpetatud, tagastab ta salvestatud tulemuse ega
   kutsu executor'it uuesti. Päris MG400 executor integration on TODO.
4. `claimed` tähendab ainult seda, et server andis töö Atomile. Server ei
   näita `executing` olekut, sest praegune API ei saa seda usaldusväärselt teada.
5. Atom salvestab terminaltulemuse enne aktiivse claim'i kustutamist ja saadab
   sama terminaltulemuse sama ID-ga uuesti kuni `POST /api/atom/result` saab
   eduka vastuse. Serveri tulemusuuendus on idempotentne.
6. Server ei muuda vastuolulist terminalolekut vaikides. Konflikt logitakse ja
   tagastatakse veana inimese uurimiseks.

## Atom → station protokoll

Põhitransport on sama põhimõttega nagu Lab 1 laboriarvutis: üks programm omab
AtomS3 USB serial-porti, baud on seadistatav (vaikimisi 115200) ja iga sõnum
on üks reavahetusega lõpetatud JSON objekt. Lab 2 firmware saadab:

```json
{"letter":"A","session":"post-office","seq":1,"atom_sent_ms":1234,"job_id":"example-job-id"}
```

| Väli | Reegel |
| :--- | :--- |
| `letter` | täpselt üks suurtäht `A`–`Z`; mock executor kontrollib lisaks, et Lab 1 `letters.json` sisaldab trajektoori |
| `session` | mittetühi kuni 64 märgi pikkune Lab 1-ga ühilduv session |
| `seq` | mittenegatiivne täisarv; koos session'iga vana kanali duplicate key |
| `atom_sent_ms` | valikuline mittenegatiivne Atomi uptime; seda ei võrrelda station'i kellaga |
| `job_id` | kohustuslik serveri stabiilne ID, 1–80 märki (`A–Z`, `a–z`, number, `.`, `_`, `-`) |

Lisaväljad lükatakse tagasi. Seega ei võta adapter vastu koordinaate, kiirust,
pumba väärtust, trajektoori ega muud direct-motion käsku.

Station → Atom vastus kasutab täpselt firmware poolt loetavat envelope'i:

```json
{"post_office_result":{"id":"example-job-id","status":"done"}}
```

või:

```json
{"post_office_result":{"id":"example-job-id","status":"refused","reason":"robot_not_enabled"}}
```

Stabiilsed station'i keeldumispõhjused on `invalid_message`, `invalid_letter`,
`duplicate_conflict`, `robot_not_enabled`, `executor_busy`,
`ambiguous_after_restart` ja `execution_failed`. Vigase JSON-i või puuduva
`job_id` puhul ei ole ID-d võimalik kajastada ning adapter vastab tühja `id`
väärtusega; firmware ei käsitle seda aktiivse töö terminaltulemusena.

SQLite'i kirje luuakse olekus `in_progress` enne executor'i väljakutset.
Terminaltulemus püsib restardi üle. Sama `job_id` ja sama payload tagastavad
sama tulemuse; sama ID teise payload'iga või sama `session + seq` teise ID-ga
annab `duplicate_conflict`. Pärast protsessi restarti muutub pooleli olnud
`in_progress` fail-safe olekuks `refused / ambiguous_after_restart` ning seda
ei käivitata automaatselt uuesti.

Praegune `MockLetterExecutor` ei impordi MG400 klienti ega loo robotivõrgu
ühendust. Adapteri default on lokaalselt keelatud; `--allow-mock-jobs` lubab
ainult kontrollitud mock-täitmise. Tulevane päris executor peab eraldi tõendama
lokaalse enable'i, roboti teadaoleva safe/ready oleku ja ainsa motion-saatja
omandi. Päris USB, AtomS3 ja MG400 otsast lõpuni kontroll on TODO.

## Vigased ja keeldutud tööd

- kasutaja API lükkab skeemile mittevastava või whitelist'i mittekuuluva töö
  tagasi enne järjekorda lisamist;
- kui Atom või jaam avastab lisapiirangu rikkumise, raporteerib ta `refused`
  ja masinloetava `reason` väärtuse;
- serveri/Atomi põhjused ja station'i stabiilne nimekiri on eri piiride
  masinloetavad väärtused; station'i väärtused on fikseeritud ülal;
- hostile input'it käsitletakse andmetena: pikkus, tüüp, lubatud märgid,
  struktuur ja vahemikud valideeritakse; seda ei panda shell-käsku, failiteesse
  ega HTML-i ilma turvalise kodeerimiseta;
- tundmatu, vigane või aegunud töö ei liiguta robotit.

## Ühenduse katkemine ja tulemuse retry

- postkontori kadumine ei katkesta juba Atomile edastatud ja station'is
  lokaalselt vastu võetud terviklikku kõrgtaseme tööd;
- station lõpetab juba vastu võetud töö oma kohalike ohutusväravate järgi;
  internetiühendus ei ole otsene motion-control kanal;
- safe-stop direct remote-control ühenduse kadumisel kuulub Lab 3, mitte selle
  postkontori Lab 2 semantikasse;
- Atom säilitab aktiivse töö ID, viimase jaamalt saadud oleku ja saatmata
  terminaltulemuse üle ajutise internetikatkestuse;
- ühenduse taastumisel kordab Atom sama tulemuse saatmist sama ID-ga fikseeritud
  kahe sekundi retry-intervalliga;
- uut tööd ei claim'ita, kuni eelmise töö lõppolek on lahendatud;
- pärast Atom'i restarti ei käivitata ebaselget aktiivset claim'i uuesti. See
  muudetakse `ambiguous_after_reboot` põhjusega saatmata `refused` tulemuseks.

Serveripoolne idempotentsus ning AtomS3 NVS-puhvri tarkvaraalus on teostatud.
Päris seadme katkestuskatse on veel TODO.

## Kohalik teostus ja konfiguratsioon

Server kasutab Flaski ja SQLite'i. SQLite valiti, sest see säilitab töö ID,
claim'i, terminaltulemuse ja `last_seen` väärtuse serveri restardi järel,
kuid ei vaja eraldi production-andmebaasi. Claim toimub ühes
`BEGIN IMMEDIATE` transaktsioonis; lõpetatud tööd ei panda uuesti järjekorda.

Kohalik käivitus nõuab vähemalt:

- `ATOM_API_KEY` — Atomi bearer-võti;
- `POST_OFFICE_PASSWORD` — kasutajaliidese parool;
- `POST_OFFICE_USER` — kasutajanimi, software default `lab-user`;
- `POST_OFFICE_DB` — valikuline SQLite faili tee;
- `JOB_TTL_SECONDS` — software default 60 s;
- `JOB_MAX_TTL_SECONDS` — software default 3600 s;
- `ATOM_STALE_SECONDS` ja `ATOM_OFFLINE_SECONDS` — software default 10 s / 30 s.

Ilma Atomi võtme või kasutaja paroolita server ei käivitu. Need software
default'id ei ole labori lõplikud väärtused: final TTL ja olekupiirid vajavad
reaalset võrguotsust ja katset.

## Logimine ja saladused

Logida võib töö ID, olekumuutuse, aja, seadme ID pseudonüümi ja veakoodi.
Logida ei tohi Atomi võtit, kasutaja parooli, sessiooniküpsist, SSH privaatvõtit
ega täielikke autoriseerimispäiseid.
