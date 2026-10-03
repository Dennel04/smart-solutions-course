# Labori 1 tellimus

Meeskond kontrollib tabeli järgi labori varu. Tabel ei kinnita ühegi eseme olemasolu ega puudumist enne laborikontrolli.

| Osa | Kogus | Milleks seda laboris vaja on | Laboris kontrollitud | Kas tellida? | Märkus |
| :--- | :---: | :--- | :---: | :---: | :--- |
| AtomS3 | 1 | Tähe valimiseks ja saatmiseks ning pildi kuvamiseks Atomi ekraanil. | jah, 02.–03.10.26 | ei | AtomS3R; ühendatud püsivara (pump + täht) peal 03.10.26. |
| USB-C kaabel | 1 | AtomS3 ühendamiseks arvutiga ja püsivara laadimiseks. | jah | ei | Atom ↔ laboriarvuti: püsivara, rõhu telemeetria ja täht (USB kanal). |
| USB-C → Ethernet adapter | 0 | Etherneti pordita sülearvuti ühendamiseks MG400 võrguga. | jah | ei | Ei vaja: laboriarvutil on kaks Ethernet porti (ülikooli võrk + MG400). |
| LAN kaabel | 1 | Pythoni jaama ja MG400 vahelise Etherneti ühenduse loomiseks. | jah | ei | Laboriarvuti teine Ethernet port → MG400 LAN1 (192.168.1.6). |
| Marker | — | Tähtede joonistamiseks enne ja pärast pastakahoidiku valmimist. | ei | ei | Ei kasutatud: pastakahoidik (3D printimise L1) oli olemas. |
| Maalriteip | — | Paberi ja vajaduse korral markeri ajutiseks kinnitamiseks. | ei kontrollitud | ei | — |
| Paber | lehed | Roboti joonistustestide tegemiseks. | jah, 03.10.26 | ei | Joonistati 264 × 210 mm lehele. |
| Umbes 24 × 24 mm lame proovitükk | 1 | Kümne pick-and-place tsükli kontrollimiseks. | jah, 02.10.26 | ei | 24 × 24 mm klaas, kümme võtmist 10/10 (Andmehõive katse). |
| MG400 koos iminapa komplektiga | 1 | Proovitüki tõstmiseks ja tähtede joonistamise liikumiste tegemiseks. | jah | ei | API-režiimis; iminapp tõstmiseks, pastakahoidik joonistamiseks. |
| Pumbakast | 1 | Imemise ja puhumise juhtimise kontrollimiseks MG400 DO-liinide kaudu. | jah, 02.10.26 | ei | DO2 = imemine, DO1 = puhumine, kontrollitud impulssidega. |
| Sülearvuti Etherneti võimalus | — | Pythoni jaama ühendamiseks roboti võrguga. | jah | ei | Jaam on laboriarvuti (lauaarvuti), mitte sülearvuti; Wi-Fi-d sellel ei ole. |
| Hädastopi ligipääs | 1 | MG400 esimeste liikumiste ohutuks peatamiseks. | jah | ei | Roboti alusel, käsi stopi juures igal uuel liikumisel. |
| Multimeeter | 1 | Pumbakasti DO-liinide kontrollimiseks enne juhtmete ühendamist. | jah | ei | Kasutati Andmehõive anduri juhtmestiku ja Vout kontrolliks. |
| 3D printimise pastakahoidik, kui valmis | 1 | Markeri kinnitamiseks MG400 flantsi külge joonistamise ajal. | jah, 12.09.26 | ei | Raimo disain, kahest detailist keermega, vedru annab järele. |

**Tulemus (03.10.26):** tellimust ei olnud vaja — kõik selle labori jaoks vajalik oli riiulil
(sama järeldus nagu Andmehõive L1-s). Ainus avastatud puudus: laboriarvutil ei ole Wi-Fi
adapterit, seega Atomi täht jõuab jaama USB kaudu (vt `letter_channel.md`); eraldi Wi-Fi
adapterit ei tellitud, sest USB kanal töötab ja adminiõigusteta ei saa draiverit paigaldada.
