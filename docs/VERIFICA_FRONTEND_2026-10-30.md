> Rapporto storico del checkpoint precedente al rilascio. Per versione, requisiti e procedure correnti vedere [Release 0.4.0](RELEASE_040.md) e [compatibilita](REQUISITI_E_COMPATIBILITA.md).

# Verifica frontend e screenshot — 30 ottobre 2026

## Stato e perimetro

Branch iniziale/finale `main`, HEAD `cbe8508e529aad5016f71406aa44adacc60dfe9c`.
Working tree già modificato per il Collaudo: preservati codice, documentazione
e `codex.txt` ignorato. Baseline rieseguita: 211 test superati. Nessun commit,
push, merge, tag, release o operazione su account/impianto Mitsubishi.
La v0.3.0 pubblicata resta invariata; manifest e progetto locali restano 0.3.0.
Changelog e note 0.4.0 sono preparazione non pubblicata.

## Frontend realmente eseguito

HA Core **2026.10.4**, frontend **20260930.5**, Python **3.14.3**, libreria
`aiomelcloudhome` **0.3.1**, Playwright **1.64.1**, Chromium **156.0.8078.4**.
HA eseguito sotto Linux/WSL, ascolto soltanto loopback `127.0.0.1:18123`.
Il canale browser standard era indisponibile; Playwright locale è stato usato
dopo autorizzazione esplicita. Nessun mock del frontend o modifica al codice HA.
Dipendenze Linux e browser sono locali a `.tools/`; nessuna nuova dipendenza
runtime dell'integrazione e nessuna installazione sul sistema domotico.

`tools.run_frontend_demo` sostituisce il trasporto con risposte sintetiche e
rifiuta tutte le scritture. Nessun token Mitsubishi viene richiesto. Il modello
FTC7 della fixture non è una identificazione o prova di compatibilità reale.
L'orologio della sola sessione demo viene accelerato: la UI legge sensori e
manager reali, senza alterazione DOM, animazioni simulate o stati imposti.

| Percorso verificato nel vero frontend | Risultato |
|---|---|
| Configura → Diagnostica → Collaudo diagnostico | Pompa e durata 20/60 minuti selezionabili, default 60 |
| Avvio con controlli disabilitati | Sessione indipendente dal flow |
| Barra nativa `bar-gauge` | Valore del sensore, da avvio fino a scadenza 100% |
| Tempi e acquisizioni | Durata, trascorso/residuo, scadenza e contatori visibili |
| Chiusura del browser e riapertura | La sessione prosegue nel backend |
| Stop dalla tile, anche mobile | Si ferma solo la raccolta; zero GET sintetici aggiuntivi al click |
| Scadenza naturale | Stato completato separato dai controlli non verificabili |
| Errore storage del Collaudo | Stato parziale, errore persistenza e FAIL coerente con JSON |
| Scarica la diagnostica dal menu HA | Download autentico completato/interrotto/parziale, schema validato |
| Variazione permessi durante sessione | Arresto/invalidation prima del reload e motivo conservato |
| Nuovo avvio con controlli abilitati | Rifiutato; opzioni non modificate automaticamente |
| Reload/riavvio della demo durante raccolta | Checkpoint preservato, interrotto, nessuna ripresa automatica |
| Plancia ordinaria dopo errore collaudo | Sensori ordinari disponibili, polling indipendente |

Desktop **1440×1000** e viewport smartphone **390×844**, temi chiaro e scuro.
Nessun overflow orizzontale nella vista mobile verificata. Emulazione viewport,
non telefono fisico: Safari, altri browser e accessibilità completa non verificati.
Warning HA per acceleratori multimediali facoltativi ffmpeg/turbojpeg non
impediscono flow, dashboard o download; non è un collaudo delle funzioni media.

## Problemi corretti e file

- `test_entities.py`: durate in minuti con unità suggerita; report sempre in
  secondi. Stati enum tradotti senza cambiare codici o unique ID. Nessuna
  migrazione forzata delle preferenze del registro entità utente.
- `dashboard.py`: vista Diagnostica in due sezioni responsive, larghezza completa
  per barra/stato/stop/risultati lunghi. Pulsante stop senza stato data sconosciuta.
  Risoluzione degli ID dal registro, plance esistenti non sovrascritte.
- `__init__.py`, `test_manager.py`, `core/test_session.py`: invalidazione dei
  controlli con motivo `control_permissions_changed`, finalizzazione locale
  limitata prima che HA cancelli i task della entry durante reload. Il FAIL
  rimane anche se reload o storage falliscono. Un errore del manager non impedisce
  il reload ordinario. Nessuna chiamata al writer o modifica delle opzioni.
- `core/test_session.py`, `test_manager.py`: unica valutazione dei controlli per
  checkpoint, sensori ed export; eliminata divergenza visiva dopo errore storage.
  Le perdite di osservazioni non producono PASS dell'acquisizione.
- `strings.json`, `translations/it.json`: testi chiari, download HA e distinzione
  fra report Assistenza e report ristretto del Collaudo.
- `tools/run_frontend_demo.py`, `capture_frontend_demo.py` e requisiti opzionali:
  harness isolato e sequenza reale ripetibile. `generate_test_demo.py` aggiornato
  alle durate in minuti; `build_documentation_previews.py` non sovrascrive più
  gli screenshot autentici con illustrazioni HTML.
  Risolti anche il caricamento anticipato della cattura del wizard e un errore
  di sovrascrittura PNG WSL/Windows: la cattura prepara ora un file separato e
  lo sostituisce atomicamente. Un fallimento non tronca l'immagine precedente.
- `tests/test_frontend_regressions.py`: nove regressioni su permessi/reload,
  persistenza, contatori e unità. Aggiornati i test della struttura responsive.
- README, guide utente/tecnica/debug/collaudo, changelog, bozza release e
  documentazione screenshot aggiornati; nessun claim di validazione fisica.

## Garanzie di isolamento e non interferenza

La simulazione controllata di 60 minuti confronta gli stessi coordinator con
e senza raccolta: **64 GET in entrambi i casi**, 60 context e 4 errorlog;
intervallo 60 secondi e journal risultante identici. Le letture di setup sono
esterne a questo conteggio. Questa prova usa il trasporto ordinario con risposte
sintetiche, non misura traffico di un account reale. Nel frontend lo stop
aggiunge **zero letture sintetiche**; barra e cambio pagina non chiedono refresh.

Percorso: lettura ordinaria → inventario di metadati limitato → parsing e commit
ordinario → osservazione limitata → `put_nowait` → worker/executor → store separato.
Il coordinator non attende reducer, export o disco del Collaudo. Nessun lock del
journal è acquisito dal manager; il lock lifecycle è soltanto locale al Collaudo.
La suite verifica callback asyncio e sensori ordinari anche con elaborazione
lenta, fault storage, eccezioni, timeout, 401/403/404/429 e dati incompleti.

Limiti: coda **4**, **75** campioni, **128** eventi/guasti per categoria,
**128** percorsi schema, report **1 MiB**; timer UI locale **30 s**, nessun
checkpoint al tick. Storage separato con checkpoint atomici verificati e attesa
massima 2 s; stop/unload attende il worker fino a 3 s. Saturazione, limiti o
errori persistenti fermano solo il Collaudo. 24 ore disabilitate. Nessun retry
aggiuntivo verso Mitsubishi. Il Recorder può registrare i nuovi stati, senza
eventi custom al secondo o nuove statistiche di lungo periodo.

Manager senza client cloud/writer/ConfirmationGate; nessun percorso di comando.
Autenticazione ordinaria non alterata. L'account conserva i propri privilegi:
read-only è una separazione software, non necessariamente una ACL del server.
Lo store principale non cambia formato. Un guasto disco non è risolvibile dal
software: il risultato RAM può essere scaricato fino allo spegnimento e non si
promette conservazione dei dati non confermati dopo crash.

## Screenshot e privacy

**11 PNG autentici** in `docs/images/`: quattro richiesti, stop manuale, tre
varianti desktop/mobile/tema e tre immagini preesistenti aggiornate
(plancia, wizard, assistenza). Nomi e rigenerazione nella
[procedura screenshot](SCREENSHOT_COLLAUDO.md). Tutti revisionati visivamente,
con nomi generici e dati sintetici; nessuna immagine AI o montaggio grafico.
README, guida utente/collaudo e note di rilascio collegano solo file esistenti.

Report scaricati con il meccanismo autenticato HA, validati e senza UUID della
fixture; valori sconosciuti non esportati. Output, token e database della demo
restano in `.tools/` ignorata, fuori dai pacchetti. La chiusura ordinata del
nuovo harness revoca il token temporaneo corrente e rimuove il file browser-auth.
Le fixture non vanno condivise come acquisizioni Mitsubishi autentiche.

## Verifiche locali finali

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check custom_components tests tools
.venv/Scripts/python.exe tools/build_release.py --output-dir dist/validation-frontend-v040
git diff --check
```

**220 test superati**; un DeprecationWarning HA/aiohttp preesistente.
Ruff, build HACS e diff verificati. ZIP source/HACS con integrità CRC, inventario
e SHA-256 controllati. Il pacchetto HACS contiene il componente alla radice e
non include screenshot/tool di sviluppo o dati privati. Gli artefatti locali
riportano ancora versione **0.3.0**: non sono una nuova release della 0.3.0 e non
vanno caricati sulla release pubblicata. Nessuna CI remota avviata in questa fase.

## Checklist per la prima prova reale autorizzata

1. Allineare versione futura 0.4.0, completare CI e autorizzare separatamente
   pubblicazione/installazione; conservare backup verificato e pacchetto 0.3.0.
2. Usare prima HA di prova isolata, senza automazioni domestiche duplicate e
   senza due copie Diagnostics sul medesimo account. Controlli manuali spenti.
3. Verificare aggiornamenti ordinari, app Mitsubishi ed eventuale integrazione
   ufficiale. Annotare privatamente CPU/RAM/disco/Recorder e frequenze baseline.
4. Avviare **20 minuti** dal percorso Configura → Diagnostica → Collaudo.
   Non provocare errori, cambiare stagione, modalità, sensori o setpoint.
5. Verificare continuità sensori/app/automazioni e assenza 429; se compare carico
   anomalo fermare solo il Collaudo. Nessun riavvio ripetuto per aggirare backoff.
6. Verificare stop, report parziale e reload della sola integrazione di prova.
   Scaricare **⋮ dell'account → Scarica la diagnostica**, controllare privacy
   e conservare il JSON originale. Solo dopo esito soddisfacente provare 60 minuti.
7. Se occorre ripristinare: esportare, fermare raccolta, ripristinare pacchetto
   precedente e backup coerente se necessario, riavviare soltanto HA di prova.
   Nessuna cancellazione del journal; downgrade reale non ancora verificato.

Il software locale e il frontend hanno superato i gate qui eseguibili per
preparare una **release ordinaria destinata al primo collaudo**. Non è ancora
pubblicabile senza versione 0.4.0 allineata, CI e autorizzazione separata;
non è dichiarato pronto per il sistema domestico dei genitori. Mancano verifica
account, correttezza fisica, benchmark sul target e coesistenza reale. Non serve
trasformare automaticamente questa limitazione in una beta.

Il JSON consentirà di valutare campi presenti/assenti/nulli, tipi inattesi,
decoder mancanti, disponibilità storico/P1 e coerenza temporale. Prima di
Asgard occorrono lacune cloud dimostrate e prova specifica di compatibilità
MAC-597IF-E/proxy; selezione sensore, TH1A/TH1B e configurazione FTC potrebbero
richiedere report ufficiali o sorgenti locali, senza garanzia preventiva.
