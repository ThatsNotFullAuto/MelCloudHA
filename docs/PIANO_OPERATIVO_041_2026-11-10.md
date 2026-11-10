# Piano operativo — affidabilità dei report e raccolta delle evidenze cloud

Data: 10 novembre 2026. Documento di pianificazione, non annuncio di release.

Esecuzione dell'incremento A: [note e aggiornamento 0.4.1](RELEASE_041.md).
L'incremento B descritto qui resta una possibilità futura, non implementata.

Aggiornamento dell'esecuzione: il valore dichiarato fornito dall'utente è `ftC7`.
La 0.4.1 normalizza soltanto maiuscole e spazi esterni delle etichette esplicite
FTC4–FTC7, senza deduzioni da modelli o firmware. Il sensore resta invariato e
le capacità non diventano verificate. I report precedenti non sono riclassificati.

## 1. Obiettivo e stato di partenza

Produrre un primo incremento locale che corregga le ambiguità del report 0.4.0,
preservando funzionamento ordinario, privacy e compatibilità. Stabilire poi se
serva una raccolta aggiuntiva di metadati sicuri, usando sempre il polling esistente.

Baseline locale verificata: branch `main`, HEAD
`a2433f87d3408a8312a3994c88fe775cc703351e`, versione 0.4.0.
Ultima campagna di sviluppo: 225 test superati; non rieseguiti per questa sola
pianificazione. Prima dell'implementazione verrà verificata nuovamente la baseline.
La modifica locale preesistente a `.gitignore` protegge i report diagnostici:
va preservata, come `codex.txt` e tutte le acquisizioni private.

L'analisi offline di un report utente ha rilevato:

- letture e storico acquisiti correttamente durante la sessione osservata;
- `ErrorCode` presente nell'inventario ma classificato tra i dati assenti;
- `ftcModel` presente come stringa, con generazione normalizzata `unknown`;
- campi tecnici non interpretati, conservati come alias di sessione;
- differenza da chiarire fra codice corrente leggibile e guasti storici leggibili.

Il report autentico rimane privato. Non verrà inserito nei test pubblici, copiato
nel piano o trasferito a servizi esterni. Le fixture saranno scritte da zero con
dati sintetici che riproducano soltanto le condizioni strutturali necessarie.

## 2. Supervisione e delega effettivamente attivata

Il responsabile è l'agente principale: coordina il backlog, decide il contratto,
assegna i file, integra il lavoro e verifica sicurezza, compatibilità e gate.
I subagenti non pubblicano, non operano sull'impianto e non autorizzano eccezioni.

| Responsabile / incarico | Modello e ragionamento usati | Motivazione e risultato |
|---|---|---|
| PM e supervisore: agente principale | Modello della sessione | Decisioni architetturali, conflitti, integrazione e approvazione tecnica finale |
| `report_semantics_plan`: semantica e compatibilità | `gpt-6.1-sol`, medium | Analisi mirata di reducer, inventario e validatore; work package e casi limite |
| `privacy_collection_plan`: privacy e nuove evidenze | `gpt-6.1-sol`, high | Revisione di esportazione, stringhe arbitrarie, alias e confini delle capacità |
| `qa_rollout_plan`: QA e procedura operativa | `gpt-6-luna`, medium | Riuso dei test esistenti, checklist, gate e ripristino senza ripetere l'audit tecnico |

Le tre analisi sono state delegate e completate in sola lettura. Ai subagenti
sono stati dati contesti brevi, senza la cronologia completa o il JSON privato;
sono stati richiesti risultati limitati e specifici. Nessuna sotto-delega.

Per l'esecuzione futura si riusano questi ruoli: implementatore core, revisore
privacy e QA. Il supervisore resta proprietario delle decisioni trasversali.

## 3. Decisione architetturale del supervisore

**Incremento A, candidato 0.4.1:** correggere interpretazioni e presentazione
utilizzando il contratto attuale, senza nuove chiavi, nuovi valori liberi o
modifiche al significato dei contatori. Non cambiare il numero di schema.

Il validatore 0.4.0 usa struttura e vocabolario chiusi. Un'estensione additiva
non è automaticamente compatibile: un nuovo reader può leggere il vecchio
formato, mentre il vecchio reader può rifiutare i nuovi campi.

**Incremento B, eventuale versione successiva:** se servono categorie esportate
aggiuntive o un nuovo profilo, definire prima uno schema 2 con reader 1/2.
La destinazione di versione, plausibilmente una minor release, verrà decisa sul
diff effettivo. Non inserirlo di nascosto nel bugfix 0.4.1.

Non è possibile ricostruire dal vecchio report il testo originale di `ftcModel`,
i nomi degli alias o la differenza fra stringa vuota e sentinel non esportato.
Questi dati rimangono sconosciuti. Gli alias non vanno associati fra sessioni.

## 4. Backlog e sequenza di esecuzione

I percorsi `core/...`, `sensor.py` e gli altri moduli dell'integrazione sono
relativi a `custom_components/melcloud_diagnostics/`. `tests/`, `tools/` e
`docs/` sono relativi alla root del repository.

### WP0 — Congelare perimetro e criteri

Responsabile: PM. Dipendenze: nessuna. Complessità: bassa.

Attività:

1. Verificare HEAD, branch, working tree, versioni installate e baseline test.
2. Inventariare le modifiche preesistenti e controllare l'esclusione dei dati privati.
3. Approvare una tabella di significati: presenza nello schema, disponibilità
   del valore decodificato, valore autorizzato all'esportazione, identificazione
   FTC e leggibilità dei codici correnti/storici.
4. Assegnare un solo proprietario a ogni file. Nessuna modifica al writer.

Consegna: contratto di comportamento e lista dei file toccabili.
Gate: nessuna ambiguità su quali modifiche siano compatibili con schema 1.

### WP1 — Correggere la falsa assenza dei campi

Responsabile: implementatore core, `gpt-6.1-sol` medium.
Dipendenza: WP0. Complessità: media.

File principali: `core/test_session.py`, `core/schema.py`,
`tools/read_support_report.py`; test mirati dedicati.

Attività:

- Calcolare l'assenza strutturale dall'inventario pertinente all'operazione,
  evitando di dedurla dalla sola mancanza di un valore decodificato.
- Gestire frame non disponibili, inventario troncato e report precedenti senza
  prove sufficienti: non trasformare l'incertezza in assenza confermata.
- Conservare i contatori `present/missing/invalid/changes` con il loro contratto
  attuale; spiegare quando descrivono il valore normalizzato.
- Non chiamare "mancante nel cloud" un valore soltanto redatto per privacy.
- Non inventare distinzioni vuoto/sentinel/formato ignoto dai dati aggregati.

Consegna: diff piccolo e fixture sintetiche che riproducano l'incoerenza.
Accettazione: un campo inventariato come presente non compare fra gli assenti;
una misura disponibile e redatta rimane disponibile; l'assenza non viene
certificata se manca una copertura strutturale sufficiente.

### WP2 — Chiarire P1 e identificazione FTC senza cambiare contratto

Responsabile: implementatore core; revisione PM/privacy.
Dipendenza: WP1. Complessità: media.

File: `core/test_session.py`, lettore offline, documentazione diagnostica;
eventuali etichette UI soltanto se necessarie.

Attività:

- Documentare che l'attuale `code_readable` riguarda codici correnti interpretabili
  esportati. Non modificarne silenziosamente il significato per includere lo storico.
- Presentare separatamente, usando le evidenze già presenti, i record P1 storici,
  l'eventuale P1 attivo e i dati non determinabili.
- Conservare la condizione: P1 attivo richiede flag di errore vero e codice P1
  nello stesso campione. Uno storico P1 non diventa un guasto attivo.
- Chiarire che FTC `unknown` non equivale a campo `ftcModel` assente.
  Mantenere conservativo `FTCGeneration.from_declared()`.
- Distinguere record, duplicati riosservati, episodi fisici e finestra di 30 giorni.
  Non raggruppare automaticamente più record in un solo guasto e non attribuire cause.
- Aggiornare lo stato delle verifiche nella documentazione: esiste un report
  utente acquisito e analizzato offline. Questo non equivale a una validazione
  indipendente dell'impianto o della compatibilità di ogni generazione FTC.

Consegna: report leggibile, documentazione e casi sintetici coerenti.
Accettazione: storico disponibile e codice corrente vuoto non si contraddicono;
assenza di un timestamp di risoluzione non implica guasto ancora attivo;
nessuna identificazione TH1A/TH1B o FTC ricavata per supposizione.

### WP3 — Revisione e verifica dell'incremento A

Responsabile: PM; QA per test ordinari, revisore `gpt-6.1-sol` high per privacy.
Dipendenze: WP1–WP2. Complessità: media.

La QA può preparare test indipendenti dopo WP0, mentre il core implementa.
Usare file di test distinti per evitare conflitti; il PM integra i contratti comuni.

Gate obbligatori:

| Ambito | Criterio verificabile |
|---|---|
| Semantica | Casi omesso, null, vuoto, spazi, placeholder, valore valido, tipo errato e redazione distinti dove esiste evidenza; nessuna ricostruzione di dati perduti |
| P1 | Solo storico; codice corrente con flag vero/falso/ignoto; letture duplicate; codici diversi alla stessa data; nessuna falsa segnalazione attiva |
| FTC | Valore esplicito riconosciuto, stringa sconosciuta, null, valore lungo; `unknown` mantenuto quando necessario |
| Privacy | Segreti sintetici in chiavi, valori, array e oggetti; nessun valore ignoto esportato o registrato nei log |
| Compatibilità | Nuovo reader legge schema 1 storico; validator della 0.4.0 accetta l'output dell'incremento A; journal, config entry e ID invariati |
| Isolamento | Scenario simulato di un'ora: 64 GET identici con/senza Collaudo, stesso journal; nessun refresh, retry o comando operativo aggiunto |
| Persistenza | Report parziale, file assente/corrotto, stop/reload: problema confinato al Collaudo |
| Distribuzione | Ruff, suite completa, diff, ZIP HACS, manifest, integrità e checksum Windows/Linux quando si prepara un pacchetto |

Non fissare un numero-obiettivo di test. Aggiungerli per comportamenti e rischi;
non per replicare l'implementazione. Dopo il superamento, ripetere la suite
solo per nuove modifiche o problemi concreti.

Consegna: diff revisionato, risultati e pacchetto locale di validazione.
Esito: candidato 0.4.1 pronto per una successiva decisione di pubblicazione.

### WP4 — Ottenere evidenza FTC con gli strumenti già disponibili

Responsabili: PM e proprietario dell'installazione; revisore privacy.
Dipendenza: nessuna modifica software necessaria per il primo controllo.
Complessità: bassa per la verifica, da valutare per eventuali decoder.

1. Consultare il sensore HA **Modello FTC dichiarato**, già esposto da `sensor.py`.
2. Confrontare privatamente con identificazione tecnica già disponibile,
   senza entrare in commissioning o cambiare configurazioni.
3. Comunicare solo la categoria tecnica necessaria, evitando seriali o etichette
   personali. Non richiedere un'esportazione generale del vecchio journal.
4. Analizzare i contratti locali di `aiomelcloudhome` e preparare una matrice
   "campo esatto → tipo → semantica verificata → prova mancante".
5. Proporre mapping FTC soltanto se esiste una corrispondenza dimostrata.

Gate: presenza del campo e identificazione del controller rimangono due fatti
distinti; un nome modello o un numero firmware non bastano a identificare FTC7.

### WP5 — Decidere se serve l'incremento B

Responsabile: PM con revisore privacy `gpt-6.1-sol` high.
Dipendenze: WP3 e risultati utili di WP4. Complessità: alta.

GO soltanto se manca un'informazione precisa e utile che il contratto attuale
non può rappresentare. Esempi: contatori espliciti per vuoto/null/sentinel o
stato di identificazione FTC osservata ma non riconosciuta.

Prima del codice:

- definire schema 2 con vocabolario finito, reader 1/2 e versionamento esplicito;
- mantenere invariati chiave/schema del journal principale;
- progettare uno store separato per il nuovo formato, preservando l'ultimo
  risultato schema 1. Al downgrade il vecchio codice non leggerà lo schema 2;
  renderlo esplicito e non cancellare o convertire automaticamente dati;
- conservare al massimo un risultato per formato previsto, con limite e politica
  di conservazione documentati; nessuna crescita illimitata;
- vietare retrocompilazione di nuovi metadati nei report vecchi quando mancavano;
- definire la matrice dei consensi: il consenso attuale ai numeri non autorizza
  testo libero, nomi di campi sconosciuti o payload integrali.

Raccolta ammessa: percorsi tecnici esatti, motivati e revisionati; tipi,
presenza e classificazioni sicure. Gli oggetti sconosciuti non vengono esplorati
ricorsivamente. Nessuna esportazione in blocco dei 34 alias o dei loro originali.
Regex generiche e limiti di lunghezza non rendono sicuro un testo arbitrario.

Invarianti: soli observer già presenti, zero GET aggiuntivi, polling invariato,
coda 4, 75 campioni, inventario 128, report 1 MiB, durate 20/60 minuti,
timer locale 30 secondi e circuit breaker del solo Collaudo. Ogni variazione
dei limiti richiede una motivazione e verifica separata.

STOP se servono payload grezzi, nomi/valori ignoti indiscriminati, nuovi endpoint,
interpretazioni FTC non provate o regressioni di privacy/carico.

### WP6 — Secondo collaudo guidato e ricostruzione P1

Responsabile: proprietario autorizzato; PM analizza soltanto l'export locale.
Dipendenze: incremento pertinente verificato e installazione di prova autorizzata.

1. Backup verificato e pacchetto precedente conservato; una sola copia Diagnostics
   sullo stesso account, controlli manuali spenti.
2. Annotare prima CPU/RAM/disco/Recorder, normali letture, eventuale integrazione
   ufficiale e app Mitsubishi. Nessuna soglia universale di risorse viene inventata.
3. Eseguire 20 minuti; osservare reattività, riuscite/fallite, perdite, 429 e
   persistenza. Confrontare con la baseline, tenendo conto della fase del polling.
   Non imporre al test reale di 20 minuti un conteggio derivato dalla simulazione di un'ora.
4. Confrontare nell'app valori già visibili, orario e semantica acqua/ambiente;
   un setpoint generico non viene identificato automaticamente come mandata attiva.
5. Non modificare modalità, temperature, sensori o impostazioni per creare eventi.
6. Fermare soltanto il Collaudo in caso di rallentamento o problema persistente;
   esportare il risultato completo o parziale dalla diagnostica ufficiale HA.
7. Rivedere privacy e metadati prima dell'analisi locale; misurare di nuovo il
   carico dopo la sessione. Non abilitare 24 ore.
8. Confermare privatamente le date degli episodi e degli interventi con il
   proprietario. Non ricostruire impostazioni precedenti al guasto dai dati successivi.

Consegna: rapporto rivisto, confronto manuale e lacune residue motivate.
Se manca un contatore o una misura indipendente, indicare il controllo come
non verificato: il solo JSON non certifica traffico totale o carico di HA.

## 5. Regole di collaborazione e controllo dei token

- Tre analisi parallele al massimo; per le modifiche, parallelismo soltanto su
  file disgiunti e dopo un contratto approvato dal PM.
- Un implementatore possiede `core/test_session.py`/`core/schema.py`; il revisore
  privacy commenta prima di modificarli. Nessuna scrittura concorrente sullo stesso file.
- Contesto minimo: task, contratto, sezioni pertinenti e risultato atteso.
  Niente fork dell'intera conversazione o copia del report autentico ai subagenti.
- `gpt-6-luna` medium per checklist, inventari e documentazione già specificata;
  `gpt-6.1-sol` medium per core e test; high per contratti/privacy/migrazioni.
  Escalation solo se emerge una difficoltà concreta. Nessun modello più costoso
  per semplice formattazione o controlli meccanici.
- Output brevi: file coinvolti, evidenze, diff/test e punti aperti. Il PM mantiene
  una sola decisione condivisa, evitando audit duplicati.
- Test mirati per sviluppare; suite completa e build centralizzate ai gate.
  Il risparmio di token non viene quantificato senza metriche effettive.

## 6. Comandi previsti ai gate, non eseguiti da questo piano

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check custom_components tests tools
git diff --check
.venv/Scripts/python.exe tools/build_release.py --output-dir dist/validation-report-fix
```

Il pacchetto è solo di validazione finché versione, contenuti, schema,
compatibilità e autorizzazioni di rilascio non sono definiti. Non caricarlo su
una release esistente. Per UI modificata: smoke test HA isolata con dati sintetici;
desktop/mobile, chiaro/scuro e download tramite HA. Rigenerare screenshot solo
se l'interfaccia è cambiata.

## 7. Rischi e criterio finale di completamento

| Rischio | Contromisura / decisione |
|---|---|
| Nuove chiavi rifiutate dal validator 0.4.0 | Incremento A senza estensioni; incremento B con schema e downgrade espliciti |
| Perdita di distinzione assente/null nel bounding | Usare la prova strutturale disponibile; nuova cattura versionata solo se necessaria |
| Testo FTC contenente etichette o identificativi | Prima verifica locale; esportazione solo a vocabolario finito revisionato |
| Alias interpretati come campi universali | Nessun mapping fra sessioni; nessuna retrodecodifica promessa |
| Dati dopo il guasto scambiati per dati precedenti | Timeline con fonte/timestamp; causa e sensore restano unknown senza prova |
| Allargamento del progetto a hardware o nuovi protocolli | Fuori perimetro; eventuale decisione successiva sulle lacune dimostrate |
| Regressione dell'acquisizione ordinaria | Gate di non interferenza e isolamento dello storage diagnostico |

L'incremento A è concluso quando il bug è riprodotto da test sintetici, la
correzione passa, i vecchi reader accettano i nuovi report, il nuovo reader
accetta i vecchi, i gate privacy/isolamento sono positivi e la documentazione
descrive il comportamento effettivo. Nessun obiettivo di diagnosi certa del P1.

L'incremento B non è obbligatorio per chiudere A: si apre soltanto con una
lacuna precisa, un contratto sicuro e beneficio verificabile. Asgard o strumenti
ufficiali si valutano dopo questa analisi; non ne è autorizzato l'acquisto o uso.

Questa attività produce il piano e le analisi delegate. Non implementa modifiche
runtime, non cambia versioni, non esegue commit/push/merge/release o installazioni.
Implementazione locale, futura pubblicazione e collaudo reale restano passi
distinti; per le operazioni esterne occorre l'autorizzazione specifica pertinente.

Riferimenti: [Collaudo guidato](COLLAUDO_GUIDATO.md),
[requisiti e compatibilità](REQUISITI_E_COMPATIBILITA.md),
[note 0.4.0](RELEASE_040.md).

Per i criteri di delega sono state consultate le pagine ufficiali OpenAI
[Model selection](https://developers.openai.com/api/docs/guides/model-selection)
e [Multi-agent](https://developers.openai.com/api/docs/guides/agents-api/multi-agent).
La documentazione raccomanda incarichi indipendenti e circoscritti; piccoli
passaggi sequenziali restano al coordinatore. Più agenti possono aumentare i
token complessivi. I nomi effettivamente usati nella tabella sono quelli
disponibili nel catalogo di questa sessione, senza stime di prezzo o risparmio.
