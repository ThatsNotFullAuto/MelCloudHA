# Aggiornamenti senza riconfigurare l’impianto

## Release 0.3.0

Seguire la [guida 0.3.0](RELEASE_030.md) per aggiornare dal normale canale
HACS. Tag v0.3.0, manifest/costante/Python 0.3.0. Riavvio HA richiesto,
nessuna modifica sulla pompa.
Config entry 1.1 e storage 1 compatibili con 0.2.1, senza reset o migrazione
distruttiva. Fare backup prima dell'aggiornamento. Per tornare indietro scegliere
v0.2.1 in HACS e riavviare, preservando account e registro.

La pubblicazione ordinaria rende la 0.3.0 latest. ZIP HACS esatto:
`melcloud_diagnostics.zip`. Il workflow verifica entrambe le versioni HA previste,
crea una bozza, carica gli asset e ne controlla dimensioni e digest prima di renderla
pubblica con prerelease=false. Una bozza incompleta non va pubblicata manualmente.

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

## Checkpoint locali precedenti (storico)

I paragrafi seguenti documentano le build locali precedenti al versionamento
della 0.3.0. Per installare la versione corrente usare la guida sopra.

Questo incremento mantiene config entry 1.1, storage 1, versione pacchetto 0.2.1,
dominio, identificativi e dashboard. Nessuna migrazione o riconfigurazione è
necessaria. La vista normalizzata si ricostruisce al poll successivo; lo storico
precedente viene letto come prima. Il registro ignora valori nulli nelle variazioni.

Prima di un eventuale collaudo autorizzato, salvare un backup HA coerente che
comprenda configurazione e `.storage/melcloud_diagnostics.<entry_id>`. Il rollback
del codice alla 0.2.1 non richiede conversione del registro; ripristinare il backup
solo se occorre recuperare anche lo stato precedente. Non eliminare config entry
o registro e non ripristinare impostazioni sulla pompa. Questa sessione non esegue
installazioni, ripristini o prove sull'impianto reale.

Per una verifica locale dei pacchetti senza sostituire quelli già in `dist`:

```powershell
.venv/Scripts/python.exe tools/build_release.py --output-dir dist/validation-ftc-foundation
```

Il pacchetto ottenuto è soltanto un artefatto di verifica, con versione ancora
0.2.1: non caricarlo su GitHub né sostituire gli asset della release pubblicata.

## Consolidamento persistenza e ripristino

Il consolidamento aggiunge soltanto campi opzionali allo storage 1; i test
leggono registri precedenti e verificano che Store HA 1 legga ancora quelli nuovi.
Non occorre ricreare account o entità. File corrotti, futuri/non riconosciuti e
file scomparsi durante l'esecuzione bloccano il salvataggio invece di essere
azzerati. Non modificarli manualmente per aggirare il controllo.

In caso di errore: conserva il report e una copia protetta del registro; interrompi
l'istanza HA di prova, verifica spazio/permessi e ripristina un backup coerente
di configurazione e storage. Riavvia e confronta guasti e ID. Ripristinare una
versione precedente del codice non richiede conversione dei campi aggiuntivi;
un ripristino del backup riporta anche la storia al momento del backup.
Se il file manca già al primo caricamento, il software non può distinguere una
prima installazione da una cancellazione precedente: serve il confronto con il
backup. Nessun ripristino dell'impianto è necessario.

Per il pacchetto di questo secondo ciclo usa una destinazione distinta:

```powershell
.venv/Scripts/python.exe tools/build_release.py --output-dir dist/validation-reliability
```

Versione ancora 0.2.1, artefatto non rilasciato; i pacchetti precedenti restano
intatti. Installazione reale e collaudo seguono la
[procedura dedicata](COLLAUDO_MELCLOUD_HOME.md), solo dopo autorizzazione.
