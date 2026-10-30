# MELCloud Diagnostics v0.4.0

**Release ordinaria. Nessun collaudo con account Mitsubishi o impianto reale è
stato eseguito. Gli screenshot sono del vero frontend HA con dati sintetici.**

Prima di installare leggere [requisiti e compatibilità](REQUISITI_E_COMPATIBILITA.md):
HA ≥2026.10.4, Python ≥3.14.2 nell'ambiente HA, account MELCloud Home e Internet.
HACS è il percorso descritto; nessun hardware o plugin frontend aggiuntivo.

## Cosa cambia

Rispetto alla sola visualizzazione nell'app MELCloud Home, l'integrazione offre
monitoraggio diagnostico in Home Assistant, conservazione degli errori
osservabili e dei cambiamenti disponibili, verifiche automatiche di struttura e
un rapporto tecnico esportabile. La nuova modalità **Collaudo diagnostico**
raccoglie queste evidenze in una sessione guidata di **20 o 60 minuti**.

Si avvia da **Impostazioni → Dispositivi e servizi → MELCloud Diagnostics →
Configura → Diagnostica → Collaudo diagnostico**. Si sceglie la pompa, si avvia
e si segue la vista Diagnostica della plancia: barra percentuale reale, durata,
trascorso/residuo, contatori e stati cloud/storico/persistenza. Chiudere il browser
non interrompe la sessione. **Interrompi collaudo** ferma solo la raccolta e
conserva un risultato parziale. Il 100% indica tempo trascorso, non impianto sano.

![Collaudo nel vero frontend HA — dati sintetici](images/diagnostics-collaudo-running.png)

[Avvio e durata](images/diagnostics-collaudo-start.png) ·
[Completamento](images/diagnostics-collaudo-complete.png) ·
[Parziale](images/diagnostics-collaudo-partial.png) ·
[Vista smartphone](images/diagnostics-collaudo-running-mobile.png).
Tutte le [11 immagini e la loro provenienza](SCREENSHOT_COLLAUDO.md).

## Sicurezza e qualità

La sessione osserva le acquisizioni ordinarie, senza nuovi GET, refresh o retry.
Non possiede writer/client cloud e non invia comandi operativi. I controlli
manuali devono essere disabilitati; se abilitati durante una sessione, questa
si arresta con `control_permissions_changed` e FAIL delle condizioni, senza
cambiare automaticamente l'opzione. L'account mantiene i suoi privilegi:
read-only è applicato nel codice, non necessariamente dal server Mitsubishi.

Coda limitata, lavoro fuori dal percorso critico del polling, storage separato,
checkpoint atomici, limite report 1 MiB e circuit breaker del solo Collaudo.
Il journal principale e le normali entità restano indipendenti. La simulazione
di un'ora ha prodotto 64 GET con e senza Collaudo; non è un benchmark sul sistema
domestico. La durata di 24 ore resta disabilitata.

Il report schema 1 separa fatti, interpretazione e verifiche; inventaria dati
assenti, non interpretati e formati inattesi. I campi sconosciuti hanno alias e
metadati limitati, senza valori grezzi. Temperature, setpoint e RSSI conosciuti
richiedono consenso iniziale. Verifica fisica indipendente sempre distinta dai
controlli software. Nessun invio automatico di dati.

## Aggiornare con HACS

1. Fare un backup HA protetto e verificato; conservare pacchetto e checksum 0.3.0.
2. In **HACS → MELCloud Diagnostics → Aggiorna**, scegliere **v0.4.0**.
   Se necessario usare **⋮ → Scarica di nuovo / Redownload → v0.4.0**.
3. **Riavviare Home Assistant**. Non eliminare né ricreare l'integrazione.
4. Verificare i normali sensori e che i controlli manuali siano disabilitati.
5. Per la vista Diagnostica: **Configura → Genera plancia** e aggiungere il YAML
   a una nuova dashboard o copiare la sola nuova vista. Le dashboard esistenti
   non sono sovrascritte; gli ID sono risolti dal registro effettivo.

Dominio, config entry, credenziali, identificativi entità/dispositivi, preferenze
e journal storico conservano formato e identità. Nessuna migrazione distruttiva.
Lo storage del Collaudo è separato; file assente/corrotto non azzera il journal.

## Primo collaudo e report

Usare prima una **HA di prova isolata e autorizzata**, senza due copie Diagnostics
sullo stesso account. Controllare baseline CPU/RAM/disco/Recorder, app Mitsubishi,
eventuale integrazione ufficiale e normali letture. Avviare **20 minuti**,
osservare reattività e assenza di 429. Fermare il solo Collaudo se necessario.
Non cambiare setpoint, modalità o configurazioni per creare dati o guasti.

Alla fine: **⋮ dell'account dell'integrazione → Scarica la diagnostica**.
Il JSON contiene `data.diagnostic_test`, anche per stop o risultato parziale.
Con una sessione conservata il download restituisce questo report ristretto,
invece del precedente report libero dell'intero journal. Lo storico non viene
cancellato. Controllare date, metadati HA e numeri autorizzati prima di condividere
il file con Codex o nelle [issue](https://github.com/ThatsNotFullAuto/MelCloudHA/issues).
Non allegare credenziali, backup o payload grezzi; indicare a parte la categoria
dell'eventuale richiesta di assistenza. [Procedura completa](COLLAUDO_GUIDATO.md).

## Limiti della validazione

Frontend reale verificato su HA 2026.10.4/Chromium, desktop e viewport smartphone,
temi chiaro/scuro, con dati sintetici. Nessuna verifica su telefono fisico,
sistema domestico, prestazioni target o account Mitsubishi reale.
Le due righe CI pinned/latest non dimostrano compatibilità con due versioni HA
diverse se risolvono allo stesso numero: la versione effettiva è registrata nei job.

Non è una diagnostica completa dei parametri di servizio FTC4–FTC7. Causa P1
non identificata; selezione sensore e lettura TH1A/TH1B non verificate. CN105/Asgard
e importazione SD non implementati; proxy MAC-597IF-E sconosciuto. Non serve
acquistare hardware. Nessuna nuova dipendenza runtime o comando Mitsubishi.

Un disco guasto può impedire nuovi checkpoint: il report RAM è recuperabile
finché HA rimane attivo, senza garanzia dopo un crash. Un'operazione OS già
nell'executor non è fisicamente annullabile. Non viene cancellato lo storico.

## Ripristino alla 0.3.0

Esportare il risultato e interrompere il Collaudo. In HACS scegliere
**Scarica di nuovo → v0.3.0** e riavviare la sola HA di prova. Conservare config
entry e journal principale. La 0.3.0 ignora lo storage separato del Collaudo.
I contratti preesistenti sono coperti dai test sintetici; il downgrade completo
su un impianto reale non è collaudato. Se necessario usare il backup coerente,
sapendo che riporta i dati alla data del backup. Non ripristinare parametri
sulla pompa e non eliminare lo storico per risolvere un errore storage.

[Guida utente](GUIDA_UTENTE.md) · [Collaudo](COLLAUDO_GUIDATO.md) ·
[Verifica frontend](VERIFICA_FRONTEND_2026-10-30.md).
