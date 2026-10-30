# Aggiornamenti senza riconfigurare l’impianto

## Come arriva un aggiornamento

Quando viene pubblicata una nuova **release GitHub**, HACS può rilevarla e
mostra un aggiornamento disponibile per MELCloud Diagnostics. Il changelog
è nel dettaglio dell’aggiornamento e nella pagina della release. Un semplice
commit su main non costituisce una nuova versione per gli utenti.

La rilevazione non è istantanea: dipende dai controlli periodici di HACS.
Puoi usare **Aggiorna informazioni** nel menu della repository per anticiparla.
Questo è l’avviso nel sistema di aggiornamenti HA/HACS; una notifica push sul
telefono richiede una tua automazione e non viene attivata automaticamente.

## Procedura consigliata

1. Leggi il changelog, inclusi versione HA richiesta, migrazioni e riavvio.
2. Esegui il normale backup HA prima di aggiornare.
3. Aggiorna **l’integrazione esistente** da HACS.
4. Riavvia HA quando richiesto. Le modifiche al codice Python richiedono il
   riavvio per essere caricate; non viene riavviato automaticamente l’impianto.
5. Verifica il ritorno delle letture. Non eliminare né ricreare l’account.

## Cosa viene conservato

Il dominio `melcloud_diagnostics`, gli identificativi univoci delle entità e
il registro `.storage/melcloud_diagnostics.<entry_id>` sono contratti stabili.
La configurazione account, la selezione delle pompe e i permessi già salvati
restano nella config entry HA. Gli aggiornamenti non scrivono impostazioni
sulla pompa e non sovrascrivono le plance.

Le proposte di comando non ancora concluse vengono invalidate dal riavvio:
non vengono riprese o inviate in seguito. La cronologia FTC non viene cancellata.
Il registro locale non viene mai inserito nella cartella dell’integrazione,
che HACS sostituisce durante un aggiornamento.

Questo riduce i rischi di regressione, ma non garantisce che ogni futura
release sia priva di problemi. I cambi incompatibili devono avere migrazioni,
test e istruzioni esplicite. Non rinominare gli ID per correggere un semplice
nome visualizzato. Un cambiamento del formato di storage richiede una
migrazione separata, non la cancellazione del file esistente.

## Processo per chi rilascia

1. Modificare codice e test; verificare config entry precedenti, storico e ID.
2. Aggiornare la versione in `manifest.json` e `pyproject.toml`.
3. Aggiungere in `CHANGELOG.md` una sezione `## [versione] - data` con novità,
   effetti sui dati, compatibilità, eventuali azioni richieste e riavvio.
4. Attendere i test del branch main, inclusa la matrice sull’ultima HA stabile.
5. Creare e inviare un tag `vVERSIONE` corrispondente ai due manifest.
6. Il workflow Release riesegue i test, costruisce i pacchetti e pubblica
   release, changelog e checksum. Se i test falliscono, la release non viene pubblicata.
7. HACS usa il pacchetto `melcloud_diagnostics.zip` e la versione minima HA
   dichiarata in `hacs.json`. Non ripubblicare lo stesso tag con codice diverso.

Il workflow settimanale sull’ultima stabile segnala incompatibilità nuove:
non aggiorna i sistemi degli utenti e non pubblica una release da solo.

## Tornare alla versione precedente

Leggi prima le note della versione: una migrazione futura potrebbe non essere
reversibile. Se non ci sono cambi di schema, HACS permette di riscaricare una
versione precedente. Riavvia poi HA. In caso di dubbi usa un backup coerente
con quella versione, preservando sia configurazione sia registro.

La prima pubblicazione 0.2.0 mantiene schema e ID del prototipo 0.1.0.
