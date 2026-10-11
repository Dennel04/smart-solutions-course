# Lab 2 ohutuskokkuleppe mustand

> See dokument on kokkuleppe mustand. See ei tõenda, et meeskonnaliikmed on
> selle läbi lugenud või et katkestus- ja riistvarakatsed on tehtud.

## Kohustuslikud reeglid

1. Kaugtöö tohib käivitada ainult siis, kui robotiga samas ruumis on inimene,
   kes näeb kogu tööala ja ulatub füüsilise hädastopini.
2. Ruumis olev inimene kontrollib tööala ning lubab roboti lokaalselt.
   Remote enable on keelatud ja seda funktsiooni ei lisata.
3. Kui ruum on tühi, on robot voolust välja lülitatud, mitte ainult tarkvaras
   disabled-olekus.
4. Kui laua üldkaamera pilti ei ole või see ei näita kogu tööala, ei käivitata
   kaugtööd. Tööriistakaamera üksi ei ole piisav.
5. Postkontor võtab vastu ainult whitelist'i kõrgtaseme töid. Koordinaate,
   trajektoore, DO käske ja otseseid MG400 käske ei võeta internetist vastu.
6. Iga uus tööjada kontrollitakse esmalt lokaalselt 20% kiirusel, tööriist
   vähemalt 20 mm tööpinnast kõrgemal ja ilma proovitükita.
7. Aegunud töö ei liiguta midagi. Tundmatu, vigane või whitelist'i mittekuuluv
   töö ei liiguta midagi.
8. Robotile saadab liikumiskäske korraga ainult üks programm.
9. Kui internet katkeb pärast tervikliku kõrgtaseme töö lokaalset vastuvõttu,
   ei katkestata selle tõttu roboti jada. Jaam lõpetab juba vastu võetud töö
   oma kohalike ohutusväravate järgi, Atom säilitab tulemuse ja saadab selle
   postkontorisse pärast ühenduse taastumist. Seda kontrollitakse laboris kolm
   korda enne internetist päris tööde vastuvõttu.
10. MG400 füüsiline hädastopp on ainus usaldatud stop. Veebilehe stop-nupp on
    ainult mugavusfunktsioon.
11. MG400 aluse kaitselüliti rakendumise järel ei proovita robotit kaugelt
    uuesti käivitada; ruumis olev inimene peab olukorra kontrollima.
12. Labori 1 MG400 ohutusreeglid kehtivad edasi: käed ei ole 440 mm ulatuses,
    enne liikumist öeldakse „liigub“, esimene jooks on aeglane ja 24 V
    pumbakasti juhtmeid muudetakse ainult väljalülitatud süsteemil.

## Võrgu- ja infoturve

- production-kasutajaliides kasutab HTTPS-i ja parooli või tugevamat
  autentimist;
- tulemüüris on ainult minimaalselt vajalikud pordid ning iga pordi otstarve
  dokumenteeritakse;
- dropletil puudub võrguühendus robotisse, jaama või Atomisse; ainult Atom
  algatab postkontori suunas väljaminevaid HTTPS-päringuid;
- kogu välissisendit käsitletakse hostile input'ina: skeem, tüüp, pikkus,
  lubatud märgid ja väärtusvahemik kontrollitakse enne kasutamist;
- Atomi autentimisvõtit ei lisata reposse, näidiskonfiguratsiooni ega logisse;
- SSH privaatvõtmeid ei lisata reposse, vestlusse ega e-kirja;
- igal arvutil on eraldi SSH võti; jagatakse ainult avalikku võtit;
- kaameravood jäävad kohalikku võrku. Need ei lähe dropleti postkontorisse,
  postkontor ei proxy neid ja kaamera enda aadress ei ole internetist avatud;
- Atomi vaikimisi Wi-Fi parool vahetatakse enne seadme laborist väljaviimist.

## Enne kaugkäivituse lubamist

- [ ] Ruumis olev vastutaja on nimetatud ja hädastopi juures.
- [ ] Robot on tema poolt lokaalselt lubatud.
- [ ] Tööala ja kogu robot on laua üldkaameras nähtav.
- [ ] Töö ID, whitelist'i tüüp, argument ja TTL on kontrollitud.
- [ ] Jaama safety gate kinnitab, et robot on ühendatud, lubatud, veatu ja vaba.
- [ ] Sama töö ID ei ole juba täitmisel ega lõpetatud.
- [ ] Uus jada on varem lokaalselt 20% kiirusel ohutult kontrollitud.
- [ ] Kolm päriskatset kinnitavad, et internetikatkestus ei katkesta juba
  vastu võetud lokaalset tööd ja puhverdatud tulemus saadetakse hiljem.

## Meeskonna kinnitus

Iga liige lisab oma kinnituse ise pärast kokkuleppe päriselt läbilugemist.

| Nimi | Kuupäev | Kinnitus |
| :--- | :--- | :--- |
| TODO — team member confirmation required | TODO | TODO |
| TODO — team member confirmation required | TODO | TODO |
| TODO — team member confirmation required | TODO | TODO |
