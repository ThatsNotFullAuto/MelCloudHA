# Raccogliere informazioni per l’assistenza

La modalità di debug serve a capire perché una lettura, una connessione o
un passaggio del wizard non funziona. **Non abilita modifiche sulla pompa**
e non richiede di provocare un guasto o cambiare una temperatura.

## Procedura guidata

Per una prima segnalazione basta il report strutturato:

1. Apri **Configura → Assistenza · prepara diagnostica**.
2. Scegli il problema e segui le istruzioni della schermata **Report pronto**.
3. Chiudi la finestra e usa **Scarica diagnostica** nel menu dell’account
   dell’integrazione. Allega quel file JSON senza modificarlo.

Non serve attivare i log di debug per il primo report. Il file include la
categoria scelta, un riferimento univoco e i dati tecnici utili. La categoria
preparata resta disponibile fino al prossimo riavvio o reload: scarica il
report prima di riavviare. Anche senza preparazione è sempre possibile usare
Scarica diagnostica; la categoria risulterà semplicemente non specificata.

Se il creatore richiede anche i log dettagliati:

1. Apri **Impostazioni → Dispositivi e servizi → MELCloud Diagnostics**.
2. Nel menu **⋮**, scegli **Abilita registrazione debug**.
3. Ripeti soltanto l’operazione che presenta il problema, ad esempio aprire
   il wizard o attendere un aggiornamento dei sensori. Per una lettura
   ordinaria attendi almeno un minuto; lo storico viene letto ogni 15 minuti.
4. Torna nello stesso menu e scegli **Disabilita registrazione debug**:
   HA propone il download del file di log.
5. Seleziona anche **Scarica diagnostica**, nello stesso menu.
6. Prima di condividere i file, controllane il contenuto. Nella segnalazione
   indica cosa ti aspettavi, cosa è successo e l’orario approssimativo.

L’esportazione standard dei log HA può contenere messaggi di altre
integrazioni: non pubblicare il file completo senza averlo controllato.
Il report di questa integrazione è più mirato, ma contiene date, codici e
valori tecnici dell’impianto.

Se l’integrazione non è ancora configurata e il menu non è disponibile,
puoi chiedere a chi gestisce HA di abilitare temporaneamente il logger
`custom_components.melcloud_diagnostics` e ripetere il wizard. Non serve
abilitare il debug globale o quello della libreria di autenticazione.

## Cosa viene registrato

- Tipo di operazione: scoperta account, lettura unità, storico o richiesta
  di modifica già autorizzata.
- Esito, codice HTTP, durata e tipo di errore tecnico, senza il testo
  integrale dell’eccezione o della risposta cloud.
- Numero di account trovati, candidati locali e pompe selezionate.
- Rilevazione di storico non disponibile e completamento delle acquisizioni.
- Passaggi delle conferme e stato dell’eventuale richiesta, senza token
  di conferma o reinvii automatici.

Il report include versioni di integrazione, HA, libreria e Python; ultimo
aggiornamento riuscito; ultimi stati HTTP; contatori e al massimo **100
richieste recenti**, dall’ultimo caricamento dell’integrazione. Le informazioni
operative in memoria non sostituiscono lo storico guasti persistente.

I log del progetto non includono email, password, token OAuth, token di
conferma, URL con identificativi delle unità o payload cloud completi.
Il report assegna nomi come `unit_1` alle unità e include solo i campi
diagnostici previsti. I valori mancanti restano sconosciuti.

## Limiti

Il debug può aiutare a distinguere errori di autenticazione, rete, limiti
del cloud e formati dati inattesi. Non garantisce la diagnosi fisica della
pompa: la selezione TH1A/TH1B e i dati non esposti da Mitsubishi restano
non disponibili anche con il debug attivo.

Disattiva il debug dopo la raccolta: evita un volume inutile di log.
Mantieni invece il normale monitoraggio e lo storico guasti.

## Formato per il creatore dell’integrazione

Il JSON usa l’involucro standard di HA. Nei dati dell’integrazione, `support`
identifica il formato `melcloud_diagnostics.support`, la versione di schema
`1`, il riferimento del report, la data, la categoria e gli indicatori rilevati.
`versions`, `transport_health`, `units` e `commands` contengono i dettagli.
Le unità sono pseudonimizzate e i campi sconosciuti restano null o assenti.

Per un riepilogo leggibile, chi sviluppa può eseguire:

```text
python tools/read_support_report.py percorso-del-report.json
```

Il formato ha una versione propria, separata da quella dell’integrazione:
un suo cambiamento incompatibile richiederà un nuovo numero di schema.

## Fatti normalizzati nella 0.3.0

`units.unit_N.normalized_telemetry` è un'aggiunta compatibile allo schema report 1.
Comprende parametro, valore, unità, `acquired_at`, eventuale `origin_at`, fonte,
generazione dichiarata, disponibilità, validazione e revisione protocollo se nota.
La sorgente cloud attuale non fornisce qui una data originaria verificata:
`origin_at` resta null. Anche la revisione resta null.

Confrontare `acquisition_state`, `last_successful_poll` e l'età delle misure:
un guasto di rete può coesistere con l'ultimo valore noto, che non diventa una
nuova misura riuscita. Dopo 180 secondi il report lo marca `stale`. Le entità HA
mantengono la gestione precedente della disponibilità tramite coordinator.
Il report omette identificativo unità e istanza sorgente dai fatti esportati;
non esporta campi arbitrari del payload. Date e dati tecnici restano da controllare
prima della condivisione. Vedi [modello e limiti](MODELLO_DIAGNOSTICO.md).

## Persistenza e validazione prima del collaudo

`persistence_state` aggiunge `pending_commit`, tipo/data dell'ultimo errore di
storage, conteggio errori di notifica e politica `best_effort_no_replay`.
Il blocco `support.findings` può indicare `journal_commit_pending`,
`journal_storage_error` o `notification_delivery_failed`. Lo schema report resta
1: sono campi aggiuntivi, non sostituzioni. `acquisition_state.last_error.phase`
distingue snapshot, storico e storage; non contiene payload o messaggi di errore
provenienti dal server. Un valore già salvato non significa che lo storico
successivo sia riuscito.

Il validatore [offline](VALIDAZIONE_DATI_CLOUD.md) produce una mappa dei soli
campi esposti, mancanti o invalidi. Non stampa valori, ID, nomi o segreti e non
contatta Mitsubishi. Non cancella o corregge file. Un errore del registro richiede
verifica dello storage/backup, non cancellazione del file né reset della pompa.
