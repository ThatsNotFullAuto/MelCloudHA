# Sorgenti e compatibilità FTC — verifica documentale 30 ottobre 2026

## Come leggere lo stato

**Implementato**: esiste un percorso nel codice di questo progetto.
**Test automatici**: sole fixture sintetiche. **Documentato upstream**: capacità
dichiarata o decoder esaminato, non collaudo locale. **Reale verificato**: nessuno
in questa sessione. Il modello rappresenta FTC4–FTC7, ma autenticazione MELCloud
Home, controller e singoli parametri hanno prove separate.

| Generazione | Modello comune | MELCloud Home su quella generazione | ESPHome/Asgard upstream | SD ufficiale | EAC-MT-M1 |
|---|---|---|---|---|---|
| FTC4 | Implementato, test sintetici | Unknown | Dichiarato da firmware ≥12.01, comandi limitati | Log SD documentati storicamente; formato/tool attuale unknown | Unknown |
| FTC5 | Implementato, test sintetici | Unknown | Dichiarato; energia istantanea non disponibile | Tool elencato | Unknown |
| FTC6 | Implementato, test sintetici | Unknown | Dichiarato, limiti per trasporto/modello | Tool elencato | Compatibilità documentata |
| FTC7 | Implementato, test sintetici | Unknown | Dichiarato, limiti per trasporto/modello | Tool elencato | Compatibilità documentata |

Per tutte le righe: nessun adattatore ESPHome o importer SD/E-Monitoring operativo
in MELCloud Diagnostics. Il cloud esistente è implementato, ma la matrice per
generazione non è verificata. I servizi MELCloud classico e MELCloud Home non
sono intercambiabili. Il modello ERST20F-VM2E non certifica da solo FTC7.

## MELCloud Home

Letture allowlist `GET /context`, `/monitor/atwunit/{uuid}` e relativo `/errorlog`;
autenticazione `aiomelcloudhome==0.3.1`. Frequenze precedenti invariate: 60 secondi
e 15 minuti. La forma delle risposte è verificata soltanto contro i parser e le
fixture sintetiche del repository: nessuna prova su account reale. HTTP 401
richiede riautenticazione; 403/404 sullo storico rimangono indistinguibili fra
endpoint non disponibile e permessi insufficienti. Rate limit e errori non
producono uno storico vuoto. Guest buildings non supportati.

Sensore ambiente selezionato/presente, configurazione completa, indirizzo FTC
del guasto e valori al momento fisico del guasto non sono dimostrati leggibili.
Non vengono ricavati dal valore di temperatura o da una capability generica.

## CN105, ESPHome Ecodan e Asgard

Fonti congelate alla revisione
[`c5527d47c54150a81ed493decb77dc91cd4cf23e`](https://github.com/gekkekoe/esphome-ecodan-hp/tree/c5527d47c54150a81ed493decb77dc91cd4cf23e):
[manuale Asgard](https://github.com/gekkekoe/esphome-ecodan-hp/blob/c5527d47c54150a81ed493decb77dc91cd4cf23e/asgard/manual.md),
[protocollo](https://github.com/gekkekoe/esphome-ecodan-hp/blob/c5527d47c54150a81ed493decb77dc91cd4cf23e/protocol.md),
[decoder](https://github.com/gekkekoe/esphome-ecodan-hp/blob/c5527d47c54150a81ed493decb77dc91cd4cf23e/components/ecodan/response.cpp),
[tipi](https://github.com/gekkekoe/esphome-ecodan-hp/blob/c5527d47c54150a81ed493decb77dc91cd4cf23e/components/ecodan/proto.h),
[proxy](https://github.com/gekkekoe/esphome-ecodan-hp/blob/c5527d47c54150a81ed493decb77dc91cd4cf23e/docs/proxy.md).

| Messaggio | Significato documentato e decoder esaminato | Limite della prova |
|---|---|---|
| 0x03 | Stato/codici errore e zone | Non prova uno storico completo |
| 0x04 | Frequenza compressore | Non prova granularità adeguata ai cicli |
| 0x09 | Target zona/mandata, altri limiti | Non confondere target con temperatura misurata |
| 0x0C | Mandata, ritorno, ACS | Presenza sensori dipende dall'impianto |
| 0x10 | Richieste termostati IN1/IN6/IN5 | Non identifica sensore ambiente selezionato |
| 0x14 | Portata primaria/stati riscaldatori | Nessuna soglia ufficiale importata |
| 0x15 | Stato pompe/valvole | Non certifica cablaggio o topologia |
| 0xC9 | Identificazione controller/hardware | Decodifica parziale, non configurazione completa |

I decoder non garantiscono tutti i parametri su tutte le generazioni. Le misure
energetiche istantanee sono documentate FTC6+; FTC5 ha un limite esplicito. Sono
presenti differenze FTC7 sui termistori esterni e limitazioni service su alcuni SUZ.
Il documento e il codice possono differire: lo stato errore numerico usa nel
decoder una lettura a 16 bit, mentre una nota del protocollo riporta un'altra
formula. Non abbiamo reimplementato nessuno dei due.

Il decoder `SH_TEMPERATURE_STATE` usa `0.0` per un sentinel di temperatura non
riportata: un futuro importer dovrà preservarne l'indisponibilità e verificare
le entità effettive, evitando zero come misura automatica. Questa osservazione
documenta un rischio di interoperabilità, non una diagnosi sull'impianto.

MAC-567IF-E è un esempio nel manuale proxy; PAC-WF010-E è escluso. Non abbiamo
trovato nei documenti esaminati una prova specifica MAC-597IF-E + SL/PX + MELCloud
Home. Resta unknown. Il proxy può dipendere dai messaggi richiesti dal modulo
collegato. Il firmware offre controllo e algoritmi automatici: osservazione,
inoltro seriale e interrogazione attiva non sono la stessa cosa del monitoraggio
elettricamente passivo.

Scelta futura preferita: consumare entità ESPHome già disponibili in HA, con
mapping esplicito e senza chiamare servizi di controllo. API nativa diretta
richiederebbe connessione e gestione autenticazione aggiuntive; MQTT richiede
schema reale e broker giustificato, qui non verificati. Il manuale documenta
anche letture HTTP, ma non è ancora un contratto di importazione implementato.

[Licenza upstream](https://github.com/gekkekoe/esphome-ecodan-hp/blob/c5527d47c54150a81ed493decb77dc91cd4cf23e/LICENSE):
GPL-3.0. Non sono stati copiati codice, decoder o firmware nel progetto MIT.
Il lavoro si limita a descrizione delle capacità e interoperabilità fra componenti
indipendenti. Un eventuale incorporamento richiederebbe una valutazione separata.

## Strumenti Mitsubishi e formati

La [pagina Mitsubishi degli strumenti](https://les.mitsubishielectric.co.uk/installers/tools-and-software-downloads)
elenca SD Card Tool FTC5/FTC6/FTC7. La
[documentazione SD Alklima](https://kennisbank.alklima.nl/hc/nl/articles/36758589302801-SD-Card-Tool-bij-Ecodan-warmtepomp)
descrive sia configurazioni sia acquisizione dati; i download esaminati richiedono
accesso installatore. Il [manuale storico FTC4, §5.6](https://library.mitsubishielectric.co.uk/pdf/download_full/882)
documenta log operativi SD, senza provare il formato dei tool moderni.
Non abbiamo campioni autentici, specifiche di file, colonne, date/fusi o prova
della presenza di selezione sensori e storico completo nei file. Nessun decoder.
L'importazione futura avverrà da copie già esportate: non scriverà sulla scheda
né sul controller. Non vengono fornite qui procedure operative sulla macchina.

La [scheda EAC-MT-M1](https://alklima.nl/leveringsprogramma/warmtepompen/toebehoren/regelingen/eac-mt-m1)
documenta FTC6/FTC7, CN105 e Bluetooth LE. La
[presentazione tecnica](https://alklima.nl/software-en-apps-voor-installateurs/e-monitoring-tool)
descrive dati, impostazioni/DIP, request codes, report e download CSV. La sessione
con smartphone avvia la registrazione; per logging esteso/storico rimanda a SD.
CSV è quindi un formato dichiarato, ma schema, date e completezza non sono
verificati: occorre un export autentico anonimizzato. Nessuna prova di acquisizione
autonoma continua, integrazione HA o coesistenza con MAC-597IF-E. Non è stato
eseguito reverse engineering Bluetooth.

## Riferimenti service e P1

Negli estratti indicizzati del [manuale OCH814A, tabella 9.4.1, pagina 50](https://library.mitsubishielectric.co.uk/pdf/download_full/4940)
sono presenti 103–105 (ultimi tre guasti), 504/507 (temperature zona), 555/556
(temperature al guasto) e 567 (identificatore termistore). La denominazione del
507 nell'estratto merita confronto visivo sulla revisione esatta: non viene usata
come mapping software. La sezione guasti associa P1 alla rilevazione ambiente.
Il download completo via browser ha superato il limite dimensionale del tool;
non è stata completata una lettura integrale del manuale. OCH809A resta un
riferimento da acquisire/verificare per la revisione esatta dell'unità esterna.
Questi codici service non sono indirizzi CN105 e non generano richieste nel codice.

La [nota tecnica P1](https://kennisbank.alklima.nl/hc/nl/articles/37602867442321-P1-storing)
descrive anche selezione impropria del sensore e distingue procedure FTC5/6 e
FTC7. È una possibile pista per il tecnico, non prova della causa dei due episodi.
