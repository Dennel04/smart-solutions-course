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
3. Tulevane jaama adapter peab hoidma töö ID järgi vastuvõtu- ja täitmislogi.
   Kui ID on juba lokaalselt vastu võetud või lõpetatud, ei käivita ta uut
   MG400 töötajat. See adapter on TODO — Atom/MG400 integration required.
4. `claimed` tähendab ainult seda, et server andis töö Atomile. Server ei
   näita `executing` olekut, sest praegune API ei saa seda usaldusväärselt teada.
5. Kui Atom ei tea pärast katkestust, kas tulemus jõudis serverisse, küsib ta
   esmalt `GET /api/atom/jobs/{id}` ja saadab sama terminaltulemuse sama ID-ga
   uuesti. Serveri tulemusuuendus on idempotentne.
6. Server ei muuda vastuolulist terminalolekut vaikides. Konflikt logitakse ja
   tagastatakse veana inimese uurimiseks.

## Vigased ja keeldutud tööd

- kasutaja API lükkab skeemile mittevastava või whitelist'i mittekuuluva töö
  tagasi enne järjekorda lisamist;
- kui Atom või jaam avastab lisapiirangu rikkumise, raporteerib ta `refused`
  ja masinloetava `reason` väärtuse;
- soovituslikud põhjused: `unknown_job`, `invalid_arg`, `expired`,
  `station_offline`, `robot_not_locally_enabled`, `robot_busy`,
  `safety_gate_failed`, `local_mapping_missing`;
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
- ühenduse taastumisel kontrollib Atom serveri olekut ja kordab sama tulemuse
  saatmist eksponentsiaalse või piiratud backoff'iga;
- uut tööd ei claim'ita, kuni eelmise töö lõppolek on lahendatud;
- pärast Atom'i restarti tuleb püsivast salvestusest taastada lahendamata töö
  ID või jätta süsteem ohutult käsitsi lahendatavasse olekusse. Teostusviis on TODO.

Serveripoolne sama tulemuse kordussaatmine on teostatud ja idempotentne.
AtomS3 püsiv puhver ning päris katkestuskatse on veel TODO.

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
