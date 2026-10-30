# MELCloud Diagnostics

<img src="custom_components/melcloud_diagnostics/brand/icon.png" alt="Casa azzurra con tre diamanti rossi e segnale diagnostico" width="112">

Diagnostica per Mitsubishi Ecodan in Home Assistant, tramite **MELCloud Home**.
Parte in **sola lettura**. Non richiede hardware aggiuntivo.

**Versione 0.2.0 ? prima pubblicazione, da validare sull?impianto reale.**
Testata con HA Core **2026.10.4**, ultima stabile verificata al 30 ottobre 2026.

## Inizia da qui

- [Installazione HACS e prima configurazione guidata](docs/GUIDA_UTENTE.md).
- [Plancia Ecodan: stato, temperature e guasti](docs/GUIDA_UTENTE.md#la-plancia-ecodan).
- [Aggiornamenti, changelog e conservazione dei dati](docs/AGGIORNAMENTI.md).
- [Changelog](CHANGELOG.md) e [release scaricabili](https://github.com/ThatsNotFullAuto/MelCloudHA/releases).
- [Limiti e dettagli tecnici](docs/DETTAGLI_TECNICI.md).

## Installa da HACS

In **HACS ? menu ? ? Repository personalizzate**, aggiungi:

```text
https://github.com/ThatsNotFullAuto/MelCloudHA
```

Scegli categoria **Integrazione**, scarica **MELCloud Diagnostics** e riavvia
Home Assistant quando richiesto. Poi apri **Impostazioni ? Dispositivi e
servizi ? Aggiungi integrazione ? MELCloud Diagnostics**.

Il wizard cerca account MELCloud Home gi? presenti in HA, propone il loro
riuso, cerca eventuali candidati locali ESPHome/Asgard e ti fa scegliere le
pompe associate all?account Mitsubishi. Non devi conoscere l?indirizzo IP.
I candidati in rete non sono identificazioni certe della MAC-597IF-E.

## Cosa ottieni

Temperature e impostazioni osservabili, stato operativo, codice guasto,
storico errori quando disponibile, ricorrenze P1, report esportabili e una
plancia nativa adatta a telefono e computer, senza schede aggiuntive.

Le modifiche sono **opzionali e manuali**: permesso separato, riepilogo prima/dopo,
**due conferme**, scadenza e ricontrollo dei valori. Nessun comando dalla plancia,
nessun reset e nessun reinvio automatico dopo un timeout. La mandata resta
esclusa dalle scritture nella prima versione.

## Aggiornamenti

Le release numerate su GitHub alimentano gli aggiornamenti HACS, con changelog
e indicazione del riavvio. Aggiorna l?installazione esistente: non eliminarla e
ricrearla. Entit?, credenziali e storico hanno identificativi/formati stabili;
le plance esistenti non vengono sovrascritte. Vedi la [procedura completa](docs/AGGIORNAMENTI.md).

## Progetto indipendente

Non ? un?integrazione ufficiale Mitsubishi o Home Assistant. L?icona ? un
emblema originale: casa azzurra, richiamo ai tre diamanti e segnale diagnostico;
non riutilizza il logo ufficiale Home Assistant.
Non sono inclusi APK, codice proprietario decompilato, credenziali o dati di un impianto reale.

I test usano risposte sintetiche: disponibilit? dei dati e comportamento con
l?account reale vanno ancora verificati. Leggere P1 non ne dimostra la causa.
