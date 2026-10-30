# Primo collaudo MELCloud Home reale — procedura preparata, non eseguita

Questa sessione non autorizza accesso all'account, installazione o avvio del
collaudo reale. I passaggi seguenti sono predisposti per un'esecuzione futura
autorizzata dal proprietario. Non richiedono Asgard, SD Tool o modifiche hardware.

## 1. Identificare e conservare il punto di partenza

Annotare privatamente versione HA/Python, versione dell'integrazione, elenco
entità, unità scelte e disponibilità dei dati nell'app. Generazione FTC e firmware
devono provenire da identificazione/documentazione tecnica: se non noti, scrivere
unknown. Non aprire l'impianto per completare il test software.

Eseguire un backup HA protetto comprendente configurazione, config entry e
`.storage/melcloud_diagnostics.<entry_id>` se esistente. Verificare che il backup
sia leggibile e conservare una seconda copia fuori dall'istanza di prova.
Proteggerlo come credenziale; non copiarlo nel repository o allegarlo a issue.
Conservare anche il pacchetto precedente e il checksum di quello da collaudare.

## 2. Preparare HA di prova senza avviare controlli preesistenti

Usare un'istanza separata, con il riferimento verificato HA 2026.10.4 e Python
≥3.14.2. Non avviare una copia completa della produzione con automazioni e
integrazioni di controllo attive. Preferire una configurazione di prova minima.
Non spostare o scollegare il modulo Mitsubishi: MELCloud Home resta disponibile.

Una sola istanza MELCloud Diagnostics deve interrogare l'account durante il test;
non sommare il polling di due copie di questa integrazione. La normale app e
l'integrazione ufficiale eventualmente già usata non vengono riconfigurate qui.
Per upgrade di un'istanza di prova esistente preservare config entry, registro e ID.

Per la release **v0.3.0** seguire la [procedura HACS](RELEASE_030.md).
Annotare versione e checksum dalla release. Le vecchie build locali 0.2.1 non
sono la 0.3.0. Per installazione manuale autorizzata, a HA di prova fermo,
copiare soltanto la cartella
`custom_components/melcloud_diagnostics` nella cartella custom_components di prova,
oppure estrarvi il contenuto di `melcloud_diagnostics.zip` nella sottocartella
`melcloud_diagnostics`. Non estrarre lo ZIP HACS nella root di configurazione.
Non sostituire la componente ufficiale e non installare sulla HA dei genitori.

## 3. Configurare esclusivamente la lettura

Avviare HA di prova e aggiungere/configurare l'integrazione tramite UI. Credenziali
solo nella UI HA; riuso account solo tramite la scelta prevista dal wizard.
Verificare **Modifiche abilitate = disattivato**. Se una vecchia config entry
di prova aveva controllo abilitato, disabilitarlo prima del collaudo; non aprire
proposte o conferme di modifica. Controllare che non esistano automazioni di prova
che richiamino controlli da altre integrazioni.

Non cambiare setpoint, regolazione, stagione, orari o modalità per creare eventi.
Non provocare P1, disconnettere sensori, resettare errori o modificare i termostati.

## 4. Osservare una finestra di almeno 20 minuti

Registrare in un foglio privato orario/fuso e letture già disponibili: temperatura
ACS/ambiente, setpoint con relativo metodo di regolazione, stato operativo,
connettività e codice errore. Confrontare con app/display senza modificarli.
Il confronto richiede orari e significato equivalenti, non solo numeri uguali:
aria/acqua sono grandezze diverse e il cloud può avere ritardo.

Verificare almeno dieci acquisizioni successive e due tentativi dello storico,
alle frequenze invariate di 60 secondi/15 minuti. Controllare tramite report i
contatori GET diagnostici, eventuali 401/403/404/429 e lo stato dello storage.
La riuscita di uno storico vuoto non prova assenza di guasti FTC. Uno storico
unsupported/unavailable non è uno zero e non invalida da solo gli altri dati.

Non aumentare il polling. In presenza di 429 o errori ripetuti raccogliere il report,
interrompere l'istanza di prova e analizzare offline, senza retry manuali ravvicinati.
Un errore storage o un commit in attesa impedisce di considerare accettato il test.

## 5. Verificare un solo riavvio/reload dell'integrazione di prova

Scaricare il primo report, eseguire un riavvio controllato di HA di prova o reload
della sola integrazione, attendere il ritorno delle letture e scaricare un secondo
report. Confrontare ID entità, guasti conosciuti e osservazioni. Un P1 rimasto
attivo non deve generare una nuova osservazione solo per il reload; non devono
essere notificati di nuovo i guasti storici iniziali.

Se P1 non è presente, la verifica P1 reale rimane non eseguita: non provocarlo.
Se non avvengono variazioni spontanee, la loro correttezza è verificata soltanto
nei test sintetici. Errori storage/cancellazioni forzate vanno provati in pytest,
non corrompendo o cancellando file dell'istanza reale.

## 6. Raccogliere e validare il report in sicurezza

Usare **Configura → Assistenza → Report pronto**, poi **Scarica diagnostica**.
Non attivare debug globale o della libreria OAuth. Se servono log, usare il solo
logger del progetto e disabilitarlo dopo la finestra; verificare file di HA perché
possono contenere messaggi di altre integrazioni.

Tenere i JSON originali in `private-captures/` o fuori dal repository. Eseguire
il [validatore offline](VALIDAZIONE_DATI_CLOUD.md). Non incollare risposte API,
token, backup o credenziali nella chat. Il report pseudonimizza le unità ma
contiene date e dati tecnici: rivederlo prima di ogni condivisione.

## 7. Criteri di esito e arresto

| Controllo | Accettazione della sola diagnostica cloud |
|---|---|
| Sicurezza | Controllo disabilitato, nessuna operazione di comando diagnostica osservata |
| Acquisizione | Snapshot ripetuti leggibili, senza errori di schema non spiegati |
| Provenienza | Fonte cloud e timestamp di acquisizione; origine ignota rimane null |
| Coerenza | Valori confrontabili con app/display o discrepanze riproducibili documentate |
| Dati assenti | Missing/invalid/stale/unsupported distinti da zero e salute confermata |
| Persistenza | Nessun errore/commit pendente; guasti e ID preservati al reload |
| Duplicati | Nessuna notifica reiterata in assenza di nuova evidenza |
| Schema | Validatore accetta il contenitore; campi invalidi analizzati separatamente |

Autenticazione non riuscita, schema inatteso, perdita di storico o errore storage
richiedono arresto della prova e analisi. Un test superato con storico inaccessibile
deve riportare esplicitamente quella limitazione. Non dimostra la causa di P1,
selezione del sensore o compatibilità di altre generazioni FTC.

## 8. Terminare e ripristinare

Fermare l'istanza di prova se il collaudo non deve proseguire; conservare report
e checksum privatamente. Non eliminare il registro per risolvere un errore.
Per rollback, a HA di prova fermo ripristinare il codice precedente; se necessario
ripristinare anche il backup coerente di config entry/storage. Riavviare e
confrontare i dati. Un backup ripristina lo storico solo fino alla sua data.
Non eseguire rollback di parametri sulla pompa: il test non ne modifica alcuno.

## Condizioni per valutare in seguito Asgard

Questa sessione non sviluppa né collauda Asgard. Il passaggio successivo richiede
tutte queste evidenze, altrimenti occorrono altre informazioni:

1. Generazione FTC e firmware identificati tecnicamente.
2. Collaudo cloud con esito registrato e inventario dei campi realmente mancanti.
3. Evidenza specifica per MAC-597IF-E su proxy SL/PX e continuità MELCloud Home;
   esempi di altri adattatori non bastano.
4. Elenco dei parametri locali effettivamente pubblicati nella modalità scelta,
   con unità, timestamp, sentinel e frequenza; vantaggio diagnostico misurabile
   rispetto al cloud. Per P1 servono prove sulla selezione/presenza sensore,
   non semplicemente un'altra temperatura ambiente.
5. Firmware/configurazione verificati senza azioni automatiche o nuovi comandi,
   e adattatore software read-only con associazione esplicita dell'unità.
6. Piano tecnico di installazione e ripristino, con autorizzazione separata.

Il solo successo del collaudo cloud non soddisfa le condizioni hardware.

## Modalità guidata disponibile dalla 0.4.0

La 0.4.0 aggiunge una sessione osservatrice avviabile dalla UI. La
[procedura guidata e checklist](COLLAUDO_GUIDATO.md) integra questa procedura,
senza autorizzare prove reali. Prima 20 minuti su HA isolata, misurando il carico
e verificando app, automazioni e polling invariati; solo dopo valutare 60 minuti.
24 ore disabilitate. Non modificare impostazioni per creare eventi. Conservare
backup e risultati parziali; nessun collaudo reale è stato eseguito da Codex.
