# Modello diagnostico comune — 0.3.0

## Confini

Un'unica integrazione `melcloud_diagnostics`. Entità, dashboard e journal
continuano a consumare gli snapshot cloud precedenti. `core/telemetry.py` e
`core/capabilities.py` non dipendono da Home Assistant o da trasporti; il cloud
viene adattato da `core/cloud_telemetry.py`. Nessun nuovo pacchetto Python.

`DiagnosticSource` conserva il contratto cloud esistente. `TelemetrySource`
definisce soltanto la futura lettura di fatti; `ServiceExportImporter` definisce
la trasformazione offline di byte già acquisiti legittimamente. Sono Protocol,
senza implementazione ESPHome, MQTT, SD o Bluetooth e senza metodi di comando.
La protezione concreta attuale è più limitata e verificabile: l'adattatore cloud
è una funzione pura senza client di rete, writer o accesso a controller.

## Osservazione

`Observation` è immutabile: unità logica interna, parametro, valore scalare,
unità di misura, acquisizione, origine opzionale, fonte e istanza della fonte,
generazione FTC dichiarata, disponibilità, validazione e revisione opzionale.
I nomi dei parametri attuali conservano quelli cloud; futuri adattatori devono
mapparli esplicitamente e distinguere temperatura ambiente, acqua e setpoint.
L'associazione fra ID cloud e dispositivo locale deve essere verificata: nessun
abbinamento per nome, generazione o indirizzo IP.

| Campo | Significato |
|---|---|
| `acquired_at` | Quando il software ha ricevuto il fatto |
| `origin_at` | Data della misura/evento fornita dalla sorgente, se verificata |
| `available` | Valore presente, incluso zero o false |
| `missing` | Campo assente/null; se malformato la validazione è `invalid` |
| `unsupported` | Sorgente che dichiara esplicitamente l'indisponibilità |
| `acquisition_error` | Lettura fallita, senza valore sostitutivo |
| `unknown` | Disponibilità non determinata |
| `stale` | Valore conservato oltre l'età massima scelta dal consumatore |
| `structural` | Tipo/formato utilizzabile, nessuna validazione fisica |
| `verified_real` | Riservato a evidenza reale; mai attribuito dalle fixture/cloud adapter |
| `invalid` | Formato errato o timestamp futuro rispetto al confronto |

Le date devono avere fuso esplicito e vengono normalizzate UTC. Nessuna data
originaria viene ricavata dal semplice orario del poll. Nessuna soglia fisica è
introdotta. Il limite 180 secondi del report è una politica di aggiornamento.
Una lettura di export con data originaria vecchia rimane vecchia anche se appena
importata. La data futura rende il fatto inutilizzabile nel confronto.

## Capabilities

Il registry distingue `unknown`, `documented_unverified`, `verified_real` e
`unavailable`. Una prova documentale richiede riferimento; contesto modello,
firmware, adattatore e trasporto restringe la corrispondenza. Si sceglie la prova
più specifica solo se univoca; conflitti restituiscono `unknown`.
Il registro iniziale documenta soltanto la mappatura identificativa 0xC9 per
FTC4–FTC7 e il limite energia istantanea FTC5, per il trasporto CN105 upstream.
Tutto il resto, cloud incluso, resta `unknown` in assenza di prova contestuale.
Una misura cloud disponibile non costituisce una certificazione della capacità
su tutti i controller della stessa generazione. Il registry non attiva driver.

## Confronto multi-sorgente

`compare` è una funzione pura per un solo parametro/unità. Conserva tutte le
osservazioni distinte, deduplica ripetizioni identiche e considera le più recenti
per acquisizione di ciascuna coppia fonte/istanza. Un successivo fallimento
esplicito impedisce di riutilizzare di nascosto una vecchia misura di quella fonte.
Conflitti con lo stesso timestamp restano visibili. Non sceglie un vincitore,
non modifica entità o journal e non genera eventi di variazione.

I candidati escludono valori assenti, stale, non validati o invalidi. Il confronto
esatto richiede almeno due candidati di tipo e unità uguali entro una finestra
temporale configurata dal chiamante. `disagreement=None` significa non
confrontabile; true significa solo valori diversi, non un guasto. Nessuna
tolleranza termica, calibrazione o soglia ufficiale viene presunta. Un eventuale
fallback operativo richiederà una politica esplicita e test separati.

## Persistenza e motore futuro

Involucro storage 1 invariato, con aggiunte opzionali retrocompatibili:
`previous_observed_at` per unità e `event_id` nei nuovi eventi. Nessuna
conversione delle chiavi guasti precedenti o cancellazione dei dati. La vista
normalizzata vive in memoria e nel report; il journal conserva guasti,
variazioni e nuove notifiche di guasti storici. Non esiste
ancora un buffer continuo di misure prima del guasto, né un motore di diagnosi P1.
Il journal resta cloud: non va alimentato con sorgenti alternate. Una futura
persistenza multi-sorgente richiederà schema versionato, timestamp per singolo
fatto, lettura del formato precedente e test di backup/upgrade/rollback.

Le regole deterministiche future dovranno restituire conclusioni separate dai
fatti e citare evidenze/limiti. Baseline approvata dal tecnico per incoerenze di
modo; fonte o configurazione approvata per portata e temperature; campionamento
adeguato per cicli compressore; date reali per ricorrenze stagionali. Nessuna
regola o azione correttiva automatica è attualmente aggiunta.

Il consolidamento usa copie di lavoro del journal: stato pubblicato, metadati
storico e notifiche avanzano solo dopo conferma dello storage. Una scrittura
incerta viene ritentata identica prima di nuove acquisizioni. Poll e audit
condividono il lock di commit; i poll sono serializzati. Il nuovo wrapper usa
Store HA con scritture atomiche e rilettura, senza API private di HA.
Le cancellazioni del task chiamante non abbandonano una scrittura in corso.
La cancellazione durante lo storico conserva prima gli snapshot già ottenuti.

`last_successful_poll` indica snapshot acquisiti e persistiti; un successivo
errore di autenticazione nello storico resta esplicito in `acquisition_state`.
Le entità possono essere indisponibili finché HA richiede riautenticazione.
Una notifica fallita non annulla un evento salvato e non viene reinviata al
riavvio. Non esiste un protocollo di ricevute sul bus HA: vedere i
[limiti di durabilità e consegna](AFFIDABILITA_E_COLLAUDO.md).
