# Guida all?installazione e all?uso

## Prima di iniziare

Servono Home Assistant Core **2026.10.4 o successivo**, HACS e un account
**MELCloud Home** con la pompa gi? visibile nell?app Mitsubishi.
La versione corrente ? stata verificata con Core 2026.10.4; i test automatici
controllano anche l?ultima stabile. Non ? una promessa per ogni versione futura.

Non servono Asgard, accesso al quadro elettrico o modifiche ai collegamenti.
Se sai gi? aprire HACS, puoi seguire questi passaggi. L?installazione di HACS
stesso non ? compresa: consulta la [sua guida ufficiale](https://www.hacs.xyz/docs/use/).

## 1. Scarica l?integrazione da GitHub con HACS

1. In Home Assistant apri **HACS**.
2. Apri il menu **? ? Repository personalizzate**.
3. Incolla `https://github.com/ThatsNotFullAuto/MelCloudHA`.
4. Scegli il tipo **Integrazione** e aggiungila.
5. Cerca **MELCloud Diagnostics**: l?icona ? una casa azzurra con tre diamanti rossi.
6. Aprila e scarica la versione pubblicata.
7. Se HA chiede il riavvio, eseguilo quando ? comodo.

Scaricare i file e configurare l?account sono due passaggi distinti.
Non rimuovere l?eventuale integrazione Mitsubishi gi? funzionante.

## 2. Avvia il wizard

Apri **Impostazioni ? Dispositivi e servizi ? Aggiungi integrazione** e cerca
**MELCloud Diagnostics**. La schermata di benvenuto spiega cosa verr? cercato.
Premi **Avanti** per iniziare.

Il wizard non cambia temperature, modalit? o impostazioni della pompa.

## 3. Leggi i risultati della ricerca

Il wizard controlla gli account della componente ufficiale **MELCloud Home**
gi? configurati in questa istanza HA. Se ne trova uno, puoi riutilizzarlo
senza riscrivere la password: l?indirizzo ? mostrato parzialmente mascherato.
Il riuso avviene soltanto dopo la tua scelta.

Cerca anche annunci ESPHome in rete e consulta i dispositivi gi? registrati
in HA. I risultati indicano l?origine: **registrato in HA** oppure
**rilevato in rete, da verificare**. I nomi sono indizi, non identificazioni certe.
Non viene avviata una scansione delle porte o tentato un accesso ai dispositivi.

La MAC-597IF-E pu? non comparire e ci? **non impedisce** il monitoraggio cloud.
Il wizard non pu? recuperare account o password dalla rete.

## 4. Accedi, se necessario

Scegli un account gi? trovato oppure **Accedi con un altro account**.
Usa le stesse credenziali dell?app **MELCloud Home**: non quelle del Wi-Fi,
di Home Assistant o del vecchio servizio MELCloud.

Se non ricordi la password, recuperala nell?app Mitsubishi e torna qui.
Le credenziali si inseriscono soltanto nella UI HA, non nella chat o su GitHub.
HA le conserva nella propria configurazione: proteggi accesso e backup.

## 5. Scegli la pompa

Dopo l?accesso compaiono le pompe aria-acqua associate al tuo account.
Seleziona quelle da monitorare, confrontandone i nomi con l?app Mitsubishi.
La prima versione non include gli impianti condivisi come ospite.

Il riepilogo finale elenca la selezione e conferma che partirai in **sola lettura**.
Conferma per completare l?aggiunta.

## 6. Controlla le prime letture

Apri il dispositivo appena aggiunto. Attendi il primo aggiornamento e confronta
qualche dato con MELCloud Home: temperatura acqua sanitaria, stato operativo,
metodo di regolazione e codice errore, se presente.

Un valore **sconosciuto** o **non disponibile** pu? dipendere dal cloud o da un
sensore non esposto; non indica automaticamente un guasto. Le letture possono
arrivare in ritardo. Lo storico errori viene interrogato ogni 15 minuti.

Se un valore non coincide, conserva il report: menu dell?integrazione ?
**Scarica diagnostica**. Le letture disponibili sono sufficienti per iniziare;
non occorre abilitare le modifiche.

## La plancia Ecodan

1. Apri **Configura** di MELCloud Diagnostics.
2. Scegli **Prepara la plancia Ecodan**.
3. Copia l?intero testo di configurazione mostrato: contiene gi? i nomi
   corretti dei tuoi sensori. Non modificare i nomi a mano.
4. Crea una **nuova plancia vuota** da **Impostazioni ? Plance** e aprila.
5. Apri **Modifica plancia ? ? ? Editor di configurazione grezza**.
6. Incolla il testo al posto del contenuto della nuova plancia e salva.

La preparazione non installa automaticamente la plancia. Usa una plancia
nuova per non sostituire una configurazione che utilizzi gi?. I nomi dei menu
possono variare leggermente con lingua e versione del frontend HA.

La plancia segue il tema chiaro/scuro di HA ed ? suddivisa in stato generale,
acqua sanitaria, zone, grafico di 24 ore, guasti e collegamento. Una vista per
ciascuna pompa. Il grafico si popola con le letture future e richiede che il
Recorder di HA registri questi sensori.

Le icone aprono i dettagli: **non inviano comandi**. Le impostazioni di zona
possono riferirsi all?acqua: leggerle sempre insieme al metodo di regolazione.
La plancia non ricava le temperature di tutti i termostati delle camere.

Puoi poi personalizzare le schede con l?editor visivo HA. Gli aggiornamenti
dell?integrazione non sovrascrivono le modifiche alla tua plancia.
Se rinomini manualmente un?entit? e una scheda perde il riferimento, rigenera
la configurazione e adatta la scheda interessata.

## Cambiare una temperatura, solo se desiderato

Questa funzione ? separata dal monitoraggio e disabilitata inizialmente.

1. **Configura ? Permessi di controllo**: abilita le modifiche manuali.
2. Torna in **Configura ? Proponi modifica setpoint**.
3. Scegli la pompa e una temperatura con nome comprensibile.
4. Controlla valore attuale e limiti; inserisci il nuovo valore.
5. Prima conferma: rileggi il riepilogo e seleziona la casella per continuare.
6. Seconda conferma: autorizza l?invio della precisa modifica mostrata.
7. Leggi l?esito. Se non ? verificato, controlla app/display prima di riprovare.

Entrambe le caselle partono deselezionate. La procedura scade dopo due minuti
dalla creazione della proposta. Se cambi idea, chiudi il wizard o prosegui
senza spuntare la conferma. Nessun invio avviene fino alla seconda conferma.

Se la zona usa la temperatura dell?acqua in mandata, la modifica ambiente
viene rifiutata: **non cambiare la regolazione dell?impianto per sbloccarla**.
Questa prima versione permette solo ACS e setpoint ambiente nelle condizioni
supportate. Non offre reset o configurazioni tecniche.

## Se qualcosa non funziona

| Cosa vedi | Cosa fare |
|---|---|
| Nessun account trovato | Scegli accesso manuale: l?account pu? esistere nell?app ma non in HA |
| Nessun dispositivo trovato in rete | Prosegui con l?account Mitsubishi; la MAC-597IF-E pu? non annunciarsi |
| Accesso non riuscito | Verifica le stesse credenziali nell?app MELCloud Home |
| Account valido ma nessuna pompa | Controlla account, tipo aria-acqua e propriet?; ospiti non ancora supportati |
| Storico non accessibile | Continua con i sensori disponibili; non equivale a zero guasti |
| Grafico vuoto | Attendi letture e verifica il Recorder; i dati non sono retroattivi |
| Temperatura non modificabile | Mantieni il monitoraggio e controlla app/display; non modificare la configurazione FTC |
| Esito del comando non noto | Non ripetere subito: il comando potrebbe essere arrivato |

Per segnalazioni usa le [issue del progetto](https://github.com/ThatsNotFullAuto/MelCloudHA/issues).
La repository ? pubblica: non allegare password, token, backup HA o foto con
dati personali. Il report diagnostico omette le credenziali, ma contiene date
e dati tecnici: controllalo prima di condividerlo pubblicamente.
