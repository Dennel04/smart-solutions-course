# Lab 3 tulevaste mõõtmiste metoodika

Kõik tulemused on TODO. Neli CSV-d jäävad ainult päistega; allpool on
planeeritud andmetähendus ja analüüs, mitte katse tulemus.
Olemasolevad päised on piisavad, kui iga seeria tingimused ja tõendid
seotakse allpool kirjeldatud viidetega. Päiseid selles töös ei muudeta.

## Juhtimislatentsus

[Kohalik seeria](../data/latency_local.csv): 30 päris nupuvajutust.
[VPN-seeria](../data/latency_vpn.csv): 30 päris nupuvajutust mobiilse andmesidega.

| Veerg | Tähendus ja ühik |
|---|---|
| trial | Seerias unikaalne katse ID |
| button_ts | Vajutuse aeg ühisel mõõteajaskaalal millisekundites |
| robot_motion_ts | Füüsilise liikumise algus samal ajaskaalal millisekundites |
| latency_ms | robot_motion_ts − button_ts; millisekundites |
| connection | VPN-seeria tegelik ühendus ja tingimused |
| notes | Seeria ID, kuupäev, meetod, tõend/failiviide, kaamerate arv ja seadistus ning tõrked |

Brauseri ja roboti sõltumatuid kellasid ei lahutata ilma kontrollitud
sünkroonimise/veapiirita. Eelistada ühist salvestust või muud põhjendatud
ühist ajabaasi; valida meetod ja määramatus enne mõõtmist: TODO.
Liikumise algus ei ole HTTP-vastus ega käsu vastuvõtt.

Võrrelda sama uut ohutult kontrollitud jada ja samu tingimusi; märkida
0/1/2 aktiivset kaamerat ja klientide arv. Kummagi seeria keskmine,
maksimum ning võrreldavus Lab 2 juhtimislatentsusega: TODO.
Ebaõnnestunud katse säilitatakse põhjusega; puuduvat viidet ei märgita nulliks.

## Mõlemad kaamerad VPN-i kaudu

[Kaamerate CSV](../data/camera_vpn_metrics.csv) eristab üldvaadet ja
tööriistakaamerat. Iga kaamera/tingimuse rida seotakse notes-väljas
kuupäeva, seeria/katse ID, meetodi, mõõteakna alguse/lõpu ja tõendifailiga.

| Veerg | Tähendus ja ühik |
|---|---|
| camera | Laua üldvaade või XIAO tööriistakaamera; täpne allikas |
| resolution | Tegelik capture- ja kuvamisresolutsioon pikslites |
| latency_ms | Füüsilise sündmuse ja kuvatud kaadri vahe, ms |
| fps | Mõõteaknas tegelikult väljastatud kaadrid sekundis |
| bandwidth_mbps | Mõõdetud edastuskiirus Mbit/s; märkida mõõtepiir |
| connection | Mobiilne andmeside VPN-iga ning võrgu tingimused |
| notes | Mõõteaken, toorloendurid, seaded, kliendid, aktiivsed vood ja tõendiviited |

Kasutada sama sündmuse/kuvatud kaadri meetodit nagu
[Lab 2 kaameraplaanis](../../lab2/docs/cameras.md).
FPS = kaadrite arvu muut / mõõteakna sekundid;
ribalaius = baitide arvu muut × 8 / sekundid / 1 000 000.
JPEG payload'i loendur ei hõlma kogu VPN-i protokollikulu; kui mõõdetakse
võrguliideselt, märgitakse see eraldi. Säilitada toorloendurid ja JPEG-seaded.

Lab 2 füüsiliste lähteandmete kontrollitud failid ja võrreldavus: TODO.
Mock-kaadrid, software-loendurite arendustest ja XIAO diagnostiline USB JPEG
ei ole VPN-i ega kahe füüsilise kaamera mõõtmistulemused.

## Tunneli 48 tunni logi

[tunnel_48h.csv](../data/tunnel_48h.csv) kogutakse tulevikus dropleti poolt:
üks kontroll läbi tunneli iga 10 sekundi järel, järjest 48 tundi.
Kontrolli siht, timeout ning tunneli kaudu minemise kontroll: TODO.

| Veerg | Tähendus ja ühik |
|---|---|
| timestamp | Plaanitud kontrolli aeg ISO 8601 UTC-s; seeria algus/lõpp notes-väljas |
| reachable | 1 = vastas, 0 = ei vastanud kokkulepitud timeout'i jooksul |
| rtt_ms | Eduka kontrolli RTT millisekundites; ebaõnnestumisel tühi |
| notes | Tegelik käivitusaeg/viivitus, siht, meetod ja tõrge; ei sisalda saladusi |

Enne kogumist määrata seeria täpne algus ja lõpp ning kasutada poolavatud
48 h akent: kavandatud kontrollide arv on 17 280 (48 × 3600 / 10).
See on ajakava arvutus, mitte olemasolevate ridade arv.

Analüüsiplaan:

- Sorteerida ajad, kontrollida duplikaate ja oodatud 10 s sammu.
- Eristada vastamata kontroll ja puuduv logirida; puuduv rida on teadmata
  olek, mitte tõendatud tunnelirike. Raporteerida logi katvus.
- Iga teadaolev tulemus esindab järgmist 10 s intervalli kuni akna lõpuni.
  Järjestikused vastamata intervallid moodustavad ühe vaadeldud katkestuse.
- Raporteerida katkestuste arv, hinnanguline teadmata/maas aeg sekundites,
  suurim järjestikune katkestus sekundites ning piirid akna serval.
- Vaadeldud kättesaadavus = edukate intervallide kestus /
  teadaolevate intervallide kestus × 100%. Puuduliku logi korral lisada kogu
  akna alumine/ülemine piir, lugedes teadmata aja vastavalt maas/üleval ajaks.
- 10 s samm annab ainult proovivõtust tuleneva hinnangu: lühem katkestus võib
  jääda märkamata. Põhjused lisada ainult logitõendi olemasolul.

Kõik tegelikud kokkuvõtted ja katkestuste põhjused: TODO.
Logijat selles etapis ei rakendata ega käivitata.

## VPN-i kadumine liikumise ajal

Kolme füüsilise katse väljad ning eeltingimused on
[ohutuskokkuleppes](safety.md#vpn-i-kadumine-liikumisel).
Enne kaugliikumist tuleb ohutu käitumine teostada ja lokaalselt kinnitada.
Katsete tulemused ja taastamine: TODO.
