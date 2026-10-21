# MG400 ühine omanik: software-only prototüüp

## Piir ja lähtekood

[`src/ownership_model.py`](../src/ownership_model.py) modelleerib ühe kohaliku
koordinaatori juhtimisõigust SQLite'is. Kõik katsed kasutavad ajutist baasi,
sünteetilisi kliente, kellaaegu ja kinnitusi. **See ei ole production-lukk ega
MG400 liikumisluba.** `Grant`, `StepAdmission` ja `Snapshot` sisaldavad
muutumatut `physical_execution_allowed=False` välja.

Moodul ei loo HTTP/TCP klienti, ei impordi MG400 koodi ega saada liikumise,
pumba, enable'i, ClearError'i või stop'i käske. Lab 1, StationAdapter,
StationJobStore, Atom ja production jäävad muutmata. `PickPlacePreflightExecutor`
tagastab endiselt `refused`; pumba- ja ühise omaniku blokeeringud jäävad alles.
Taust: [pick-place leping ja laboriblokeeringud](pick_place_executor.md).

Kontrollitud fork on `Dennel04/mg400-base`, `lab-jog`, commit
`982ebf8533c4dfe39ad62fb570e339e3e918bcb8`:
[server.py](https://github.com/Dennel04/mg400-base/blob/982ebf8533c4dfe39ad62fb570e339e3e918bcb8/mg400/server.py),
[cli.py](https://github.com/Dennel04/mg400-base/blob/982ebf8533c4dfe39ad62fb570e339e3e918bcb8/mg400/cli.py).
Serveri `_robot_lock` kaitseb ühenduse vahetamist. UI teised käsurajad ei küsi
terve tööjada omanikku. CLI `_connect` loob oma `DobotMG400` TCP ühenduse.
[Lab 1 station](../../lab1/src/station.py) kasutab protsessisisest
`EXECUTION_LOCK` lukku ning [MG400Client](../../lab1/src/mg400_client.py)
saadab HTTP päringuid ilma ownership-token'ita.

## Olekud ja üleminekud

| Olek | Tähendus ja lubatud järgmine samm |
| :--- | :--- |
| `BLOCKED` | Algkäivitus või kohalik blokeering. Ainult operaatori kinnitused avavad `FREE`. |
| `FREE` | Omanikku pole. Atomaarne `reserve` annab ühele omanikule `RESERVED`. |
| `RESERVED` | Omanik hoiab tervet jada; ühtegi sammu ei tohi veel modelleerida. `activate` annab `ACTIVE`. |
| `ACTIVE` | Sama omanik modelleerib sammud ühe kaupa. Kinnitatud tervikjada vabastab `FREE`. |
| `UNCERTAIN` | Crash, restart, timeout, sidekadu või ebaselge tulemus. Uued sammud ja omanikud on keelatud. |

`block` annab vaba süsteemi korral `BLOCKED`; olemasoleva omaniku korral
annab see `UNCERTAIN`. Vigane või tagasihüpanud monotoonne kell blokeerib samuti loa.
Lease'i aegumine ei anna `FREE`. Võrgu taastumine ei ava luba ega jätka jada.
Prototüüp ei saada rikkeseisundis automaatselt `off`/`blow`, sest see võiks
detaili vabastada. Füüsiline hädastopp jääb ainsaks usaldatud stop'iks.

### Claim, fencing ja terve jada

Omanik on `Owner(client_id, session_id, job_id)`. `reserve` kontrollib
identifikaatoreid ning teeb `BEGIN IMMEDIATE` tehingus claim'i. Kaks korraga
taotlevat klienti saavad ühe võitja. Teine saab `not_free`; kasutatud job ID
saab `duplicate_job_id`, ka pärast lõppu või restarti. Mudel ei korda tööd.
Prototüüp ei autendi klienti ega operaatorit; päris gateway peab siduma need
ID-d usaldatud kohaliku sessiooni ja operaatori antud tööloaga.

Iga uus claim, loa tühistamine, vabastamine ja koordinaatori restart kasvatab
püsivat fencing token'it. Meetodid kontrollivad kliendi, sessiooni, job ID,
token'i ja koordinaatori epoch'i vastavust. Vana token või võõras omanik ei
tohi aktiveerida, uuendada heartbeat'i, alustada/kinnitada sammu ega lõpetada
jada. Andmebaasi kirjutamisõigus ja ID teadmine ei ole päris autentimine.

`admit_step` salvestab `PENDING` sammu enne hüpoteetilist saatmist. See
tagastab ainult modelleerimise kirje, mitte käivitatava callback'i või käsu.
Teist sammu ei võeta vastu enne esimese kinnitamist; sama step ID ei kordu.
Omanik jääb alles ka kinnitatud sammude vahele. Üksiku HTTP päringu mutex
ei tagaks seda omadust.

### Kinnitus ja vabastamine

`StepEvidence` vajab eraldi `acknowledged`, `feedback_fresh`,
`effect_confirmed`, `no_fault`, `robot_stopped` kinnitusi. Ainult HTTP 200
või DO ack ei täida neid tingimusi. Vigane või poolik kinnitus viib
`UNCERTAIN` olekusse. Pumba puhul ei tähenda `pump_mode=suck` kinnitatud
vaakumit või detaili hoidmist.

`complete` nõuab vähemalt üht kinnitatud sammu, ootel sammu puudumist ning
`CompletionEvidence` kõiki lippusid: tervikjada lõpetatud, värske tagasiside,
kinnitatud seisak, ohutu väljundite seis ja veatu olek. Alles siis märgib
mudel töö `COMPLETED` ja vabastab omaniku. Puudulik lõpptulemus annab
`UNCERTAIN`, mitte vale `done` või vaba robotit.

Need on **sünteetilised väited**, mida praegu test sisestab. Mudel ei mõõda
seisakut ega valideeri roboti trajektoori, sensori allikat või proovide
värskust. Mudel ei tea täieliku plaani sammude arvu; tulevane usaldatud
planner peab siduma tõendi konkreetse plaani ja selle kõigi sammudega.
Kasutaja antud booleane ei tohi kunagi võtta production-tõendina.

### Lease, crash ja restart

Heartbeat pikendab lease'i kuni absoluutse sequence deadline'ini; see ei
pikenda tervikjada ajapiiri. Kestuste 1 tunni ülempiir on tarkvarasisendi
piirang, mitte laboris mõõdetud ohutu ooteaeg. Kõik ajad testides on
sünteetilised. `snapshot` ja muud mudelioperatsioonid kontrollivad kellaaega;
taustal watchdog'i ei tööta. Päris gateway vajab eraldi testitud watchdog'i.

`OWNER_CRASH`, `CONNECTION_LOST`, `UNKNOWN_RESULT` ja `COMMAND_FAILED`
tühistavad loa. Timeout'i avastanud ebaõnnestuv operatsioon salvestab
`UNCERTAIN` ka siis, kui kutsuja saab keeldumise. Deadline'i möödumist ei
tohi transaction rollback'iga kogemata tühistada.

Iga uus `OwnershipModel` samal baasil modelleerib **koordinaatori restarti**,
mitte uut klienti. Kliendid jagavad üht koordinaatorit. Uus epoch tühistab
vana instantsi; varasem RESERVED/ACTIVE töö jääb `UNCERTAIN`. Ka varem
vaba koordinaator alustab pärast restarti `BLOCKED`. Pooleli sammud ja job ID
ajalugu säilivad, automaatset jätkamist ega DB reset'i ei ole.

`operator_clear` nõuab kehtivat token'it, operaatori ID-d, kohalikku kinnitust,
kinnitatud seisakut, saatmata/pooleli käskude puudumist ning ohutut väljundite
seisu. Kõik kinnitused peavad olema päris `True`, mitte tekst või arv 1.
Vana kinnituse token ei ava uuemat rikkeseisundit. Operaator ei saa selle
meetodiga aktiivset tööd üle võtta. Pärast `UNCERTAIN` vabastamist ei saa
vana job ID uuesti käivitada; vana töö jääb ajaloos ebaselgeks.

## Üks päris gateway: vajalikud muudatused, mitte praegune kaitse

Tulevane kohalik gateway peab ainsana omama MG400 TCP ühendusi ja üht
serialiseeritud käsukirjutajat. Lab 1 station, Lab 2 station ning mg400-base
UI/CLI peavad kasutama seda sama vahendajat. Gateway kontrollib token'it
vahetult enne käsu väljastamist ning hoiab luba terve jada lõpuni.

Eraldi review'd nõudvad muudatused mg400-base'is:

1. Lisada koordinaatori eluea OS-lukk enne TCP, worker'ite ja job store'i
   avamist. Praegune prototüüp seda lukku ei rakenda. Teine koordinaator
   võib siin vana epoch'i blokeerida, seega mudel ei taga teenuse saadavust.
2. Suunata UI ja CLI ühe gateway kliendiks. CLI `_connect` ei tohi enam
   omada eraldi TCP-rada. Kaitsta ka käsurealt imporditud `DobotMG400` rada.
3. Kontrollida omanikku kõigil olekut muutvatel radadel: move/jog/recall/sync,
   pump/raw DO, speed/smoothness, connect/disconnect, enable/disable,
   clear_error/recover ning z_floor ja salvestatud asendite muutmine.
   Read-only status/config/check võib jääda eraldi vaatamisloaga. Stop vajab
   kohalikku prioriteedireeglit; seda ei tohi pidada füüsiliseks hädastopiks.
4. Hoida järjekord ja token'i kontroll sama kirjutaja all. Tühistada vana
   epoch'i saatmata käsud. TTL üksi ei luba uut omanikku, sest juba saadetud
   käsk võib robotis veel töötada. MG400 ei kontrolli meie fencing token'it
   ega tühista selle tõttu varem vastu võetud käsku.
5. Lisada usaldatud feedback-/completion-validaator, watchdog ja auditeeritav
   lifecycle. Siduda värskus, plaan ja sensori kinnitused konkreetse tööga.
   Ebaselge lõpp vajab kohalikku operaatorit, mitte automaatset ClearError'i,
   enable'it, pumba vabastust või uue omaniku proovikäsku. Praegune
   `/api/enable` proovib enne `clear_error`; seda kombineeritud käitumist
   tuleb eraldi review'da, kaugelt enable'i ei lisata.

Lab 1 `MG400Client` vajab tulevikus kohaliku gateway lepingu wrapper'it ning
station peab hoidma grant'i terve jada vältel. Lab 2 integratsioon peab
lahendama ka StationJobStore'i constructor'i restart-märgistuse: omanik peab
välistama konkureeriva programmi juba enne store'i avamist. Kumbagi
integratsiooni see samm ei tee.

### Otseühenduse möödapääs

SQLite ei blokeeri roboti porte 29999/30003/30004. Teine DB lubab teist
modelleeritud omanikku; seda näitab piirangutest. Teine arvuti, teine
mg400-base protsess või toor-TCP skript võib praegusest mudelist mööda minna.
Mudeli token on otsust kontrolliv number, mitte saladus ega roboti võti.

Laboris tuleb robotivõrk eraldada ja lubada juhtimisportidele ainult gateway
host. Sama hosti protsesside jaoks on lisaks vaja kontrollitud teenuse
õigusi ja võrgujuurdepääsu eraldust. Ainult localhost HTTP bind või
kokkuleppeline faililukk ei blokeeri toor-TCP-d. Siin ei määrata IP-sid,
VPN-i, tulemüürireegleid ega production-seadeid.

SQLite-baasi koopia taastamine, kustutamine või muu DB võib token'i ajaloo
tagasi pöörata. Päris gateway vajab mitte-tagasilükatavat epoch'i ning
operaatori kontrollitud taastamist. See prototüüp ei ole hajus lukk,
turvapiir ega kaitse pahatahtliku Python-koodi/andmebaasimuudatuse vastu.

## Enne riistvaraga sidumist

- Review'da ühine gateway ja kõik UI/CLI/jaamade käsurajad; tõendada, et
  teine protsess ja teine laboriarvuti ei saa luua konkureerivat TCP juhtimist.
- Kontrollida seisaku/idle tagasiside tähendus, vana käsujärjekorra tühjenemine,
  crash/restart ja lease'i kaotus. Testida eri omanikke ja stale token'it
  enne uut päris tööjada. Füüsiline hädastopp ja ruumis olev operaator jäävad nõutuks.
- Õpetada eristuvad source/finished asendid ning kontrollida lähenemis- ja
  ülekandeteed, tööriist, kaamera üldvaade ja esimene aeglane proov.
- Kontrollida pumba juhtmestik, osaline DO-käsu ebaõnnestumine, DA2 päris kalibratsioon,
  vaakumi/haarde ning vabastuse kinnitus. Praegused DO ack'id seda ei kinnita.

Riistvarakatsed, mõõtmised ja päris pick-place executor jäävad TODO.
Siia ei ole lisatud Arenduspäeviku kannet ega füüsilisi tulemusi.

## Kohalikud software-only kontrollid

Lab 2 virtuaalkeskkonnas: `python -m pytest -q tests/test_ownership_model.py`,
seejärel `python -m pytest -q` ja `python -m src.e2e_demo`.
Testid keelavad päris HTTP/TCP ühendused ja hoiavad simulation SQLite failid
pytest'i ajutises kataloogis. Olemasolev mock E2E ei kasuta uut mudelit.
