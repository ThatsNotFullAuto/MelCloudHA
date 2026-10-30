# MELCloud Diagnostics — Home Assistant

Versione **0.2.0**, per Mitsubishi Ecodan tramite **MELCloud Home**.
Acquisizione diagnostica di sola lettura predefinita, con modifiche manuali
opzionali vincolate a due conferme distinte. Non richiede Asgard.

È un prototipo verificato con dati sintetici, non ancora collaudato con
l'account o l'impianto reale. Non è l'integrazione ufficiale Home Assistant.

## Cosa è implementato

- Configurazione dall'interfaccia HA e riautenticazione.
- Lettura delle unità aria-acqua di proprietà dell'account ogni 60 secondi.
- Temperature ambiente e ACS, setpoint osservati, metodo di regolazione
  per zona, stato operativo, codice guasto, errore attivo, connessione,
  abilitazione macchina, forzatura/inibizione ACS, RSSI e modello FTC
  quando forniti dal cloud. Zona 2 solo se compare nei dati.
- Lettura dello storico errori ogni 15 minuti, se autorizzato e disponibile.
- Ultimo errore, descrizione, date di comparsa/cessazione e conteggio dei
  P1 conosciuti negli ultimi 30 giorni. Uno storico non disponibile non
  viene mostrato come zero guasti.
- Registro persistente dei guasti, aggiornamento della loro cessazione,
  deduplicazione e conservazione anche se il cloud restituisce poi meno dati.
- Snapshot dei valori disponibili alla rilevazione di un errore e registro
  delle variazioni osservate di metodo di regolazione e setpoint.
- Evento HA `melcloud_diagnostics_observation` per notifiche/automazioni.
- Esportazione tramite **Scarica diagnostica** dell'integrazione, senza
  password, token, nome dell'abitazione o UUID delle unità.

Gli snapshot sono acquisiti quando il software osserva il guasto, non
necessariamente nell'istante fisico del guasto. I dati cloud possono essere
ritardati. I valori assenti restano sconosciuti; non diventano 0 °C o “nessun errore”.

## Installazione per una prima verifica in sola lettura

Requisito di riferimento: **Home Assistant 2026.10.4**, Python >= 3.14.2.
Non sostituire file della componente ufficiale `melcloud_home`.

1. Copiare `custom_components/melcloud_diagnostics` nella directory
   `config/custom_components/` dell'istanza HA scelta.
2. Riavviare HA.
3. Aggiungere **MELCloud Diagnostics** da Impostazioni → Dispositivi e servizi.
4. Inserire email e password MELCloud Home nella UI HA, non in file del
   repository o nella chat. Il campo password è mascherato.
5. Lasciare disabilitata l'opzione per le modifiche. Verificare dati,
   metodo di regolazione e disponibilità storico; scaricare la diagnostica
   per il confronto con il display/MELCloud Home.

L'account deve essere quello di **MELCloud Home**, non del servizio MELCloud
precedente. La prima versione considera le unità negli edifici di proprietà
(`buildings`); non include `guestBuildings`.

HA conserva le credenziali nella config entry secondo il normale modello
di questa integrazione: non è un archivio segreti separato. Proteggere
accesso amministrativo e backup. Il codice non stampa credenziali o token.

L'eventuale integrazione ufficiale esistente mantiene i suoi comandi:
la nostra modalità di sola lettura si applica solo a **MELCloud Diagnostics**.

## Modifiche opzionali con doppia conferma

Non vengono create entità `climate`, `number`, `select`, `switch` o azioni
di comando che possano aggirare il percorso di conferma.

In **Configura** dell'integrazione:

1. Aprire **Permessi di controllo** e abilitare le modifiche manuali.
   Questa abilitazione da sola non invia comandi e non vale come conferma.
2. Aprire **Proponi modifica setpoint**, scegliere unità, parametro e valore.
3. Prima schermata: confrontare valore corrente, nuovo valore e limiti,
   selezionare esplicitamente la casella e proseguire. Nessun comando inviato.
4. Seconda schermata: verificare di nuovo la stessa modifica, selezionare
   la seconda casella e proseguire. Solo adesso può essere inviato un comando.

Entrambe le caselle partono deselezionate. Una proposta vale 120 secondi
complessivi ed è legata al flusso UI, all'unità, al parametro e al valore.
Un token già usato non può essere riutilizzato. Il riavvio, il reload o la
disabilitazione del controllo invalidano le proposte ancora pendenti.

Prima di ciascuna conferma operativa viene riletta l'unità; se il valore,
la modalità rilevante o i limiti sono cambiati, la proposta viene rifiutata.
Connessione e assenza di guasti devono essere esplicite nei dati.

Parametri ammessi nella prima versione:

| Parametro | Condizioni |
|---|---|
| `SetTankWaterTemperature` | ACS presente, limiti e passo dichiarati |
| `SetTemperatureZone1` | Metodo HeatRoomTemperature o CoolRoomTemperature |
| `SetTemperatureZone2` | Come sopra e Zona 2 confermata dalle capabilities |

**I setpoint di mandata non sono ancora scrivibili.** L'impianto descritto
nell'handoff usa probabilmente la regolazione in mandata: in quel caso
le modifiche ai setpoint di zona vengono intenzionalmente rifiutate.
Non è corretto applicare all'acqua gli stessi limiti usati per la temperatura
ambiente. Servono dati reali per validare i limiti appropriati prima di estenderli.
Anche l'ACS viene rifiutata se il cloud non fornisce limiti e passo utilizzabili.

Esclusi reset errori, cancellazioni, commutazione caldo/freddo, protezioni,
antilegionella, commissioning, sensori FTC, relè, scritture Asgard e comandi liberi.

Ogni tentativo viene registrato prima dell'invio. Nessun reinvio automatico
in caso di timeout e nessun rollback automatico. Esiti:

- `pending`: intenzione salvata; se HA è stato interrotto, non è noto se
  l'invio sia iniziato. Nessuna ripresa automatica al riavvio.
- `outcome_unknown`: invio fallito o timeout; il comando potrebbe essere
  stato applicato. Controllare l'impianto prima di crearne un altro.
- `accepted_unverified`: il server ha accettato, ma la lettura successiva
  non ha confermato il valore.
- `observed_requested_value`: la lettura cloud successiva mostra il valore
  richiesto; non dimostra da sola l'esecuzione fisica.
- `cancelled_before_send`: controllo revocato o proposta scaduta durante
  il salvataggio dell'intenzione; comando non inviato.

Non è disponibile un aggiornamento atomico condizionato lato server:
una modifica esterna può intervenire tra l'ultima lettura e l'invio.
Il vincolo è applicativo; il token Mitsubishi mantiene i privilegi originali.
La doppia conferma non protegge da codice ostile con accesso amministrativo a HA.

## Notifica di un errore osservato

Esempio da adattare al proprio servizio di notifica:

```yaml
alias: Ecodan - nuovo errore osservato
triggers:
  - trigger: event
    event_type: melcloud_diagnostics_observation
    event_data:
      type: active_fault
actions:
  - action: persistent_notification.create
    data:
      title: "Errore Ecodan"
      message: "Codice osservato: {{ trigger.event.data.code }}"
```

Altri tipi: `setting_changed` e `cloud_fault_added`. Il caricamento iniziale
dello storico non genera una raffica di notifiche su guasti vecchi.
Una variazione osservata non identifica chi l'ha effettuata e non viene
automaticamente etichettata come errore di configurazione.

## Persistenza e limiti diagnostici

Registro in `.storage/melcloud_diagnostics.<entry_id>` nell'istanza HA.
Conserva tutti i guasti importati, le ultime 1000 osservazioni per unità e
gli ultimi 1000 tentativi di comando. Il file contiene dati tecnici e date,
non password o token. Includerlo nei backup e scaricare report periodici
se si desidera conservare tutte le osservazioni oltre questi limiti.
La rimozione dell'integrazione non cancella automaticamente questo registro.

- Storico cloud e storico completo FTC non sono dimostrati equivalenti.
- Le date senza fuso orario vengono rifiutate invece di indovinare il fuso;
  lo storico sarà indicato non disponibile se la risposta usa quel formato.
- Non è implementata una baseline di commissioning certificata dal tecnico.
- Non è dimostrata la lettura della selezione TH1A/TH1B: P1 viene registrato,
  non diagnosticato automaticamente come sensore guasto o configurazione errata.
- Non sono implementati lettura dei report energetici, WebSocket,
  compressore/portata locali o Bluetooth. Nessun valore viene inventato.

## Estensione Asgard

Il modulo `core/sources.py` definisce il confine delle sorgenti. Il decoder
CN105 e il firmware Asgard non sono incorporati nell'integrazione.
Un adattatore locale futuro dovrà conservare provenienza, timestamp e
disponibilità senza sostituire silenziosamente i dati cloud.

Prima dell'hardware restano da confermare proxy MAC-597IF-E, continuità
MELCloud Home, dati disponibili in proxy e firmware diagnostico adeguato.
Non sono necessari acquisti per provare la parte cloud.
Audit: [repository Asgard](https://github.com/gekkekoe/esphome-ecodan-hp).

## Sviluppo e verifiche

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install aiomelcloudhome==0.3.1 homeassistant==2026.10.4 pytest pytest-asyncio ruff
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check custom_components tests
.venv/Scripts/python.exe tools/build_release.py
```

Test su dati sintetici: gate di conferma, scadenza/replay/concorrenza,
variazione dei valori, timeout e assenza di retry; allowlist trasporto;
storico e dati mancanti; classi/schema di flusso HA, entità e coordinator.
Non sono prove live contro Mitsubishi, né una verifica completa del frontend
HA su browser o della gestione dell'impianto fisico. Nessuna scrittura reale
è stata usata per lo sviluppo.

Autenticazione riutilizzata da `aiomelcloudhome==0.3.1`. Endpoint aggiuntivi
ricostruiti dall'APK mediante analisi statica e implementati separatamente,
senza includere codice proprietario decompilato nel pacchetto distribuibile.
L'APK proviene da un mirror e la firma non è stata confrontata con un
certificato Mitsubishi ufficiale: il protocollo resta da validare sul servizio.
