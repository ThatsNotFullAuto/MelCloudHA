# Screenshot autentici della v0.4.0

Acquisiti il 30 ottobre 2026 dal **frontend reale Home Assistant 2026.10.4**,
frontend `20260930.5`, Chromium `156.0.8078.4`, lingua italiana, zoom 100%.
Sono dati interamente sintetici, non letture di un impianto. Le catture sono
state ripetute sul codice finale con manifest 0.4.0; nessuna immagine è un mockup.

| File in `docs/images/` | Contenuto |
|---|---|
| `diagnostics-collaudo-start.png` | Wizard reale: pompa, 20/60 minuti, consensi |
| `diagnostics-collaudo-running.png` | Sensori reali: stato, barra, timer, contatori e qualità |
| `diagnostics-collaudo-complete.png` | Scadenza naturale a 100%, controlli separati |
| `diagnostics-collaudo-partial.png` | Errore storage simulato, motivo e controllo FAIL |
| `diagnostics-collaudo-interrupted.png` | Stop manuale della sola raccolta |
| `diagnostics-collaudo-running-mobile.png` | Viewport 390×844, tema chiaro, pagina intera |
| `diagnostics-collaudo-running-mobile-dark.png` | Stessa viewport, tema scuro |
| `diagnostics-collaudo-running-dark.png` | Desktop 1440×1000, tema scuro |
| `dashboard-preview.png` | Plancia quotidiana realmente renderizzata |
| `wizard-preview.png` | Benvenuto del vero wizard di configurazione |
| `support-preview.png` | Vero percorso Assistenza |

Desktop 1440×1000. Le immagini non sono mockup, non modificano il DOM e non
sostituiscono i sensori con valori grafici. Nel solo harness l'orologio del
manager viene accelerato e quello del browser allineato, così si esercitano
avvio, worker, timer, stop e scadenza senza attendere un'ora. Le percentuali
esatte dipendono anche dal tempo reale trascorso: non sono numeri imposti alla UI.

## Rigenerazione ripetibile, senza Mitsubishi

Usare una macchina Linux/WSL di sviluppo e un ambiente Python 3.14 separato.
Non installare questo harness su HA domestica. Dipendenze opzionali, esterne al
manifest e all'integrazione:

```bash
python -m venv .tools/frontend-venv
.tools/frontend-venv/bin/python -m pip install -r tools/frontend-demo-requirements.txt
.tools/frontend-venv/bin/python -m playwright install chromium
.tools/frontend-venv/bin/python -m tools.run_frontend_demo --install-requirements
```

HA richiede anche dipendenze native Linux; `pymicro-vad`/`pyspeex-noise` possono
richiedere compilatore e header se non esistono wheel. Seguire le istruzioni
ufficiali dell'ambiente HA e dei [browser Playwright](https://playwright.dev/python/docs/browsers).
Nella verifica presente sono state installate soltanto in `.tools/`, senza
modificare il sistema Ubuntu o il codice di Home Assistant.

Attendere il messaggio `Synthetic HA frontend ready` del server. Poi, in un
secondo terminale, dallo stesso repository/ambiente:

```bash
.tools/frontend-venv/bin/python -m tools.capture_frontend_demo
```

Il server ascolta **solo 127.0.0.1:18123**, crea una directory propria marcata
`.tools/frontend-ha/SYNTHETIC_DEMO_ONLY` e rifiuta directory non demo o un secondo
processo attivo. Intercetta il trasporto prima di ogni rete Mitsubishi, accetta
soltanto le letture note e rifiuta qualunque scrittura. Disabilita la ricerca LAN.
Non usa credenziali reali. Il servizio `frontend_demo.control` esiste soltanto
nel tool di sviluppo, non nell'integrazione distribuita.

La cattura usa il browser locale, blocca risorse esterne, avvia il vero flow,
chiude e riapre il browser, verifica la barra nativa, scadenza, stop e download
HA autenticato. Simula infine un errore del solo storage di collaudo. Il secondo
avvio della cattura richiede **riavvio del server demo**, che ripristina lo store
operativo mantenendo i file sintetici precedenti. Se il token locale scade,
riavviare il server, senza copiare credenziali da altre istanze.

Risultati e download rimangono in `.tools/frontend-ha/`, esclusa da Git. Fermare
con Ctrl+C il solo processo del server alla fine; la chiusura ordinata revoca
il token temporaneo e rimuove `browser-auth.json`/`ready.json`. Non pubblicare
`.storage`, token, database, download o log della demo. Il vecchio generatore
HTML `build_documentation_previews.py` conserva i mockup soltanto in `.tools/`
e non può più sovrascrivere questi screenshot autentici.

## Revisione e riuso

Controllare tutte le immagini: niente email, token, UUID, indirizzi o nomi reali.
Mantenere lingua, viewport, tema e nomi file. README, guida utente, guida collaudo
e note della release usano questi PNG. Non sostituirli con immagini AI o illustrazioni.
Le fixture offline `tools.generate_test_demo` restano utili per test dei reducer,
ma non sono la sorgente delle catture frontend.

Queste prove non sostituiscono test su telefono fisico, browser diversi,
prestazioni sull'hardware target o account Mitsubishi autorizzato.
