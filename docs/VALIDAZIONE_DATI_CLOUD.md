# Verifica offline dei dati MELCloud Home

Implementata nel consolidamento locale, non ancora applicata a dati reali.
Controlla file già ottenuti legittimamente: non esegue login, richieste HTTP,
comandi HA o operazioni sull'impianto. Non modifica il file né salva una copia.
Non è una specifica ufficiale Mitsubishi: verifica il contratto attualmente
implementato nel parser e nel modello del progetto.

## Percorso consigliato: report standard HA

Dalla root, con il file tenuto in una cartella privata:

```powershell
.venv/Scripts/python.exe -m tools.validate_cloud_data private-captures/report.json
```

Accetta il report diretto o nell'involucro HA `data`, formato support schema 1.
Preferisce `normalized_telemetry` se presente; accetta i report precedenti usando
`current_observation`. Nei report vecchi un campo omesso dall'esportazione viene
marcato `not_in_report`: non dimostra che il cloud non lo esponga.
Il tool precedente `read_support_report.py` rimane disponibile per leggere i
dettagli; il nuovo validatore produce soltanto stati e codici di verifica.

## Risposte API già acquisite, se disponibili

Non occorre acquisirle per il primo collaudo. Il codice non fornisce alcun
comando di cattura o accesso all'account. Se un campione è già disponibile,
senza credenziali/header, utilizzare il tipo corretto e l'ora reale di acquisizione:

```powershell
.venv/Scripts/python.exe -m tools.validate_cloud_data private-captures/unit.json --kind unit --acquired-at 2026-10-30T12:00:00+01:00
.venv/Scripts/python.exe -m tools.validate_cloud_data private-captures/context.json --kind context --acquired-at 2026-10-30T12:00:00+01:00
.venv/Scripts/python.exe -m tools.validate_cloud_data private-captures/history.json --kind history
```

La data è un esempio, da sostituire con quella nota. Nessun fuso viene indovinato.
`unit` verifica Snapshot.parse e la normalizzazione; `context` controlla edifici,
unità e duplicati; `history` verifica Fault.parse, date con fuso e ordine
inizio/cessazione. Una risposta storico vuota valida non prova completezza FTC.
Strutture inattese non vengono interpretate come dati validi.

## Risultati e limiti

| Risultato | Significato |
|---|---|
| `schema_valid=true` | Il contenitore è utilizzabile dal percorso verificato |
| `exposed` | Campo disponibile nella sorgente/file esaminato, non certificato fisicamente |
| `missing` | Campo assente/null nello snapshot o così dichiarato nel report |
| `invalid` | Campo presente ma non utilizzabile, oppure fatto normalizzato invalido |
| `stale` | Il report ha già marcato la misura come vecchia |
| `unknown`, `unsupported`, `acquisition_error` | Stati espliciti conservati dal report |
| `not_in_report` | Il file esportato non permette di determinare quel campo |
| `not_mapped_by_integration` | Nessun mapping implementato, non indisponibilità assoluta del servizio |

`schema_valid=true` può coesistere con parametri invalidi o mancanti: vanno
esaminati separatamente. Codice uscita 0 per schema accettato, 2 per errore.
I report normalizzati verificano enum, date, disponibilità, unità e valori numerici;
i nomi futuri non riconosciuti vengono ignorati, senza stamparli. I file oltre
5 MiB vengono rifiutati, senza troncare o alterare il contenuto.

Il risultato non riporta valori, date originali, UUID, nome unità, nomi dei campi
arbitrari o testo delle eccezioni. Le unità ricevono alias locali. La validazione
non certifica misura fisica, corretta configurazione, generazione reale o completezza
dello storico: i relativi indicatori restano false.

Selezione/presenza sensore ambiente, indirizzo guasto FTC, configurazione di
commissioning e storico completo sono indicati come non mappati. Non vengono
dedotti da temperature, modello commerciale o assenza di P1.

`private-captures/` è esclusa da Git per ridurre inserimenti accidentali. Il
file originale resta privato anche se escluso: non allegare payload integrali,
backup o credenziali. Conservare un originale protetto e condividere inizialmente
solo l'esito del validatore; verificare anche il report HA prima di condividerlo.
