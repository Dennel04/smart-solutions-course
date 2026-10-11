# Lab 2 postkontori production-paigalduse alus

> **Olek:** siin on korduvkasutatavad konfiguratsioonid ja käitamisjuhised.
> Ühtegi päris dropletit, DNS-i, sertifikaati, tulemüüri ega SSH-seadet ei ole
> nende failide loomisel muudetud ega kontrollitud. Kõik päris hosti tulemused
> jäävad TODO-ks kuni meeskond on need hostil ise kontrollinud.

## Arhitektuur ja piir

```text
Internet
   |
   | HTTPS :443
   v
Caddy (avalik TLS-i lõpetamine)
   |
   | HTTP ainult 127.0.0.1:5001
   v
Gunicorn -> Flask postkontor -> SQLite
                                  |
                                  +-- /var/lib/smart-solutions-lab2/

AtomS3 -- väljaminev HTTPS polling --> sama Caddy host
```

Droplet on ainult postkontor. See ei loo ühendust station'i, MG400 ega
kaameratega, ei vahenda kaameravooge ning ei sisalda VPN-i või tunnelit.
Station'i ja kaamerate lokaalne arhitektuur jääb laborivõrku. AtomS3
production server URL on `https://<TEAM_HOSTNAME>` ja ta algatab ühenduse ise.

Gunicorn kuulab ainult `127.0.0.1:5001`. Internetti avatakse Caddy kaudu ainult
HTTP/HTTPS pordid; porti 5001 ei avata tulemüüris. `Caddyfile.example` kasutab
hostinime, mille korral Caddy saab pärast korrektset DNS-i ja portide 80/443
kättesaadavust hallata avalikku HTTPS-sertifikaati.

## Failipaigutus production-hostil

| Tee | Omanik / õigus | Sisu |
| :--- | :--- | :--- |
| `/opt/smart-solutions-lab2/app` | `root:root`, lugemiseks | Git checkout, kogu course repo |
| `/opt/smart-solutions-lab2/venv` | `root:root` | Python virtualenv ja sõltuvused |
| `/etc/smart-solutions-lab2/env` | `root:root`, `0600` | runtime konfiguratsioon ja saladused |
| `/var/lib/smart-solutions-lab2` | service user, `0750` | püsiv SQLite andmebaas |
| `/var/backups/smart-solutions-lab2` | `root:root`, `0700` | kontrollitud SQLite backup'id |
| `/etc/caddy/Caddyfile` | `root:root` | avalik HTTPS reverse proxy |

Teenuse kasutaja `smart-solutions-lab2` on süsteemikonto ilma login-shellita.
Lähtekood ei ole selle kasutaja kirjutatav. Systemd unit annab kirjutusõiguse
ainult püsiva andmebaasi kataloogile.

## Eeltingimused

- puhas toetatud Ubuntu droplet, mille hostinimi/IP on õppejõult saadud;
- iga meeskonnaliikme eraldi SSH võtmepaar ja kontrollitud võtmega login;
- DNS A/AAAA kirje `<TEAM_HOSTNAME>` jaoks;
- `git`, `python3`, `python3-venv`, `curl`, `sqlite3`, Caddy ja `ufw`;
- Git checkout on `/opt/smart-solutions-lab2/app`;
- päris väärtused on paroolihalduris, mitte repos ega shelli ajaloos.

Pakette ja Caddyt paigaldatakse nende ametlike Ubuntu juhiste järgi päris
hostil. Seda pole siin automatiseeritud, sest hosti versioon ja õppejõu
haldusreeglid tuleb enne teada.

## Esmane paigaldus

Allolevad käsud on hostil täitmiseks pärast eeltingimuste kontrolli. Asenda
ainult märgitud placeholder'id päris hosti väärtustega.

1. Tee rakenduse kataloog ja klooni repo:

   ```bash
   sudo install -d -o root -g root -m 755 /opt/smart-solutions-lab2
   sudo git clone https://github.com/Dennel04/smart-solutions-course \
     /opt/smart-solutions-lab2/app
   ```

2. Vaata üle checkout'i branch ja commit. Seejärel käivita ettevalmistus:

   ```bash
   cd /opt/smart-solutions-lab2/app/smart-solutions/lab2
   sudo sh deploy/install.sh
   ```

   Skript ei käivita teenust, ei muuda SSH-d/tulemüüri ega paigalda Caddyt.
   Olemasolevat `/etc/smart-solutions-lab2/env` faili see üle ei kirjuta.

3. Loo kolm erinevat väärtust: veebikasutaja nimi, pikk juhuslik veebiparool
   ja eraldi pikk juhuslik Atomi bearer-võti. Ära kasuta näiteid production'is.
   Muuda root'ina `/etc/smart-solutions-lab2/env`, asenda kõik `<...>` väljad
   ja kontrolli õigusi:

   ```bash
   sudoedit /etc/smart-solutions-lab2/env
   sudo chown root:root /etc/smart-solutions-lab2/env
   sudo chmod 600 /etc/smart-solutions-lab2/env
   ```

   `POST_OFFICE_DB` peab jääma välisele püsirajale
   `/var/lib/smart-solutions-lab2/post-office.sqlite3`. Saladusi ei lisata
   Git-i, logisse, issue'sse ega ekraanipilti.

4. Kopeeri Caddy näidis, asenda `<TEAM_HOSTNAME>` ja valideeri enne reload'i:

   ```bash
   sudo install -o root -g root -m 644 deploy/Caddyfile.example /etc/caddy/Caddyfile
   sudoedit /etc/caddy/Caddyfile
   sudo caddy validate --config /etc/caddy/Caddyfile
   sudo systemctl reload caddy
   ```

5. Alles pärast konfiguratsiooni ja DNS-i kontrolli käivita rakendus:

   ```bash
   sudo systemctl enable --now smart-solutions-lab2
   sudo systemctl status smart-solutions-lab2
   sudo journalctl -u smart-solutions-lab2 -n 100 --no-pager
   sudo sh deploy/verify.sh
   ```

`/health` on tahtlikult avalik minimaalne tervisekontroll. Kasutajaliides ja
`/api/jobs*` nõuavad Basic autentimist; `/api/atom/*` nõuab eraldi bearer-võtit.
Rakendus keeldub käivitumast, kui parool või Atomi võti puudub.

## SSH hardening — ohutu järjekord

SSH lukustuse vältimiseks tehakse päris hostil toimingud täpselt sellises
järjekorras. Neid samme ei tee ükski repo skript.

1. Saa õppejõult dropleti aadress, kasutajanimi ja hosti ligipääsureeglid.
2. Tee esimene login õppejõu antud meetodil ning hoia see sessioon avatuna.
3. Lisa igale kasutatavale arvutile selle enda avalik `.pub` võti ja anna
   õppejõule ainult nõutud avalikud võtmed; privaatvõtit ei jagata kunagi.
4. Ava **teine terminal** ja tõesta, et uus võtmega login töötab.
5. Muuda SSH seadistust nii, et parooliga login keelatakse alles nüüd.
6. Valideeri konfiguratsioon käsuga `sudo sshd -t`.
7. Reload'i distro tegelik SSH service (`ssh` või `sshd`), ära tee pimesi
   restarti.
8. Ava veel üks uus võtmega sessioon ja kontrolli seda.
9. Alles pärast õnnestunud kontrolli sulge esialgne sessioon.

Root-login, kasutajate loomine ja õppejõu ligipääs kooskõlastatakse hosti
omanikuga; siin ei eeldada nende poliitikat.

## Tulemüür — käskude kontroll-leht

Need on teadlikult dokumenteeritud käsud, mitte automaatne skript. Käivita
need alles pärast võtmega login'i kontrolli ja kinnita enne `enable` käsku,
et kasutatava SSH pordi reegel on olemas.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status verbose
sudo ufw enable
sudo ufw status numbered
```

Kui host kasutab mittevaikimisi SSH porti, lisa enne tulemüüri aktiveerimist
selle täpne reegel `OpenSSH` profiili asemel. Porti 5001, SQLite'i, station'i,
MG400 või kaamerate jaoks avalikku reeglit ei lisata.

## Uuendamine ja rollback

Uuendamisel vali ja vaata commit/ref enne läbi. Skript nõuab puhast checkout'i,
teeb enne Git muudatust SQLite online-backup'i, lubab ainult fast-forward
merge'i, uuendab Python sõltuvused, restardib teenuse ja kontrollib tulemust:

```bash
cd /opt/smart-solutions-lab2/app/smart-solutions/lab2
sudo sh deploy/update.sh origin/main
```

`origin/main` on näide teadlikult valitud ref-ist, mitte automaatne soovitus.
Skript ei kasuta force/reset käsku ega kustuta andmebaasi.

Backup'i saab eraldi teha käsuga:

```bash
sudo sh deploy/backup.sh
```

Rollback'i korral peata teenus, säilita praegune DB eraldi, kontrolli valitud
backup'i `PRAGMA quick_check` abil, kopeeri see püsirajale õige omaniku ja
õigustega ning käivita teenus uuesti. Ära kirjuta toimivat DB-d üle enne, kui
backup ja soovitud rakendusversioon on tuvastatud. Rakenduskoodi rollback peab
olema eraldi läbi vaadatud Git ref ja võimalusel fast-forward; skeemimuudatuse
korral on vaja selle versiooni eraldi migratsioonijuhist.

## Taastamine puhtale dropletile

1. Taasta Ubuntu ja turvauuendused vastavalt hosti haldusreeglitele.
2. Lisa meeskonna avalikud SSH võtmed ja tee eespool kirjeldatud teise sessiooni
   kontroll.
3. Paigalda eeltingimused ning Caddy.
4. Taasta DNS ainult pärast uue avaliku IP kinnitamist.
5. Klooni kontrollitud Git ref rajale `/opt/smart-solutions-lab2/app`.
6. Käivita `deploy/install.sh`; see loob service user'i, virtualenv'i ja unit'i.
7. Taasta `/etc/smart-solutions-lab2/env` paroolihaldurist, õigustega `0600`.
8. Taasta kontrollitud SQLite backup rajale `POST_OFFICE_DB`, omanikuks
   `smart-solutions-lab2:smart-solutions-lab2` ja õiguseks `0600`.
9. Paigalda ja valideeri Caddy konfiguratsioon.
10. Sea tulemüür alles pärast SSH ligipääsu kontrolli ning käivita teenused.
11. Käivita `deploy/verify.sh`, kontrolli autentimist ja tee Atomiga päris
    outgoing-polling katse. Dokumenteeri kuupäev ning tegelik tulemus alles siis.

## Kontrollimine ja logid

```bash
sudo sh deploy/verify.sh
sudo systemctl status smart-solutions-lab2 caddy
sudo journalctl -u smart-solutions-lab2 --since today
sudo journalctl -u caddy --since today
```

`verify.sh` kontrollib env-faili õigusi ja placeholder'e, DB kataloogi
kirjutatavust service user'ina, systemd/Caddy olekut, localhost health'i,
port 5001 loopback-bind'i ning seadistatud hostinime HTTPS health'i. HTTPS curl
ei kasuta `-k` lippu, seega kontrollib ka sertifikaadi usaldatavust. Mitte-Linux
arendusmasinas annab skript teadlikult `SKIP`, mitte väljamõeldud PASS-i.

Logides võivad olla töö ID, olek, ajatempel ja veakood. Paroole, bearer-võtit,
Authorization päist, SSH privaatvõtit või kogu env-faili ei tohi logida.

## Päris dropleti päeva TODO

- [ ] Droplet, distro versioon ja vastutav omanik on kinnitatud.
- [ ] Kõigi kasutajate võtmega SSH login on teises sessioonis kontrollitud.
- [ ] Password login on keelatud alles pärast seda kontrolli.
- [ ] DNS `<TEAM_HOSTNAME>` viitab kinnitatud dropletile.
- [ ] Caddy avalik sertifikaat ja HTTPS health on kontrollitud.
- [ ] UFW lubab ainult kokkulepitud SSH, 80/tcp ja 443/tcp; 5001 pole avalik.
- [ ] Env-fail on `root:root 0600`, placeholder'e ega reposaladusi pole.
- [ ] SQLite püsib väljaspool Git checkout'i ja backup on kontrollitud.
- [ ] Kasutaja Basic auth ja Atomi bearer auth on päris hostil kontrollitud.
- [ ] Atom pollib aadressi `https://<TEAM_HOSTNAME>` väljamineva ühendusega.
- [ ] Station'i, MG400 ja kaamerate poole ei ole dropletil route'i/proxy't.
- [ ] Taasteprotseduur on päriselt läbi proovitud ja tulemus kuupäevaga kirjas.
