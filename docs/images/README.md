# Anteprime della documentazione

Queste immagini sono **anteprime illustrative**, non screenshot di un
impianto installato. Contengono soltanto dati dimostrativi. La plancia reale
usa le schede native HA e può apparire diversamente secondo versione e tema.

- `dashboard-preview.png`: organizzazione delle informazioni diagnostiche.
- `wizard-preview.png`: percorso di configurazione e riuso di un account.
- `support-preview.png`: percorso Assistenza e scaricamento del JSON.

Sono renderizzate da HTML locale con `tools/build_documentation_previews.py`.
Il sorgente rimane nel repository; non sono necessarie per eseguire
l’integrazione e non richiedono alcuna connessione a Mitsubishi.

Per rigenerarle, chi sviluppa può usare Python e Chrome/Chromium già installato:

```text
python tools/build_documentation_previews.py --render
```

Il programma non installa il browser. I file HTML temporanei e il profilo
headless sono conservati in `.tools/`, esclusa da Git.
