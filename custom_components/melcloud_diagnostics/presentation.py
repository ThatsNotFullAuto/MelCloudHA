"""Human-facing labels; protocol identifiers remain internal."""

FIELD_LABELS = {
    "it": {
        "SetTankWaterTemperature": "Temperatura desiderata dell'acqua sanitaria",
        "SetTemperatureZone1": "Temperatura ambiente desiderata — Zona 1",
        "SetTemperatureZone2": "Temperatura ambiente desiderata — Zona 2",
    },
    "en": {
        "SetTankWaterTemperature": "Desired domestic hot water temperature",
        "SetTemperatureZone1": "Desired room temperature — Zone 1",
        "SetTemperatureZone2": "Desired room temperature — Zone 2",
    },
}

OUTCOMES = {
    "it": {
        "observed_requested_value": "Mitsubishi ora riporta la temperatura richiesta. Può servire tempo perché l'acqua o la stanza la raggiungano.",
        "accepted_unverified": "Mitsubishi ha ricevuto la richiesta, ma il nuovo valore non è ancora visibile. Controlla l'app MELCloud Home o il display prima di riprovare.",
    },
    "en": {
        "observed_requested_value": "Mitsubishi now reports the requested setting. The water or room may take time to reach this temperature.",
        "accepted_unverified": "Mitsubishi accepted the request, but the new setting is not yet visible. Check MELCloud Home or the controller before trying again.",
    },
}


def field_label(field, language="it"):
    return FIELD_LABELS.get(language, FIELD_LABELS["en"])[field]


def outcome_message(outcome, language="it"):
    return OUTCOMES.get(language, OUTCOMES["en"])[outcome]
