# source_to_finished: eraldatud software-only simulatsioon

## Ulatus

[`PickPlaceSimulation`](../src/pick_place_simulator.py) kontrollib etteantud
sünteetilist sündmustikku. See ei ole päris executor ega MG400 turvapiir.
Klassil puuduvad StationAdapteri `ready` ja `execute_pick_place` liidesed.
Moodul ei loo HTTP/TCP/serial-klienti, ei võta transporti ega käivita
callback'e. Olemasolev StationAdapter ja mock E2E jäävad muutmata.

`SimulationResult` märgib edu `simulated_complete`, mitte füüsilise `done`
tulemusena. Iga tulemus sisaldab `hardware_used=False`,
`physical_execution_allowed=False` ja `automatic_retry_allowed=False`.
Preflight jääb muutmata: `refused`, `physical_execution_allowed=False`.

## Sisendid ja korduskasutus

- Kutsuja annab testide fixture'is või ajutises kataloogis loodud positions
  JSON-i. Nõutav `synthetic: true` märgis aitab vältida Lab 1 päris faili
  kogemata kasutamist. Märgis ei tõenda andmete päritolu ega blokeeri
  pahatahtlikku ümbermärgistamist. Moodulis puuduvad näidiskoordinaadid.
- `load_synthetic_plan` kutsub olemasolevat `build_local_plan` funktsiooni.
  Nelja asendi, geomeetria, source/finished erisuse, kohaliku kiiruse ja
  `source_to_finished` routine'i valideerimine pärineb avaldatud preflight'ist.
  Simulator hoiab selle tagastatud `LocalPlan` ja `PlanStep` objekte.
- Kutsuja annab eraldi testbaasiga `OwnershipModel` mudeli ja fake-kella.
  Ta peab enne katset sisestama sünteetilise kohaliku operaatori kinnituse.
  Simulaator ise ei kutsu `operator_clear` meetodit.
- `SyntheticStepObservation` sisaldab oodatud sammu, `StepEvidence` lippe
  ning vajadusel pumba ja detaili kohta eraldi sünteetilist vaatlust.
  Nimed ja lipud kirjeldavad teststsenaariumi, mitte päris mõõtmisi.

`start` küsib ühe grant'i tervele jadale ning aktiveerib selle. `advance`
võtab vastu ühe vaatluse ja grant'i. `finish` kontrollib kõigi kaheksa sammu
ning lõpptõendi olemasolu. Puuduvad automaatne stardiluba, võrgu- või
riistvaratuvastus, live-kliendi factory ja käske käivitav töötsükkel.

## Kaheksa sammu

| Nr | Avaldatud LocalPlan samm | Eraldi nõutav detaili vaatlus |
| :--- | :--- | :--- |
| 1 | `move_to_taught above_source` | detail lähtekohas; haaret veel ei eeldata |
| 2 | `move_to_taught source` | detail lähtekohas |
| 3 | `acquire_part` | värske kalibreeritud proovi väide, vaakum ja haare kinnitatud |
| 4 | `move_to_taught above_source` | värske vaakumi/haarde kinnitus säilib |
| 5 | `move_to_taught above_finished` | värske vaakumi/haarde kinnitus säilib |
| 6 | `move_to_taught finished` | värske vaakumi/haarde kinnitus säilib |
| 7 | `release_part` | värske proovi väide, vaakumi puudumine ja vabastus kinnitatud |
| 8 | `move_to_taught above_finished` | vabastuse kinnitus säilib värske proovi väitega |

Iga vaatluse samm peab võrduma kanonilise plaani järgmise elemendiga.
Vahelejätmine, kordamine, tundmatu operatsioon või üheksas samm peatab
katse. Detaili mudel järgib olekuid `at_source → held → at_finished`.
Ülekande sammud ei saa jätkuda ilma eraldi kinnitatud haardeta.
Rikke järel muutub detaili olek konservatiivselt `unknown`; automaatset
liikumist, pumba kompensatsiooni ega detaili vabastust ei järgne.

### Pump ja rõhk

Kontseptuaalsed acquire/release sammud annavad puhtale
`assess_pump_exchange` funktsioonile config-, ack- ja status-`HttpReply`
objektid. Mingit päringut ei saadeta. Acquire kasutab siin sünteetilist
`suck` vastust; release kasutab sünteetilist `off` vastust. See on testi
kokkulepe, mitte päris pumba vabastusmeetodi valik. `off` ei tõenda haarde
kadumist, seetõttu vajab release sõltumatut kinnitust.

`ok=false`, vigane/nonzero `errid`, vale DO vastendus, osaline DO-täitmine,
režiimi vastuolu, `conflict`, ebatervislik feedback ja timeout peatavad
katse. HTTP 200 ja `outputs_match=True` ei määra detaili olekut. Sama
vaakumi/haarde kinnitus on vajalik ka kandmise ajal, mitte ainult acquire'is.

`SyntheticPartEvidence` kasutab eraldi kalibratsiooni, proovi värskuse,
vaakumi, haarde ja vabastuse lippe. Päris raw ADC, pinge, kPa,
kalibratsioonikoefitsiendid, vaakumiläved, hüsterees ja stabiilsusaeg
puuduvad. Lipud ei arvuta proovi vanust ega tõenda anduri olemasolu.
Andmehõive Lab 2 ja laborikatsed peavad need teadmised hiljem andma.

## Ownership ja terminaltulemused

Enne iga sammu kutsub simulatsioon `OwnershipModel.admit_step` meetodit,
mis kontrollib omanikku, session/job ID-d, epoch'i ja fencing token'it.
Alles siis lisandub `admitted` trace-kirje. `confirm_step` vajab kogu
`StepEvidence` kinnitust; edu lisab `confirmed` kirje ja liigutab plaani
indeksit. Ühe sammu kohta ei tehta teist katset. Trace hoiab sammu,
järjekorranumbri, token'i ja detaili olekut; veaga samm jääb kinnitamata.

Vigane või tundmatu tulemus lõpetab instantsi `simulated_stopped` olekus.
Kehtiva oma grant'i korral märgib mudel `UNCERTAIN`; juba tühistatud token
ei saa uut omanikku vabastada ega blokeerida. Restart teeb vana
koordinaatori kättesaamatuks ja uus epoch hoiab vana töö `UNCERTAIN` olekus.
Puudulik või vale järjekord, pumba/haarde viga ja ka teadaolev motion-viga
kasutavad selles prototüübis sama konservatiivset rikkepiiri.

Terminaltulemus jääb muutumatuks: järgmised `advance`, `start` ja `finish`
kutsed tagastavad sama kirje ega korda samme. Uus instants ei saa sama
job ID-d uuesti claim'ida. Lease'i või absoluutse jada tähtaja ületamine
ei vabasta omanikku. Timeout'i piirangud tulevad ownership mudelist;
testides valitud ajad on sünteetilised loogilise kella väärtused, mitte
robotile või vaakumile mõõdetud kestused. Simulaator ei pikenda lease'i ise.

Edu jaoks peavad kõik kaheksa sammu olema kinnitatud, detail `at_finished`
ning `CompletionEvidence` täielik. Siis kutsub simulatsioon ownership mudeli
`complete` meetodit; see vabastab ainult modelleeritud omaniku. Puudulik
lõpptõend hoiab `UNCERTAIN` olekut. Tulemus näitab eraldi ownership olekut
ja põhjust; baasi/koordinaatori kättesaamatust ei esitata eduna.
Kui lõpu readback kaob pärast kinnitatud `complete` tehingut, tagastab
simulatsioon samuti `simulated_stopped`. Töö ajalugu võib siis juba olla
`COMPLETED`; tulemus ei väida rollback'i ega luba sama job ID-d korrata.

## Kontrollid ja allesjäävad blokeeringud

[`test_pick_place_simulator.py`](../tests/test_pick_place_simulator.py) kasutab
ainult sünteetilisi fixtures'e ning keelab päris HTTP/TCP/serial ühendused.
Kontrollitakse kogu jada, valesti järjestatud samme, sisendi geomeetriat,
haarde/vaakumi/rõhu lippe, pumba osalist viga, tundmatut motion-tulemust,
timeout'i, job ID kordust, konkurenti, stale token'it, restarti ja vabastust.

Lab 2 virtuaalkeskkonnas saab käivitada
`python -m pytest -q tests/test_pick_place_simulator.py`;
üldregressioon on `python -m pytest -q`
ning varasem mock E2E `python -m src.e2e_demo`. Olemasoleva E2E `done` on
senise mock executori tulemus, mitte selle simulaatori füüsiline edu.

See test ei tõenda roboti ohutust. Päris integratsioon vajab veel
[ühist gateway'd ja bypass-kaitset](ownership_gateway.md), autentitud
kohalikku luba, usaldatud värske tagasiside kontrolli, täisplaani kinnitamist,
seisaku tuvastust ning testitud crash/timeout käitumist. Vaja on eri
source/finished asendeid, ohutut trajektoori, kontrollitud juhtmestikku ja
Andmehõive Lab 2 kalibratsiooniga päris haarde/vabastuse katseid.
Lab 1, firmware, production, postkontori API ja Arenduspäevik jäävad muutmata.
