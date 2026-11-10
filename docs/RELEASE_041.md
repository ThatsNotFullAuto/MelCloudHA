# MELCloud Diagnostics 0.4.1 — report più precisi

Questa release ordinaria corregge alcune ambiguità dei rapporti di Collaudo.
Una lettura senza valore utilizzabile non viene più descritta automaticamente
come campo assente nel cloud. Il risultato mantiene il formato JSON schema 1.

Un report utente ha permesso di verificare offline letture e storico per una
unità. Nessun collaudo fisico indipendente è stato eseguito: questa evidenza
non certifica tutte le generazioni FTC, la freschezza dei dati o la causa P1.
I dati privati non sono inclusi nella repository o nelle fixture pubbliche.

## Cosa cambia

- Le assenze si basano sull'inventario strutturale pertinente. Campo presente
  con valore nullo, vuoto, non interpretabile o redatto non diventa assente.
  Inventario insufficiente o troncato lascia la conclusione indeterminata.
- Il fallback del flag errore e le letture di operazioni differenti vengono
  trattati prudentemente; un flag mancante, stale o invalido non attesta P1 attivo.
- Il lettore offline distingue codici correnti, flag di errore, record storici
  e presenza del campo FTC. Il modello FTC grezzo non viene esportato.
- `code_readable` conserva il significato di codice corrente interpretabile;
  può essere falso anche quando lo storico contiene P1 leggibili.
- Un FTC `unknown` può avere un campo `ftcModel` presente ma non riconosciuto.
  Le sole etichette esplicite FTC4–FTC7 vengono riconosciute anche con maiuscole
  miste e spazi esterni: ad esempio `ftC7` diventa `FTC7`. Il sensore conserva
  il testo originale; modelli di unità e numeri firmware non vengono interpretati.
  Il riconoscimento della dichiarazione non certifica capacità hardware o cloud.

I contatori `decoded_parameters` mantengono la semantica dei valori normalizzati.
La lista degli assenti vuota non dimostra completezza del cloud. I metadati di
schema 1 sono aggregati: non provano un collegamento temporale individuale fra
ogni frame dello schema e ogni acquisizione. Non ricostruiscono valori perduti.

L'interfaccia conserva quella della 0.4.0. Gli screenshot documentali restano
catture autentiche della 0.4.0 con dati sintetici, pertinenti anche a questa patch.

## Come ricevere l'aggiornamento su Home Assistant

La repository personalizzata già aggiunta in HACS non deve essere reinserita.
Dopo la pubblicazione HACS può rilevare la versione ordinaria **0.4.1** tramite
i propri controlli periodici; la rilevazione non è istantanea.

1. Fare un backup HA protetto e verificato e conservare il pacchetto precedente.
2. Aprire **HACS → MELCloud Diagnostics** e scegliere **Aggiorna** alla 0.4.1.
   Se non compare, aggiornare le informazioni della repository dal suo menu;
   in alternativa **Scarica di nuovo / Redownload → v0.4.1**.
3. **Riavviare Home Assistant** in un momento opportuno. Il codice Python nuovo
   richiede il riavvio. Non eliminare né ricreare l'integrazione.
4. Verificare versione 0.4.1 e ritorno delle normali letture, mantenendo i
   controlli manuali disabilitati per il Collaudo.

Config entry, credenziali, ID, dashboard e journal restano quelli esistenti.
Nessuna migrazione, nuovo endpoint, polling aggiuntivo o comando alla pompa.
Nessuna installazione o riavvio remoto viene eseguito dallo sviluppatore.

## Come verificare il risultato

Si può scaricare il report conservato da **⋮ dell'account → Scarica la diagnostica**:
la valutazione delle assenze usa la correzione anche sui dati già conservati,
nei limiti delle evidenze disponibili. Il file originale esportato dall'utente
non viene riscritto. Lo schema e il significato dei contatori restano invariati.

Una sessione precedente conserva la versione software originaria nei metadati.
La normalizzazione FTC corretta si applica alle nuove acquisizioni: un vecchio
report `unknown` non contiene il testo originale necessario per riclassificarlo.
Per registrare una sessione con versione 0.4.1, esportare prima la precedente,
poi avviare un Collaudo autorizzato di **20 minuti**, consentendone la sostituzione.
Confrontare nell'app soltanto le letture già visibili. Non cambiare setpoint,
modalità o sensori e non provocare guasti.

## Compatibilità e ripristino

I report schema 1 rimangono leggibili senza nuovi campi. Un ritorno alla 0.4.0
conserva il formato, ma ripristina anche le interpretazioni precedenti delle
assenze. Conservare report esportato e backup coerente; non cancellare journal
o configurazioni. Il downgrade completo su impianto reale non è stato eseguito.

## Limiti ancora presenti

P1 storico non equivale a un guasto attivo né a un numero certo di episodi.
La causa P1, selezione/presenza del sensore e lettura TH1A/TH1B restano sconosciute.
CN105/Asgard e importazione SD non sono implementati. Le 24 ore restano disabilitate.
La patch non aggiunge un nuovo profilo di acquisizione o valori testuali sconosciuti.

[Guida al Collaudo](COLLAUDO_GUIDATO.md) ·
[Requisiti e compatibilità](REQUISITI_E_COMPATIBILITA.md) ·
[Guida P1](GUIDA_DIAGNOSTICA.md).
