# Changelog

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
