# Requisiti e compatibilità — v0.4.0

Questa pagina distingue requisiti del software, verifiche automatiche/frontend
e compatibilità con un impianto reale. **Nessun account Mitsubishi o dispositivo
reale è stato collaudato.** La release ordinaria distribuisce il software
disponibile, senza certificare la diagnostica completa FTC.

## Requisiti per installare e usare l'integrazione

| Elemento | Requisito | Evidenza e limite |
|---|---|---|
| Home Assistant Core | **2026.10.4 o successivo** | Minimo dichiarato in `hacs.json`; verificato su 2026.10.4. Le versioni future richiedono test, non sono garantite automaticamente |
| Python | **≥3.14.2** nell'ambiente di HA | Vincolo `pyproject.toml`; test locali con 3.14.3. HA OS/Container gestiscono il proprio Python: non cambiarlo manualmente |
| HACS | Necessario per il percorso di installazione/aggiornamento descritto | Repository personalizzata di tipo Integrazione, asset `melcloud_diagnostics.zip`. Non è stato stabilito un ulteriore numero minimo HACS |
| Libreria cloud | **aiomelcloudhome==0.3.1** | Installata da HA tramite manifest; nessuna nuova dipendenza runtime nella 0.4.0 |
| Account | **MELCloud Home**, con unità aria-acqua visibile nell'app | MELCloud classico non è un trasporto intercambiabile. Guest buildings non supportati; permessi e risposte reali ancora da verificare |
| Connessione | HA deve poter raggiungere il servizio Mitsubishi tramite HTTPS e risolverne il DNS | Internet serve anche per scaricare integrazione/dipendenze. Nessun port forwarding o IP della pompa richiesto |
| Adattatore Mitsubishi | Unità già funzionante nel servizio MELCloud Home | Non esiste una lista di adattatori certificata da questo progetto; il modello del controller non dimostra da solo il supporto cloud |
| Interfaccia | Browser compatibile con il frontend della propria versione HA | Verificato Chromium 156.0.8078.4, italiano, temi chiaro/scuro; altre versioni/browser non verificati qui |
| Hardware aggiuntivo | **Nessuno** | Asgard, ESPHome, MQTT e strumenti Mitsubishi non sono richiesti |

HACS e il riavvio di Home Assistant sono passaggi dell'installazione. Non servono
SSH, terminale o Python per avviare il Collaudo o scaricare il rapporto. Non sono
richieste schede frontend personalizzate, Mushroom o card-mod. Playwright e i
pacchetti in `tools/frontend-demo-requirements.txt` servono soltanto allo sviluppo,
non devono essere installati su Home Assistant dagli utenti.

Per la configurazione iniziale servono le credenziali MELCloud Home, oppure il
riuso esplicito di un account già configurato nell'integrazione ufficiale HA.
Il Collaudo usa la config entry esistente senza chiedere altre credenziali.
Non eliminare l'integrazione ufficiale funzionante.

## Prerequisiti del Collaudo

- Integrazione caricata e unità selezionabile fra quelle già configurate.
- **Controlli manuali disabilitati** per l'intera sessione. L'avvio viene rifiutato
  se abilitati; una loro successiva abilitazione invalida e arresta la raccolta.
  Le opzioni non vengono cambiate automaticamente.
- Prima prova autorizzata su HA isolata, backup verificato, spazio disco libero
  e possibilità di controllare CPU/RAM/Recorder, normali letture e app Mitsubishi.
- Non avviare due copie Diagnostics sul medesimo account per duplicare il polling.
- Durata **20 o 60 minuti**; 24 ore non disponibili. Una sessione e un risultato
  per config entry; esportare il precedente prima di autorizzarne la sostituzione.

Non è stata misurata una soglia minima universale di CPU/RAM o spazio disco.
I limiti logici sono coda 4, 75 campioni, 128 eventi/guasti/percorsi per categoria
e report 1 MiB; non equivalgono a un limite RSS dell'intero processo HA. Un errore
storage arresta il solo Collaudo: dopo un crash sono garantibili soltanto i dati
già confermati, nei limiti del disco e del backup. Vedi [isolamento](COLLAUDO_GUIDATO.md).

## Compatibilità verificata del software

| Ambito | Verifica effettiva | Cosa non dimostra |
|---|---|---|
| Core 2026.10.4 / Python 3.14.3 | Suite sintetica e vero frontend HA Linux/WSL | Funzionamento con API/account reale o benchmark sull'hardware domestico |
| CI pinned / latest | Ogni job registra la versione HA risolta | Se entrambi risolvono 2026.10.4, è una sola versione HA verificata, non due |
| Desktop | Viewport 1440×1000, Chromium, temi chiaro/scuro | Altri browser o verifica completa di accessibilità |
| Smartphone | Viewport 390×844, stessa UI reale, chiaro/scuro | Telefono fisico, Safari/iOS, Android WebView o companion app |
| Aggiornamento da 0.3.0 | Config entry 1.1 e journal storage 1 preservati, test sintetici | Upgrade/downgrade completo su un'installazione reale |
| Dashboard esistenti | Non sovrascritte; nuova vista solo dal generatore YAML | Installazione automatica della vista nelle plance personalizzate |
| Integrazione ufficiale `melcloud_home` | Nessuna modifica alle sue config entry o ai suoi intervalli | Coesistenza sullo stesso account verificata sul campo |

I test Python su Windows non sono una dichiarazione di supporto a installazioni
HA di produzione su Windows. Il frontend completo è stato eseguito su Linux/WSL;
il comportamento sulle piattaforme HA dell'utente richiede la prova progressiva.
Versioni e risultati della verifica sono nel [rapporto frontend](VERIFICA_FRONTEND_2026-10-30.md).

## Compatibilità FTC4–FTC7 e sorgenti

| Generazione | Modello diagnostico | MELCloud Home per quella generazione | CN105/Asgard locale | Importazione SD/report di servizio |
|---|---|---|---|---|
| FTC4 | Implementato, fixture sintetiche | **Unknown** sull'impianto reale | Non implementata | Non implementata |
| FTC5 | Implementato, fixture sintetiche | **Unknown** sull'impianto reale | Non implementata | Non implementata |
| FTC6 | Implementato, fixture sintetiche | **Unknown** sull'impianto reale | Non implementata | Non implementata |
| FTC7 | Implementato, fixture sintetiche | **Unknown** sull'impianto reale | Non implementata | Non implementata |

Il trasporto MELCloud Home è implementato; non è certificato per ogni FTC,
firmware, modello o adattatore. Il software non deduce la generazione dal solo
nome dell'HydroTank. Le capacità dichiarate da progetti upstream sono evidenze
documentali distinte, non funzioni operative di questa integrazione: consultare
[matrice e fonti tecniche](SORGENTI_E_COMPATIBILITA.md).

MAC-597IF-E è il riferimento del futuro collaudo MELCloud Home, non una prova già
ottenuta. La coesistenza/proxy MAC-597IF-E con Asgard è **sconosciuta**. Non viene
consigliato un acquisto come sicuramente compatibile.

## Dati e limiti diagnostici

Temperature, stati, modalità, errori e storico dipendono da quello che il cloud
espone e dai permessi. Lo storico inaccessibile non equivale a zero guasti;
valori assenti o sconosciuti non diventano zero. Timestamp di acquisizione non
sono automaticamente gli istanti fisici degli eventi.

La causa degli episodi P1 non è identificata. Lettura e selezione TH1A/TH1B,
presenza del sensore selezionato, firmware e configurazione FTC completa non
sono verificate. Nessun decoder SD, Bluetooth o CN105, nessun comando operativo
aggiuntivo e nessuna correzione automatica. Le credenziali conservano i privilegi
dell'account: la modalità read-only è una separazione software.

[Installazione](GUIDA_UTENTE.md) · [Release 0.4.0 e ripristino](RELEASE_040.md) ·
[Primo collaudo di 20 minuti](COLLAUDO_GUIDATO.md).
