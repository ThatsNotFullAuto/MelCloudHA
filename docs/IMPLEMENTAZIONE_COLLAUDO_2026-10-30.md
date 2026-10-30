> Rapporto storico del checkpoint precedente al rilascio. Per versione, requisiti e procedure correnti vedere [Release 0.4.0](RELEASE_040.md) e [compatibilita](REQUISITI_E_COMPATIBILITA.md).

# Verifica locale della modalità Collaudo — 30 ottobre 2026

## Stato iniziale e finale

Branch `main`, HEAD `cbe8508e529aad5016f71406aa44adacc60dfe9c`, release di
riferimento 0.3.0. Working tree inizialmente pulito; `codex.txt` ignorato e
preservato. Baseline rieseguita: 170 test e Ruff superati. Nessun commit, push,
tag, release, installazione HA o accesso Mitsubishi in questa sessione.
Il lavoro rimane nel working tree; versione/manifest/pyproject restano 0.3.0.
La funzione è **non pubblicata**, destinata a una decisione futura sulla 0.4.0.

## Moduli e comportamento implementato

- `test_manager.py`: manager per config entry, worker indipendente dal flow,
  coda limitata, circuit breaker, timer locale, stop, recupero e storage separato.
- `core/test_session.py`: reducer puro, contratto JSON schema 1, controlli
  deterministici, evidenze P1 e validazione ricorsiva dell'output.
- `core/test_privacy.py`: copie ristrette, codici/modalità consentiti,
  inventario pre-parser senza valori sconosciuti e alias HMAC di sessione.
- `test_entities.py`, `button.py`: 18 sensori diagnostici locali e un pulsante
  che interrompe esclusivamente la raccolta. Nessun riferimento a writer/gate.
- `config_flow.py`: menu Diagnostica, durata 20/60 minuti, consenso ai numeri,
  sostituzione esplicita del precedente risultato, stato/stop/confronto/download.
- `coordinator.py` e `core/cloud.py`: osservazioni dei GET già ordinari,
  handoff non bloccante e contenimento delle eccezioni dell'osservatore.
- `storage.py`: riuso delle scritture atomiche verificate con validator e
  serializzazione in executor opzionali; default del journal invariati.
- `diagnostics.py`: con sessione conservata scarica il solo report ristretto;
  senza sessione mantiene il download precedente. Il journal non viene eliminato.
- `dashboard.py`, `sensor.py`, `const.py`, traduzioni: nuova vista generabile,
  barra nativa e identificativi risolti dal registro, vecchie entità preservate.
- `core/schema.py` e strumenti offline: riconoscimento del nuovo report,
  fixture ripetibili per documentazione visiva senza connessioni HA/cloud.

## Garanzie di isolamento e non interferenza verificate sinteticamente

Con una unità e 60 poll a un minuto simulato: **64 GET identici** con/senza
collaudo, di cui 60 context e 4 errorlog. Intervallo coordinator sempre 60 s;
journal finale identico. L'orologio viene iniettato nei test, senza attendere
un'ora reale: non è un benchmark completo dello scheduler o dell'hardware HA.

Nessun nuovo client cloud, endpoint, refresh o retry nella sessione. La prima
lettura di setup rimane ordinaria. Il callback raw è sincrono e limitato a
metadati/copie di cardinalità fissa; non esegue I/O né riduzione del report.
Il coordinator non attende worker/storage/export; non sono condivisi lock col
journal. Elaborazione e copie onerose usano l'executor HA, senza thread dedicati
non controllati. Download simultanei condividono una elaborazione.

Limiti: coda 4, campioni 75, eventi/guasti/percorsi 128, alias ignoti 128,
report 1 MiB, file con involucro fino a 1 MiB + 4096 byte. Nessuna raccolta 24 h.
Sono limiti logici dei dati, **non una misura del consumo RSS del processo**.
Una sessione/report per entry, sostituzione solo esplicita. Nessun Recorder usato
come archivio; nuovi sensori senza statistiche lunghe o payload negli attributi.

Timer 30 s: tre cambi di stato mentre il tempo avanza, zero a orologio fermo,
zero scritture storage e zero cloud. Gli altri stati cambiano su dati/transizioni.
Il Recorder può registrarli: eventuale esclusione resta una scelta dell'utente.

Test di operazioni lente dimostrano avanzamento di polling, normali sensori e
callback bus indipendenti, con limite di attesa sintetico 0,5 s. Non è un SLA.
429/reauth, tre errori consecutivi, coda/capacità, storage pieno o timeout e
eccezioni inattese fermano solo il collaudo. Main journal e polling continuano.

Checkpoint separato per poll/transizioni, scrittura atomica e rilettura;
attesa storage 2 s e chiusura worker fino a 3 s. Nessun salvataggio per barra.
Un riavvio interrompe il checkpoint attivo senza ripresa o richieste nuove.
File corrotto preservato, solo manager indisponibile. In caso di disco guasto il
report RAM è esportabile finché il processo resta attivo; dopo crash vale solo
l'ultimo checkpoint. I/O OS già in executor non è fisicamente annullabile.

## Verifiche eseguite

Ambiente: Python 3.14.3, Home Assistant 2026.10.4, aiomelcloudhome 0.3.1.

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check custom_components tests tools
git diff --check
.venv/Scripts/python.exe tools/build_release.py --output-dir dist/validation-guided-test
```

Suite: **211 test superati**, 41 aggiunti, un DeprecationWarning già emesso da
Home Assistant/aiohttp. Ruff e diff senza errori. Build locale HACS/source e
checksum verificati; artefatti in `dist/`, esclusi dal repository. Non sono una
nuova distribuzione della 0.3.0 né vanno caricati sulla release pubblicata.

Nuove suite: `test_diagnostic_test_session`, `test_diagnostic_test_isolation`,
`test_diagnostic_test_faults`, `test_diagnostic_test_demo`. Coprono lifecycle,
progressione, chiusura wizard, stop, dati mancanti/duplicati, history 403/404,
401/429, timeout, code piene, errori storage, corruzione, replay, consistenza P1,
privacy di campi annidati/dinamici, report, timer, sensori e fixture.

## Limiti e passaggio successivo

Non eseguiti: account/pompa reali, HA domestica, benchmark CPU/RAM/disco/Recorder
su hardware target, verifica grafica browser/mobile, screenshot definitivi,
matrice CI remota o un diverso ambiente HA latest. Nessuna nuova dipendenza.
Le verifiche software non dimostrano accuratezza fisica o compatibilità FTC
hardware; queste rimangono UNKNOWN. Nessuna modifica al controllo opzionale.

Prima di dichiarare pronta la funzione per i genitori serve prova autorizzata
su HA isolata: 20 minuti, controllo carico/app/integrazione ufficiale, stop/reload,
verifica report e privacy; solo dopo valutare 60 minuti. P1 non va provocato.
Sensore selezionato, TH1A/TH1B, firmware e configurazione FTC completa possono
restare sconosciuti. Prima di proporre Asgard occorrono lacune cloud dimostrate
e conferma specifica di coesistenza/proxy MAC-597IF-E; nessuna acquisto suggerito
come sicuramente compatibile. Report ufficiali/locali si valutano separatamente.

Procedura completa e checklist: [Collaudo guidato](COLLAUDO_GUIDATO.md).
Fixture e immagini: [Screenshot v0.4.0](SCREENSHOT_COLLAUDO.md).

## Verifica successiva del frontend

I risultati 211 test e i limiti sopra descrivono il checkpoint iniziale.
La successiva verifica ha avviato il vero frontend HA con backend sintetico,
corretto UI e invalidazione dei permessi, aggiunto nove regressioni (220 test)
e acquisito screenshot autentici, inclusi plancia/wizard/assistenza.
Dettagli e limiti aggiornati: [Verifica frontend](VERIFICA_FRONTEND_2026-10-30.md).
