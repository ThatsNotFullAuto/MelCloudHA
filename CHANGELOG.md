# Changelog

## [0.2.1] - 2026-10-30

### Correzioni

- Ripristinati accenti, apostrofi, frecce, simboli di grado e menu nella
  documentazione e nei testi del wizard. Il problema era nei file generati,
  non nel browser: i caratteri erano stati sostituiti con punti interrogativi.
- Aggiunti controlli di regressione sulla codifica UTF-8.

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
