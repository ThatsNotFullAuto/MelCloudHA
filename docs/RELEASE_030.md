# MELCloud Diagnostics v0.3.0

Release ordinaria del software disponibile. **Nessun collaudo con account o impianto
Mitsubishi reale è stato eseguito.** La release stabile precedente è v0.2.1.

## Miglioramenti disponibili

Il registro gestisce meglio salvataggi falliti, interruzioni, recupero e duplicati;
i report distinguono provenienza, timestamp, dati mancanti e stato della persistenza.
I nuovi controlli impediscono che unknown o differenze di formato dei numeri
appaiano come cambi di configurazione. È disponibile un validatore offline.

Il modello rappresenta FTC4–FTC7 e conserva evidenze/limiti. Questo non certifica
il cloud su ogni generazione. Asgard/CN105, importazione SD e lettura verificata
della selezione TH1A/TH1B non sono operative. Proxy MAC-597IF-E ancora sconosciuto.
Nessun hardware aggiuntivo richiesto, nessun codice GPL incorporato.

## Aggiornamento con HACS

1. Eseguire un backup HA protetto, includendo config entry e registro diagnostico.
2. In HACS aprire **MELCloud Diagnostics**. Se necessario aggiornare le informazioni
   della repository; l'indicizzazione può richiedere tempo.
3. Scegliere **Aggiorna** alla **v0.3.0**. In alternativa aprire il menu
   **⋮ → Scarica di nuovo / Redownload** e scegliere **v0.3.0**. Secondo la
   versione HACS la scelta può apparire sotto **Need a different version**.
   Non scegliere il branch main.
4. Scaricare e **riavviare Home Assistant**. Non rimuovere/recreare l'integrazione.
5. Verificare versione nel report, ritorno delle letture e modifiche disabilitate.

Per una nuova installazione aggiungere prima la repository personalizzata
`https://github.com/ThatsNotFullAuto/MelCloudHA`, categoria Integrazione.
Non sostituire `melcloud_home` ufficiale. La modalità predefinita resta sola lettura;
i permessi già salvati non vengono riscritti: per il collaudo verificarli.
La selezione delle versioni segue la [documentazione HACS](https://www.hacs.xyz/docs/use/repositories/dashboard/).
Queste istruzioni non costituiscono un collaudo del frontend HACS reale.

Asset installabile: `melcloud_diagnostics.zip`, con manifest e moduli alla root
dello ZIP, adatti a `custom_components/melcloud_diagnostics/`. Il pacchetto sorgente
e `SHA256SUMS` sono asset separati. Non servono copie di file privati o script
di cattura. Tag: `v0.3.0`; manifest/costante/metadati Python: `0.3.0`.

## Compatibilità e collaudo

Dominio, account, config entry, ID entità/dispositivi, dashboard e involucro
storage 1 sono preservati. I campi aggiuntivi sono opzionali; non serve una
migrazione distruttiva. I test simulati coprono upgrade e riavvii.
I limiti di durabilità rimangono: dati solo in RAM possono andare persi a un kill;
il bus HA non offre consegna esattamente una volta. Gli eventi salvati rimangono
nel journal, senza replay automatico delle notifiche.

Seguire la [procedura di collaudo](COLLAUDO_MELCLOUD_HOME.md) solo dopo
autorizzazione: HA di prova minimale, almeno 20 minuti, confronto con app/display,
reload e report. Non cambiare impostazioni e non provocare guasti sulla pompa.
Lo sviluppo e la pubblicazione della release non accedono all'impianto.

## Report e segnalazioni

Aprire **Configura → Assistenza**, poi **Scarica diagnostica** dal menu account
dell'integrazione. Conservare l'originale privatamente; controllarlo prima di
condividerlo. Il [validatore offline](VALIDAZIONE_DATI_CLOUD.md) non stampa valori
o identificativi e non accede a Mitsubishi.

Segnalare anomalie nelle [issue](https://github.com/ThatsNotFullAuto/MelCloudHA/issues)
con versione integrazione/HA, data/fuso, comportamento atteso e osservato. Non inviare
credenziali, token, backup HA o payload API integrali.

## Tornare alla 0.2.1

Fare una copia protetta del registro corrente. In HACS usare Scarica di nuovo,
scegliere **v0.2.1**, scaricare e riavviare HA. Non eliminare config entry o storico.
I nuovi campi opzionali del registro storage 1 sono leggibili nei test sintetici
con Store HA 1. Il downgrade completo su HA reale non è stato collaudato:
conservare il backup e verificarne il ripristino su HA di prova.
Se necessario ripristinare un backup coerente a HA fermo: i dati torneranno al
momento del backup. Nessun ripristino o reset dei parametri Mitsubishi.

La fase successiva è la verifica reale autorizzata di autenticazione, letture,
storico, reload/persistenza e analisi dei report. Non richiede acquisti hardware.
