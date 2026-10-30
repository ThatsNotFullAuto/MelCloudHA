# Diagnostica P1 e collaudo sicuro

## Cosa può dire oggi il software

Registra P1 se osservato nel cloud e mantiene i guasti storici disponibili,
gli orari forniti dalla sorgente, gli snapshot alla rilevazione e le variazioni
osservate di setpoint/metodo. Un conteggio riguarda solo i guasti conosciuti.
Non ricostruisce retroattivamente valori non acquisiti e non identifica chi ha
cambiato un'impostazione. I due episodi riferiti dall'utente non sono inseriti
automaticamente come eventi misurati o fixture reali.

P1 non identifica da solo TH1A come causa. La
[nota tecnica Mitsubishi/Alklima](https://kennisbank.alklima.nl/hc/nl/articles/37602867442321-P1-storing)
include la selezione del sensore fra le verifiche. Occorre confrontare generazione,
revisione, sensore selezionato, presenza fisica e configurazione reale con un
tecnico. Il progetto non legge ancora selezione/presenza del sensore.

| Regolazione | Interpretazione prudente |
|---|---|
| Temperatura mandata | Target acqua, diverso dal termostato ambiente |
| Curva climatica | Dipende dalla regolazione climatica; non prova necessità di termostato ambiente dedicato |
| Temperatura ambiente / Auto Adaptation | Richiede un riferimento ambiente valido e configurato |

27 °C su un termostato e circa 11,5 °C nell'app non sono automaticamente in
contraddizione: possono riferirsi ad aria e acqua. Non ricaviamo configurazione
idraulica, consenso zone o protezione anticondensa da questi numeri.

## Evidenze utili al tecnico

Conservare report già disponibili, data e fuso dell'episodio, codice esatto,
generazione e revisione verificate, metodo di regolazione e cambi precedenti.
Un eventuale report ufficiale dovrebbe includere sensore selezionato, ingressi,
identificatore del termistore e valori al guasto, se realmente disponibili.
Request codes 103–105/504/507/555/556/567 sono piste documentali da verificare
sulla revisione applicabile; non sono comandi CN105 implementati. Non provocare
un guasto e non cambiare parametri per ottenere una prova.

L'associazione stagionale richiede date affidabili e più eventi: due racconti
senza telemetria non dimostrano una relazione causale. Analogamente una misura
implausibile richiede limiti documentati o una baseline tecnica approvata.

## Collaudo immediato senza hardware

Eseguire i test del repository e la build isolata indicati nel rapporto audit.
Le fixture sono interamente sintetiche, anche per FTC4–FTC7. Verificano missing,
zero, errori, timezone, stale, duplicati, conflitti e assenza di nuove richieste.
Il round trip JSON del registro verifica lettura dopo riavvio; i test esistenti
verificano config entry, gate di controllo, entità e migrazioni precedenti.

## Collaudo reale futuro, da autorizzare separatamente

Prima identificare controller/firmware senza deduzione dal solo modello e
ottenere un backup HA. Confrontare letture già disponibili con display e app,
registrando ritardi e storico non accessibile. Servono esempi anonimizzati di
risposte cloud e, separatamente, un export ufficiale con tool/revisione/fuso
noti. Non richiedere payload integrali con segreti. Il polling deve rimanere
alle frequenze attuali, con controllo disabilitato.

Asgard avrà senso soltanto dopo prova specifica di compatibilità MAC-597IF-E,
continuità MELCloud Home, campi realmente disponibili nel trasporto scelto e
verifica di un firmware/configurazione senza azioni automatiche. Non è un
acquisto consigliato come sicuramente compatibile. EAC-MT-M1 può essere utile
per un sopralluogo tecnico FTC6/7 e per export; non è qui una sorgente continua
HA. Gli export SD potrebbero aggiungere storico/configurazione: prima occorrono
file autentici e una specifica verificata.

Per rollback e backup vedere [Aggiornamenti](AGGIORNAMENTI.md). Nessuna prova
descritta per il futuro è stata eseguita su account, HA o impianto dei genitori.

## Collaudo guidato — dalla 0.4.0

Il report della nuova sessione distingue P1 osservato attivo, record storici
accessibili e timestamp di osservazione. Selezione/presenza del sensore e causa
rimangono UNKNOWN: il collaudo non identifica TH1A/TH1B e non provoca guasti.
Leggere [guida operativa e limiti](COLLAUDO_GUIDATO.md) prima di una futura prova
autorizzata. La sessione è disponibile in HACS dalla v0.4.0.
