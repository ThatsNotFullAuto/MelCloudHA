# Changelog

## [0.4.0] - 2026-10-30

**Release ordinaria. Nessun collaudo con account Mitsubishi o impianto reale
è stato eseguito. Screenshot del frontend HA reale con dati sintetici.**

### Aggiunto

- **Collaudo diagnostico guidato**: selezione pompa, 20/60 minuti, avvio,
  stato, barra reale, durata, tempi, contatori e stop della sola raccolta.
- Session manager indipendente dal wizard: chiudere il browser non ferma il
  lavoro. Scadenza, stop, reload e riavvio conservano risultati coerenti;
  nessuna ripresa automatica dopo riavvio. Le 24 ore restano disabilitate.
- Vista Diagnostica nativa con tile/bar-gauge e ID risolti dal registro.
  Nessuna sovrascrittura automatica delle plance personalizzate.
- Rapporto JSON schema 1 tramite **Scarica la diagnostica** di HA: fatti,
  inventario cloud, dati mancanti, evidenze P1, controlli deterministici e
  confronto manuale separati dalla verifica fisica.
- Inventario limitato prima del parsing, alias per campi ignoti senza valori
  grezzi, allowlist ricorsiva e consenso separato ai numeri tecnici conosciuti.
- **11 screenshot autentici**, inclusi smartphone, tema scuro, plancia, wizard
  e assistenza; harness e cattura ripetibili solo per sviluppo.
- [Requisiti e compatibilità](https://github.com/ThatsNotFullAuto/MelCloudHA/blob/v0.4.0/docs/REQUISITI_E_COMPATIBILITA.md):
  HA ≥2026.10.4, Python ≥3.14.2 nell'ambiente HA, account MELCloud Home e rete;
  nessun hardware aggiuntivo o plugin frontend.

![Collaudo diagnostico — UI reale con dati sintetici](https://raw.githubusercontent.com/ThatsNotFullAuto/MelCloudHA/v0.4.0/docs/images/diagnostics-collaudo-running.png)

### Affidabilità e sicurezza

- Nessun comando operativo, nuovo GET, refresh o retry Mitsubishi. I controlli
  manuali devono essere spenti; abilitarli durante una sessione invalida e ferma
  la raccolta con motivo esplicito, anche se reload/storage falliscono.
- Handoff non bloccante, coda 4, elaborazione fuori dai lock del journal,
  report 1 MiB, campioni/eventi/schema limitati, timer locale 30 secondi senza
  scritture al tick. Circuit breaker del solo Collaudo; acquisizione ordinaria
  e storage storico indipendenti.
- Storage separato, atomico e verificato; report parziale recuperabile.
  File assente/corrotto non azzera il journal. Un disco guasto può impedire
  nuovi checkpoint; non si garantiscono dati RAM dopo crash.
- Durate leggibili, stati tradotti, layout responsive e contatori PASS/FAIL
  coerenti con report e checkpoint anche dopo un errore di persistenza.
- Ordinamento ZIP esplicitamente lessicografico, per checksum riproducibili
  anche fra Windows e Linux; regressione verificata prima e dopo la correzione.
- Suite sintetica e frontend HA 2026.10.4/Chromium verificati. Un'ora simulata:
  **64 GET con e senza Collaudo**, stesso journal. Zero GET aggiuntivi allo stop.
  I job CI registrano la versione risolta: pinned/latest uguali non sono due
  versioni HA differenti. Nessuna nuova dipendenza runtime.

### Aggiornamento, primo collaudo e ripristino

Fare backup protetto e verificato. In **HACS → MELCloud Diagnostics → Aggiorna**
scegliere **v0.4.0**, quindi **riavviare Home Assistant**. Se necessario:
**⋮ → Scarica di nuovo / Redownload → v0.4.0**. Non eliminare l'integrazione.
Config entry, credenziali, ID entità/dispositivi, preferenze e journal storage 1
sono preservati; le nuove entità hanno ID separati. Aggiungere la vista
Diagnostica dal YAML generato senza sostituire la propria dashboard.

Prima prova autorizzata su HA isolata, controlli manuali disabilitati:
**Configura → Diagnostica → Collaudo diagnostico → 20 minuti**. Osservare
reattività, risorse, normali letture e funzionamento dell'app Mitsubishi.
**Interrompi collaudo** ferma soltanto la registrazione. Non provocare guasti
o modificare setpoint/modalità. Al termine usare **⋮ dell'account → Scarica la
diagnostica**; il JSON contiene `data.diagnostic_test`, anche parziale.
Con una sessione conservata il download restituisce il report ristretto invece
del precedente report libero; nessuno storico viene cancellato.
Controllare privacy, date e metadati HA prima di condividere con Codex o nelle
[issue](https://github.com/ThatsNotFullAuto/MelCloudHA/issues).

La **v0.3.0 resta disponibile**. Esportare e fermare la raccolta, scegliere
v0.3.0 in Scarica di nuovo e riavviare HA. Non eliminare config entry o journal.
Il vecchio codice ignora lo storage separato del Collaudo. Downgrade completo
su impianto reale non verificato: conservare un backup coerente, che riporta
i dati alla propria data. Nessun ripristino di parametri sulla pompa.

### Limiti

- Primo account Mitsubishi reale, prestazioni sul target e coesistenza con
  integrazione ufficiale/automazioni ancora da collaudare. Viewport mobile
  verificata, non telefono fisico o tutti i browser.
- FTC4–FTC7: modello e capacità architetturali, non diagnostica di servizio completa.
- Causa P1 non identificata; lettura/selezione TH1A/TH1B non verificata.
- CN105/Asgard e importazione SD non implementati; proxy MAC-597IF-E sconosciuto.
- Nessun acquisto hardware richiesto, nessun nuovo comando verso la macchina.

[Guida completa 0.4.0](https://github.com/ThatsNotFullAuto/MelCloudHA/blob/v0.4.0/docs/RELEASE_040.md) ·
[Collaudo guidato](https://github.com/ThatsNotFullAuto/MelCloudHA/blob/v0.4.0/docs/COLLAUDO_GUIDATO.md).

## [0.3.0] - 2026-10-30

**Release ordinaria del software disponibile. Nessun collaudo con account o impianto
Mitsubishi reale è stato eseguito. La 0.2.1 resta disponibile come versione precedente.**

### Aggiunto

- Fondamenta multi-sorgente FTC4–FTC7: osservazioni normalizzate con provenienza,
  disponibilità, validazione e timestamp separati.
- Registry delle capacità con evidenze e contesto; ciò che non è verificato
  resta unknown. Contratti astratti per sorgenti future, senza driver operativi.
- Report diagnostico con fatti normalizzati e stato della persistenza;
  validatore offline che non stampa valori o identificativi.
- Procedura di collaudo cloud sicuro, backup e ripristino.

### Migliorato

- Consolidamento persistenza: scritture HA atomiche con rilettura di conferma;
  file corrotti o scomparsi durante l'esecuzione non vengono reinizializzati.
- Commit del journal isolati dallo stato pubblicato, conservati in attesa dopo
  errori/timeout e ritentati prima di nuove acquisizioni. Cancellazioni durante
  la scrittura attendono l'esito; uno storico interrotto conserva gli snapshot
  già acquisiti. Nessun replay delle notifiche al riavvio.
- Eventi diagnostici con `event_id`; nuove notifiche storiche conservate anche
  nelle osservazioni con timestamp distinto di acquisizione. Campi opzionali
  compatibili con storage 1; nessuna rinominazione o conversione distruttiva.
- Filtrati placeholder unknown/unavailable, misure non numeriche e variazioni
  puramente di formato. Codici guasto confrontati senza differenze di maiuscole;
  chiavi storiche precedenti preservate. Rifiutati ID duplicati nel context.
- Report con stato persistenza/consegna notifiche e validatore offline dei dati
  cloud/report già acquisiti, senza stampa di payload, valori o identificativi.
- Procedura di collaudo cloud reale preparata, non eseguita. Nessun accesso
  remoto, account Mitsubishi, deploy o modifica del codice di controllo.

- Fondamenta del modello diagnostico comune FTC4/FTC5/FTC6/FTC7: fatti tipizzati,
  origine, acquisizione, disponibilità e validazione separate. Nessuna compatibilità
  hardware o cloud dedotta dal solo modello FTC.
- Registry delle evidenze con contesto modello/firmware/adattatore/trasporto;
  assenza o ambiguità delle prove restituisce `unknown`.
- Vista normalizzata degli snapshot cloud nel coordinator e nel report, senza
  richieste aggiuntive; confronto multi-sorgente puro, senza vincitore automatico.
- Contratti per telemetria locale e importazione offline. Nessun driver locale,
  decoder proprietario, soglia termica o azione correttiva implementati.
- Corretto il registro: campi nulli o codice temporaneamente assente non devono
  simulare cambi di regolazione o duplicare un guasto ancora attivo.
- Test sintetici multi-generazione, disponibilità, timestamp, confronto,
  persistenza, assenza di nuove scritture e packaging isolato.
- Build con `--output-dir` per verificare HACS senza sovrascrivere pacchetti precedenti.
- Nessuna migrazione di config entry/storage, nuova dipendenza o modifica dei
  permessi di controllo. Necessario riavvio HA per caricare codice nuovo.
- Packaging riproducibile, controllo delle versioni SemVer/PEP 440, checksum,
  inventario ZIP e pubblicazione in bozza fino a verifica degli asset GitHub.
- Il publisher riconosce le prerelease e non le imposta come ultima stabile.

### Limitazioni

- Supporto FTC4–FTC7 architetturale: non certifica tutte le sorgenti o installazioni.
- Nessun collaudo reale. Autenticazione, completezza storico e dati cloud restano
  da verificare nell'account autorizzato.
- CN105/Asgard non integrati; importazione SD Mitsubishi non implementata.
- Selezione sensore TH1A/TH1B non leggibile in modo verificato.
- Compatibilità proxy MAC-597IF-E sconosciuta. Nessun acquisto hardware richiesto.
- Notifiche HA best effort; il journal conserva gli eventi salvati senza replay.

### Aggiornamento, assistenza e ripristino

In HACS aprire MELCloud Diagnostics e scegliere **Aggiorna** alla **v0.3.0**,
oppure menu ⋮ → **Scarica di nuovo / Redownload**, selezionando v0.3.0.
Fare prima un backup HA protetto e **riavviare Home Assistant** dopo
l'aggiornamento. Non cancellare né ricreare l'integrazione.

Config entry, credenziali, ID entità/dispositivi, dashboard e involucro storage 1
sono preservati; i nuovi campi sono opzionali. Non serve una migrazione distruttiva.
La modalità iniziale resta sola lettura; le opzioni esistenti non vengono riscritte.
Per il collaudo verificare che le modifiche siano disabilitate. Nessun comando
aggiunto e nessuna frequenza di polling aumentata.

Per assistenza: **Configura → Assistenza**, poi **Scarica diagnostica** dal menu
dell'integrazione. Controllare il report prima di condividerlo e segnalare problemi
su https://github.com/ThatsNotFullAuto/MelCloudHA/issues, indicando versione HA e
orario/fuso. Non allegare credenziali o backup e non provocare guasti sulla pompa.

Per tornare alla **v0.2.1**, selezionarla in Scarica di nuovo e riavviare HA;
conservare config entry e registro. I campi aggiuntivi dello storage 1 sono
leggibili nei test sintetici con Store HA 1. Il downgrade completo su HA reale
non è stato collaudato. Usare un backup coerente se necessario; il ripristino riporta i dati
alla data del backup. Non ripristinare parametri sulla pompa.

## [0.2.1] - 2026-10-30

### Correzioni

- Ripristinati accenti, apostrofi, frecce, simboli di grado e menu nella
  documentazione e nei testi del wizard. Il problema era nei file generati,
  non nel browser: i caratteri erano stati sostituiti con punti interrogativi.
- Aggiunti controlli di regressione sulla codifica UTF-8.
- Aggiunte anteprime illustrative della plancia, del wizard e dell’assistenza,
  etichettate come dati fittizi, e chiarimenti sulle dipendenze automatiche.

### Diagnostica

- Logging di debug attivabile dal menu standard dell’integrazione in HA.
- Log di operazioni cloud, stato HTTP, tempi, errori di lettura, wizard e
  conferme. Nessuna registrazione di password, token, identificativi unità
  o risposte cloud integrali nei messaggi di debug del progetto.
- Report con versioni, stato delle acquisizioni, ultime richieste e snapshot
  disponibili. La cronologia tecnica in memoria è limitata a 100 richieste.
- Guida italiana per raccogliere log e report, e disattivare il debug.
- Percorso Assistenza per scegliere il problema e recuperare il JSON con
  riferimento univoco e formato versionato; lettore del report per chi sviluppa.

### Aggiornamento

- Riavviare Home Assistant dopo l’aggiornamento del codice.
- Nessuna migrazione dei dati; configurazione, entità, storico e plance
  restano invariati. Le proposte di modifica pendenti non vengono riprese.
- Nessuna modifica dei parametri dell’impianto e nessun nuovo comando di controllo.

## [0.2.0] - 2026-10-30

Prima pubblicazione su GitHub e HACS. Versione iniziale da validare sull'impianto reale.

### Novità

- Wizard: ricerca account MELCloud Home già presenti in HA, riuso esplicito,
  accesso manuale, scelta delle pompe e riepilogo in sola lettura.
- Ricerca mDNS limitata a dispositivi ESPHome riconoscibili e indicazione
  separata dei dispositivi già registrati in HA. I candidati non sono
  identificazioni certe della MAC-597IF-E.
- Sensori di stato, temperature, codice guasto e disponibilità storico.
- Registro persistente dei guasti e delle variazioni osservate.
- Modifiche manuali opzionali, disabilitate di default, con due conferme,
  scadenza, controllo dei valori e nessun reinvio automatico.
- Icona originale e varianti chiare/scure locali; plancia nativa generata
  con le entità effettive, senza schede personalizzate o comandi.
- Documentazione italiana per prima configurazione, plancia e aggiornamenti.

### Compatibilità e aggiornamento

- Verificata con HA Core 2026.10.4, ultima stabile al 30 ottobre 2026.
- Dominio, identificativi delle entità e registro persistente restano quelli
  del prototipo 0.1.0. Credenziali e impostazioni non vengono azzerate.
- Non eliminare e ricreare l'integrazione per aggiornare.
- Riavviare Home Assistant dopo l'installazione/aggiornamento del codice Python.
- Le proposte di modifica pendenti vengono invalidate al riavvio.
- Le plance già create non vengono sovrascritte.

### Limiti

Test con dati sintetici: nessun collaudo con account Mitsubishi o impianto
reale. Setpoint di mandata, commissioning, reset e scritture Asgard esclusi.
Il cloud potrebbe non fornire storico completo o tutti i sensori.
