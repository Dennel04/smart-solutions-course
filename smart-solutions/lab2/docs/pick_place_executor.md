# pick_place: Lab 1 integratsiooni ettevalmistus

## Staatus

See muudatus valmistab ette kohaliku plaani ja read-only preflight'i.
**Päris liikumis- ja pumbaexecutor on blokeeritud.** Lab 1 kliendil puudub
pumbaliides ning jaamade vahel puudub ühine juhtimisõiguse mehhanism.
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

Kliendil ei ole pump-, DO-, connect-, enable- ega recovery-meetodit.
Lab 1 dokumenteerib ajaloolise DO2 imemise ja DO1 puhumise katse; see ei
määra uut pumba API-t, vaakumi kinnitust ega praeguse juhtmestiku õigsust.
Uus kood ei kasuta privaatset `_request` meetodit pumbakäskude leiutamiseks.

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

## Enne päris executori review'd lahendada

- Milline olemasolev pumbaliides annab acquire/release ja kinnitatud tulemuse?
  Kes kontrollib juhtmestiku, pumba oleku ja pressure calibration'i?
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
