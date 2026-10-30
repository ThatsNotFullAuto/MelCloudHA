# Consolidamento locale: affidabilità e preparazione al collaudo

Rapporto del checkpoint pre-release (154 test). Il lavoro è incluso nella
release [0.3.0](RELEASE_030.md); numeri di versione e stato Git sotto descrivono
il momento del checkpoint, non lo stato della pubblicazione successiva.

Secondo ciclo, successivo al [checkpoint multi-sorgente](AUDIT_FTC_2026-10-30.md).
Branch main, HEAD `962e5cd56cab899972f7fbec1427b5c9100a7202`, versione 0.2.1.
Baseline verificata nuovamente: 105 test e Ruff superati. Preservati tutto il diff
precedente e `codex.txt`. Nessuna operazione remota, commit, push, tag, release,
accesso a Mitsubishi o installazione reale. Nessun ampliamento Asgard/SD.

## Criticità risolte

| Criticità | Correzione e prova |
|---|---|
| Journal modificato prima del save | Copia di lavoro; adozione dopo conferma |
| Store HA può loggare senza rilanciare WriteError | Scrittura atomica + rilettura del file; test contro Store HA reale in directory temporanea |
| Save fallito perde la possibilità di notificare la transizione al retry | Commit esatto conservato e recuperato prima di nuove letture |
| Esito save incerto dopo scrittura effettiva | Retry identico; riavvio legge il journal salvato senza replay |
| Cancellazione abbandona il task mentre l'executor scrive | Scrittura protetta; lock mantenuto fino all'esito, anche con cancellazioni ripetute |
| Errore auth/cancellazione nello storico dopo snapshot acquisito | Persistenza dei fatti già disponibili prima della propagazione |
| Audit concorrente perso dal poll | Lock comune; copia dello stato più recente al commit |
| Notifiche storiche non presenti nelle osservazioni | Persistite con event_id e orario acquisizione separato dalla data guasto |
| Unknown/null, valori non numerici e rappresentazioni equivalenti | Filtraggio della baseline, confronto numerico senza cambiare valori entità |
| Maiuscole nel codice generano nuovo guasto | Identità normalizzata, chiavi legacy conservate |
| Snapshot precedente arretra la baseline | Watermark opzionale per unità |
| Context con ID duplicati sovrascritto silenziosamente | Rifiuto DataError, anche nel validatore offline |
| File corrotto trattato come registro vuoto | Validazione e arresto del salvataggio, senza cancellazione/riparazione automatica |

## File e contratti

Aggiunti `custom_components/melcloud_diagnostics/storage.py`,
`core/schema.py`, `tools/validate_cloud_data.py`, `tests/test_reliability.py`,
`tests/test_cloud_schema.py` e tre documenti: questo rapporto,
`COLLAUDO_MELCLOUD_HOME.md`, `VALIDAZIONE_DATI_CLOUD.md`.
`core` è relativo alla cartella dell'integrazione.

Modificati coordinator, inizializzazione store, journal, modelli, normalizzatore
cloud, controllo duplicati cloud, report, support envelope, `.gitignore` e le
guide pertinenti. Nessuna modifica a `core/control.py`, funzioni writer, sensori,
entità, dashboard, flussi account o manifest. Nessuna nuova dipendenza.

Storage envelope 1 e config entry 1.1 invariati. Aggiunte opzionali per
`previous_observed_at` ed `event_id`; i dati precedenti vengono letti senza
conversione distruttiva. Test di caricamento con Store HA precedente e lettura
del nuovo registro con Store HA versione 1. ID entità e snapshot raw restano
quelli esistenti. Le nuove semantiche di validazione riguardano i dati assenti o
invalidi e la deduplicazione, non introducono soglie Mitsubishi.

`persistence_state` e nuovi findings nel report sono aggiunte allo schema support
1. Il validatore offline non acquisisce dati e non stampa valori o identificativi.
Accettazione dello schema e completezza fisica rimangono verifiche separate.

## Test e verifica locale

Comandi di verifica dalla root:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check custom_components tests tools
.venv/Scripts/python.exe tools/build_release.py --output-dir dist/validation-reliability
git diff --check
```

I nuovi test sono interamente sintetici. Coprono riavvii, storage OSError/timeout,
scrittura riuscita seguita da errore, cancellazione snapshot/storico/save,
cancellazioni ripetute, recupero prima di nuove acquisizioni, audit concorrente,
notifica fallita, duplicati e P1 ricorrente dopo cessazione confermata. Inclusi
Store HA con errore atomico loggato, file eliminato/corrotto e shutdown differito.
Lo stesso audit transazionale è verificato con il gate esistente: save fallito
impedisce il writer e non riprende il comando dopo il recupero.

Il validatore è provato con report HA, report precedenti, dati normalizzati,
placeholder, timezone mancanti, contenitori errati, ID duplicati e CLI con JSON
invalido. Test di privacy verificano che dati e segreti sintetici non compaiano
nel risultato. I precedenti test di entità/ID/storico/gate/multi-sorgente/HACS
restano nella suite completa. Esito locale finale: **154 test superati**, 49 in
più della baseline, Ruff e build HACS superati, `git diff --check` senza errori.

Non eseguiti latest HA/CI remota, frontend completo, account/API live, deploy,
dispositivi o hardware. Ambiente locale verificato HA 2026.10.4/Python 3.14.3;
rimane il warning HA/aiohttp già presente nella baseline. Pacchetti isolati in
`dist/validation-reliability`, con versione ancora 0.2.1: non sono release.

## Garanzie e rischi residui

Nuova persistenza e validatore non hanno accesso a comandi di impianto. Il trasporto
cloud continua a usare GET diagnostici alle frequenze esistenti, con allowlist,
timeout e backoff precedenti. Il codice di controllo rimane invariato; il token
account conserva comunque i privilegi del servizio. La garanzia read-only è
applicativa e non limita altre integrazioni presenti in HA.

Il journal salvato è autorevole. Il bus HA non ha ricevute: dopo un arresto fra
commit e consegna una notifica può mancare, ma l'evento resta nel registro e non
viene reinviato automaticamente. `event_id` permette di correlare evento e record;
non trasforma il bus in una coda con consegna esattamente una volta.

Una perdita di alimentazione/kill prima di qualsiasi save riuscito può perdere
il commit ancora solo in RAM. Non è possibile garantire persistenza con disco
indisponibile. Una scrittura protetta può ritardare la cancellazione mentre l'I/O
si completa; non viene imposto un timeout che abbandoni l'executor. Atomicità e
rilettura verificano il risultato del filesystem, non certificano l'hardware
contro ogni perdita di alimentazione.

La scomparsa del file viene rilevata durante la vita dello store. Se manca già
al primo caricamento, non è distinguibile da un'installazione nuova senza una
prova esterna: serve il backup. File invalidi o futuri non vengono azzerati; il
recupero è manuale a HA di prova fermo. Retention invariata: ultimi 1000 eventi
per unità e 1000 tentativi; lo storico guasti non viene eliminato. Le nuove
notifiche storiche condividono il limite delle osservazioni.

Restano ignote accuratezza/completezza dei dati cloud reali e selezione/presenza
del sensore ambiente. Nessuna causa P1 assegnata; nessuna compatibilità FTC nuova.
Un timestamp di osservazione non è l'istante fisico della variazione.

## Collaudo e decisione successiva

La [procedura concreta](COLLAUDO_MELCLOUD_HOME.md) comprende backup protetto,
HA di prova minimale, sola lettura, finestra di almeno 20 minuti, confronto
con app/display, reload, report e validazione offline, criteri di arresto e
rollback. È soltanto preparata e richiede autorizzazione prima di eseguirla.

La stessa procedura elenca sei condizioni oggettive prima di valutare Asgard:
identificazione controller, inventario dei limiti cloud, evidenza specifica
MAC-597IF-E/proxy, dati locali utili e interpretabili, firmware/adattatore sicuri,
piano tecnico autorizzato. Nessuna di queste prove hardware viene dedotta dal
superamento dei test software.
