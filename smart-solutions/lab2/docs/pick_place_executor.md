# pick_place: Lab 1 integratsiooni ettevalmistus

## Staatus

See muudatus valmistab ette kohaliku plaani ja read-only preflight'i.
**Päris liikumis- ja pumbaexecutor on blokeeritud.** mg400-base pakub pumba
HTTP API-t, kuid Lab 1 `MG400Client` ei paku sellele veel avalikku wrapper'it.
Jaamade vahel puudub ühine juhtimisõiguse mehhanism.
`PickPlacePreflightExecutor` tagastab ka edukate testkontrollide järel
`refused`; `physical_execution_allowed` jääb vääraks.

CLI, Atom, postkontori API ja olemasolev mock E2E jäävad muutmata.
`--allow-mock-jobs` lubab senist mock'i, mitte MG400-t. Komponent ei loo
MG400 klienti automaatselt. Kui operaator annab kliendi ja lubab preflight'i,
võib komponent saata `get_status` ja `check_pose` kaudu oleku- ja
reachability-päringuid, sealhulgas HTTP päringuid. See on liikumiseta
eelkontroll, mitte võrguühenduseta kontroll. Selle sammu testid kasutavad
ainult fake-transporti; päris robotiga ühendust ei võeta.

## Lab 1 tegelik liides

Allikas: [mg400_client.py](../../lab1/src/mg400_client.py).

| Meetod | Tähendus | Selle muudatuse kasutus |
| :--- | :--- | :--- |
| `get_status()` | ühendus, enabled, pose ja veainfo | fake HTTP vastus |
| `require_safe_status(status)` | ühenduse, enabled-, fault-, feedback-, servo- ja pose-kontroll | päris Lab 1 valideerija fake-andmetel |
| `check_pose(x, y, z)` | punktide reachability; toetamata route võib anda `None` | nõuab kinnitatud `True`; ei tõenda vaba trajektoori |
| `set_speed(ratio)` | lokaalne kiirus | ei kutsuta |
| `move_and_wait(x, y, z, r, ...)` | bounded liikumine, clamped-target kontroll ja tagasiside | ei kutsuta |
| `stop()` | best-effort tarkvarapeatus | ei kutsuta; usaldatud stop on füüsiline hädastopp |

Lab 1 `MG400Client` ei paku pump-, DO-, connect-, enable- ega recovery-meetodit.
See piirang ei tähenda nende route'ide puudumist mg400-base serveris.
Lab 1 dokumenteerib ajaloolise DO2 imemise ja DO1 puhumise katse;
praegune juhtmestik vajab uut kontrolli. Uus kood ei kutsu kliendi privaatset
`_request` meetodit ega saada pumbakäske.

## mg400-base pumba leping: lähtekoodikontroll

Kontrollitud avalikud versioonid:

- [KKallas/mg400-base server.py](https://github.com/KKallas/mg400-base/blob/7486b8b6a043db9ae488ddc6fa7f50b5fb7a65e7/mg400/server.py)
  ja [driver.py](https://github.com/KKallas/mg400-base/blob/7486b8b6a043db9ae488ddc6fa7f50b5fb7a65e7/mg400/driver.py).
- [Dennel04/mg400-base lab-jog server.py](https://github.com/Dennel04/mg400-base/blob/982ebf8533c4dfe39ad62fb570e339e3e918bcb8/mg400/server.py)
  ja [driver.py](https://github.com/Dennel04/mg400-base/blob/982ebf8533c4dfe39ad62fb570e339e3e918bcb8/mg400/driver.py).

| Route | Sisend / vastus | Tõlgendus |
| :--- | :--- | :--- |
| `GET /api/config` | `suck_do`, `blow_do` | serveri DO vastendus; füüsiline juhtmestik veel kinnitamata |
| `POST /api/pump` | `{"mode":"suck"}`, `blow` või `off` | lokaalne pumbarežiim; interneti töösõnum seda ei sisalda |
| käsu vastus | `ok`, `errid`, `resp` | ack ainult siis, kui `ok is True`, täisarvuline `errid == 0` ja `resp` on tekst |
| `GET /api/status` | `pump_mode`, `digital_out` ja roboti olek | DO tagasiside hetktõmmis, mitte vaakumi ega haarde mõõtmine |

Server kasutab puuduva `mode` korral `off`; meie kontroll nõuab selget režiimi.
Vigane režiim, katkenud ühendus või erand võib anda ainult
`{"ok":false,"error":"..."}`, mõnikord koos `errid` väljaga. `resp` ei ole
veavastuses kohustuslik. HTTP 200 võib seega sisaldada keeldumist.
Kontroll käsitleb `resp` teksti läbipaistmatu diagnostikana ega käivita seda.
Serveri `_command` kontrollib ühendust; see route ei taga meie kalibratsiooni,
omaniku, enabled- ega feedback-ohutusväravaid. Alloleva parseri rangemad
olekunõuded on kohalik konservatiivne leping, mitte uus serverigarantii.

`set_pump` lülitab enne teise liini välja: `suck` jaoks blow=0, suck=1;
`blow` jaoks suck=0, blow=1; `off` jaoks mõlemad=0. Driver proovib teist DO-d
ka siis, kui esimene tagastas veakoodi; erand võib jada katkestada.
Rollback'i ega atomaarset kahe DO vahetust leping ei taga. Osaline täitmine,
timeout või kadunud vastus jätab tegeliku oleku ebaselgeks. Käsu kordamine
või automaatne `off`/`blow` ei ole selle muudatuse taastamismeetod.

`pump_mode` arvutatakse `digital_out` bittidest, indeksist `DO - 1`.
Mõlemad pumbabitid kõrged annavad `conflict`; mõlemad madalad annavad `off`.
Vaikimisi on suck=DO2 ja blow=DO1, kuid server võib kasutada teist
konfiguratsiooni. `/api/config` vastus ei tõenda füüsilise vastenduse õigsust.

### Software-only vastuste kontroll

[`src/pump_contract.py`](../src/pump_contract.py) sisaldab puhtaid funktsioone:
`normalize_config`, `normalize_command_reply`, `normalize_status` ja
`assess_pump_exchange`. Kutsuja annab `HttpReply` objektidega juba dekodeeritud
JSON-i; moodul ei loo klienti, ei tee I/O-d ega võta callback'e.
Testide `FakeTransport` on mäluskript, mitte päris HTTP transport.

Kontroll nõuab eri DO indekseid ja korrektseid tüüpe. Vahemik 1–64 tuleb
feedback'i uint64 esitusest, mitte roboti füüsiliste väljundite arvust.
Konfiguratsiooni ja status'e muud väljad võivad alles jääda. Terve oleku
kontroll nõuab `connected`, `enabled`, `feedback_ok`, `servo_active` tõeseid
lippe, `error=False`, `stalled=False` ning veaväljade puudumist/tühjust.
Puuduv oluline väli, tundmatu vastus, HTTP viga, vigane ack, `conflict` või
režiimi/bittide vastuolu ei kinnita väljundeid. Need kontrollid ei luba robotit.

`command_acknowledged` märgib ainult kontrollitud ack'i; status'e timeout ei
kustuta juba saadud ack'i. `outputs_match` märgib ainult antud terve
hetktõmmise vastavust soovitud režiimile. See ei tõenda, et proov pärines
käsu järel: praegune API ei anna command-ID-ga seotud feedback-kinnitust.
`vacuum_confirmed`, `physical_execution_allowed` ja `automatic_retry_allowed`
jäävad ka sobiva ack'i ja bittide korral `False`. Veakoodid on fikseeritud
lokaalsed koodid; toorest serveriteksti ei lisata neisse.

Uus moodul ei ole seotud `StationAdapter` ega preflight'iga.
Preflight'i `pump_interface_missing` tähendab endiselt kontrollitud kohaliku
pumba- ja haardekinnituse sidumise puudumist, mitte HTTP route'i puudumist.

## Vaakumi kinnitamine: Andmehõive Lab 2 sõltuvus

Laboris tuleb kontrollida sensor/op-amp ahel, ADC pin, toitepinge ning
multimeetriga mõõdetud pinge. Seejärel sisestab meeskond Andmehõive Lab 2
päris koefitsiendid [Atomi rõhuseadetesse](atom_page.md#rõhuanduri-seaded).
Raw ADC, pinge ja kPa peavad pärinema samast proovist. Praegu jäävad
kalibratsioonikonstandid, haarde/vabastuse läved, hüsterees ja nõutav
stabiilsusaeg TODO; siin ei määrata neile näidisväärtusi.

Tulevane kohalik kontroll peab tuvastama vigase/puuduva kalibratsiooni,
ADC saturatsiooni, aegunud või kadunud proovi ning kinnitama proovide allika
ja järjestuse. Vastuvõtu vanust tuleb mõõta kohaliku monotoonse kellaga;
Atomi uptime'i ei saa võrrelda otse jaama kellaga. Enne detaili tõstmist
tuleb mõõta vaakumi teke ja püsimine; pärast vabastust tuleb kontrollida
vabastuse tulemust. Vigane andur või timeout keelab järgmise liikumissammu
ja nõuab kohalikku sekkumist, mitte automaatset jada kordamist.

Ka rõhuläve ületamine ei tõesta üksi detaili püsimist: ummistus või suletud
voolik võib näidata vaakumit ilma õige haardeta. Meeskond peab päris
detaili, iminapa ja koormusega kontrollima haaret ning ohutut rikkekäitumist.
See samm ei lisa sensoritransporti ega märgi ühtegi riistvarakatset tehtuks.

## Kohalik konfiguratsioon ja kavand

`src/pick_place_preflight.py` loeb kohalikust failist neli XYZR asendit:
`above_source`, `source`, `above_finished`, `finished`.
Kontrollid nõuavad numbrilisi lõplikke väärtusi, eri allika/sihtkoha XY-d,
vertikaalset lähenemist sama R-iga, vähemalt 20 mm tõstet ja ühist
ülemist ülekandetasapinda. 440 mm välisulatuse kontroll ei asenda roboti
liigese-, tööriista- ega kokkupõrkekontrolli. Kiirus tuleb määrata lokaalselt,
esialgu kuni 20%; puuduva väärtuse korral plaani ei teki.

Praegune Lab 1 `data/positions.json` kirjeldab ühe punkti tõstekatset:
source ja finished kattuvad. See fail lükatakse üleandmisplaani jaoks tagasi.
Lab 1 andmeid ei muudeta ega esitata hilisema katse kalibratsioonina.

Kandidaatjada:

1. above_source → source;
2. `acquire_part` kontrollpunkt;
3. above_source → above_finished → finished;
4. `release_part` kontrollpunkt;
5. above_finished.

`acquire_part` ja `release_part` on kavandi mõisted, mitte pumba käsud.
Kood ei käivita seda jada. Ohutu algpoos, lähenemistee, trajektoor,
iminapa kinnitus ning vaakumi tekke/vabastuse kinnitus vajavad laborikontrolli.
Internetist saabub ainult `routine=source_to_finished`; asendid ja kiirus
ei tule töösõnumist.

## DI ja kordustäitmise piir

`preflight_enabled=False` on vaikimisi. DI piir lubab ainult Lab 1 meetodeid
`get_status`, `require_safe_status` ja `check_pose`. Kliendi andja vastutab,
et meetodid järgivad Lab 1 lepingut; DI ei ole suvalise Python-koodi sandbox.
Testid annavad Lab 1 kliendile fake HTTP session'i.

Komponent ei võta vastu ega käivita `pump_check` või `ownership_check`
callback'e. Pumba ja ühise omaniku liides jäävad blokeerituks ka edukate
oleku- ja reachability-kontrollide järel: `pump_interface_missing` ja
`exclusive_owner_interface_missing`. Neid blokeeringuid ei saa testfunktsiooni
`True` vastusega eemaldada. `execute_pick_place` tagastab `refused` ning
`physical_execution_allowed=False` jääb kehtima. Puuduv kalibratsioon,
vigane olek, timeout ja ebaselge vastus annavad samuti keeldumise.

Test kontrollib, et vanade callback-atribuutide ja liikumise, pumba ning enable
meetodite side-effect spy'd jäävad kutsumata. Lubatud fake HTTP päringud on
ainult `GET /api/status` ja `POST /api/check`; POST ei tähenda siin liikumiskäsku.

StationAdapteri dependency injection sobib uue preflight-komponendiga.
StationJobStore säilitab stabiilse ID, terminaltulemuse ning restardi järel
`ambiguous_after_restart` keeldumise. Sama ID ei korda adapteri kaudu kontrolli
ega liikumist. Wire-protokolli lisapõhjusi ei lisata: täpsemad preflight-koodid
jäävad lokaalsesse `last_report` välja, serial-tulemus kasutab seniseid põhjusi.

**Oluline piir:** Lab 1 `EXECUTION_LOCK` on ühe protsessi threading.Lock.
Ka SQLite claim üksi ei välista teise Lab 1 protsessi juhtimist. Lisaks
märgib uue StationJobStore loomine varasemad in_progress kirjed restart-
keeldumisteks; enne päris täitmist peab üks omanik välistama paralleelse
käivituse juba enne store'i avamist. Selle sammuga omanikumehhanismi
ega Lab 1 käitumist ei muudeta. Päris täitmise sidumine jääb blokeerituks.

## Üks MG400 omanik: ettepanek review'ks

Praegu saab Lab 1 station saata HTTP käske mg400-base'ile; tulevane Lab 2
executor kasutaks sama rada. mg400-base UI saadab samu käske, kuid selle CLI
avab `DobotMG400` kaudu robotile oma TCP ühendused. Serveri `_robot_lock`
kaitseb connect/disconnect vahetust, mitte kogu tööjada ega teisi programme.
Lab 2 enda faililukk või SQLite claim ei välista neid konkurente.

Soovitus on üks kohalik juhtimisprotsess, mis ainsana omab MG400 TCP
ühendusi. Selle ettepaneku elluviimine vajab eraldi mg400-base/Lab 1 review'd:

1. Lab 1 station, Lab 2 station, mg400-base UI ja CLI kasutavad sama
   käsuvahendajat. CLI ei ava eraldi robotiühendust. Vahendaja kontrollib
   kõiki olekut muutvaid radu, sh move/jog/recall, pump/raw DO, speed,
   connect/disconnect, enable/recover ja trajektoori mõjutavat konfiguratsiooni.
   Read-only vaatamine ei anna juhtimisõigust; enable jääb kohalikuks käsiloaks.
2. Operaator annab lokaalselt ühe kliendi tervele tööjadale juhtimisõiguse.
   Vahendaja seob omaniku sessiooni ja job ID-ga ning kontrollib kasvavat
   fencing-token'it enne iga käsu väljastamist. Üks serialiseeritud kirjutaja
   lükkab teised kliendid ja aegunud token'iga järjekorrakäsud tagasi.
   Üksikute HTTP päringute mutex jätaks jada sammude vahele võõrad käsud.
3. Protsessi eluaja OS-lukk välistab teise vahendaja samal hostil, enne kui
   see avab TCP või StationJobStore'i. Robotivõrgu ligipääsupiirang peab
   lubama juhtimisporte ainult sellele hostile ja kontrollitud teenusele.
   Ülejäänud hostid, toor-TCP CLI ja otsene DO/API rada ei tohi luba mööda minna.
   Hostipiirang üksi ei välista sama hosti suvalist protsessi; vaja on ka
   teenuse õiguste ja võrgujuurdepääsu eraldust. Nende kontrollideta on lukk
   ainult osalejate kokkulepe, mitte tagatud välistus.
4. Timeout, omaniku kadumine või restart sulgeb uute käsusammude loa.
   TTL üksi ei anna uut omanikku, kui vana käsk võib veel töötada. MG400 ei
   valideeri meie token'it; juba saadetud käsku ei saa fencing'uga tühistada.
   Uus omanik vajab kinnitatud seisakut ja operaatori kontrolli. Pooleli töö
   jääb ebaselgeks/keeldutuks ega jätku automaatselt. Kadunud lease'i tõttu
   ei anta pimesi `off`/`blow`, mis võiks detaili kukutada.

Enne päris täitmist peab meeskond testima kahe kliendi konkurentsi, teise
CLI käivitust, omaniku crash'i ja restarti. Füüsiline hädastopp jääb ainsaks
usaldatud stop'iks. Siin on ainult arhitektuuriettepanek: ükski uus lukk,
lease, juhtimisroute ega võrgu-/production-seadistus ei ole rakendatud.

## Enne päris executori review'd lahendada

- Kes review'b mg400-base `/api/pump` kohaliku wrapper'i, osalise DO-täitmise
  rikkekäitumise ning vaakumi/haarde kinnituse? Kes kontrollib juhtmestiku ja
  Andmehõive Lab 2 päris kalibratsiooni?
- Kuidas hoida üks juhtimisõigus üle kõigi jaamade, CLI-de ja mg400-base
  kasutajate? Eraldi Lab 2 lukk ei kaitse Lab 1 programmi eest.
- Kus on neli praegusele tööriistale õpetatud eri lähte-/sihtasendit,
  ohutu algpoos ja kontrollitud lähenemis-/ülekandeteed?
- Milline tagasiside kinnitab idle-olekut, liikumise lõppu, vaakumit ja
  detaili vabastamist? Millised ajapiirid ja käsitsi sekkumise sammud kehtivad?
- Kes annab ruumis lokaalse loa, kontrollib üldkaamerat ja ulatub hädastopini?

Pumba või juhtimisõiguse jaoks vajalikud Lab 1 muudatused tuleb enne eraldi
review'le esitada. Riistvarachecklist, official mid-job katsed ja mõõtmised
jäävad TODO. Dokument ei kinnita füüsilist integratsiooni.
