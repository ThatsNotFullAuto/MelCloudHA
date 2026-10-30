"""Native Lovelace dashboard using actual entity registry IDs, no control cards."""

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


def build_dashboard(units, entity_ids, test_entity_ids=None):
    """Build only cards with resolved IDs; never guess slugified entity names."""
    views = []
    for index, (identifier, name) in enumerate(units.items(), 1):
        entities = entity_ids.get(identifier, {})

        def tile(key, title, icon, color):
            return {
                "type": "tile",
                "entity": entities[key],
                "name": title,
                "icon": icon,
                "color": color,
                "tap_action": {"action": "more-info"},
                "icon_tap_action": {"action": "more-info"},
            }

        def section(title, icon, items):
            cards = [{"type": "heading", "heading": title, "icon": icon}]
            cards.extend(tile(*item) for item in items if item[0] in entities)
            return {"type": "grid", "cards": cards}

        sections = [
            section(
                "A colpo d'occhio",
                "mdi:heat-pump",
                [
                    ("error", "Errore macchina", "mdi:alert-circle-outline", "red"),
                    ("connected", "Collegamento Mitsubishi", "mdi:cloud-check-outline", "teal"),
                    ("operation_mode", "Cosa sta facendo", "mdi:heat-pump", "orange"),
                    ("last_update", "Ultima lettura", "mdi:update", "blue"),
                ],
            ),
            section(
                "Acqua calda sanitaria",
                "mdi:water-boiler",
                [
                    ("TankWaterTemperature", "Temperatura acqua", "mdi:thermometer", "orange"),
                    (
                        "SetTankWaterTemperature",
                        "Temperatura desiderata",
                        "mdi:thermometer-check",
                        "amber",
                    ),
                    (
                        "ForcedHotWaterMode",
                        "Riscaldamento forzato ACS",
                        "mdi:water-boiler",
                        "orange",
                    ),
                ],
            ),
            section(
                "Riscaldamento e raffrescamento",
                "mdi:home-thermometer-outline",
                [
                    (
                        "RoomTemperatureZone1",
                        "Zona 1 · ambiente",
                        "mdi:home-thermometer-outline",
                        "teal",
                    ),
                    ("SetTemperatureZone1", "Zona 1 · impostazione", "mdi:thermometer", "blue"),
                    ("zone1_mode", "Zona 1 · regolazione", "mdi:radiator", "orange"),
                    (
                        "RoomTemperatureZone2",
                        "Zona 2 · ambiente",
                        "mdi:home-thermometer-outline",
                        "teal",
                    ),
                    ("SetTemperatureZone2", "Zona 2 · impostazione", "mdi:thermometer", "blue"),
                    ("zone2_mode", "Zona 2 · regolazione", "mdi:radiator", "orange"),
                ],
            ),
        ]
        graph_entities = [
            {"entity": entities[k], "name": label}
            for k, label in [
                ("TankWaterTemperature", "Acqua sanitaria"),
                ("RoomTemperatureZone1", "Ambiente Zona 1"),
                ("RoomTemperatureZone2", "Ambiente Zona 2"),
            ]
            if k in entities
        ]
        if graph_entities:
            sections.append(
                {
                    "type": "grid",
                    "cards": [
                        {
                            "type": "heading",
                            "heading": "Temperature · ultime 24 ore",
                            "icon": "mdi:chart-line",
                        },
                        {
                            "type": "history-graph",
                            "entities": graph_entities,
                            "hours_to_show": 24,
                            "grid_options": {"columns": "full"},
                        },
                    ],
                }
            )
        sections.append(
            section(
                "Guasti e storico",
                "mdi:clipboard-pulse-outline",
                [
                    ("error_code", "Codice attuale", "mdi:alert-outline", "red"),
                    ("last_error", "Ultimo guasto registrato", "mdi:history", "amber"),
                    ("last_error_at", "Quando è comparso", "mdi:calendar-clock", "amber"),
                    ("last_error_cleared", "Quando è cessato", "mdi:calendar-check", "teal"),
                    ("p1_30d", "P1 conosciuti · 30 giorni", "mdi:counter", "amber"),
                    ("history_status", "Disponibilità storico", "mdi:database-outline", "blue"),
                ],
            )
        )
        sections.append(
            section(
                "Diagnostica del collegamento",
                "mdi:lan-connect",
                [
                    ("rssi", "Segnale Wi-Fi", "mdi:wifi", "blue"),
                    ("ftc_model", "Controller dichiarato", "mdi:chip", "blue"),
                    (
                        "control_enabled",
                        "Modifiche manuali abilitate",
                        "mdi:shield-lock-outline",
                        "amber",
                    ),
                ],
            )
        )
        sections.append(
            {
                "type": "grid",
                "cards": [
                    {
                        "type": "markdown",
                        "content": "**Come leggere questa plancia**\n\nI dati arrivano dal cloud Mitsubishi e possono essere ritardati. "
                        "Un valore **sconosciuto** o **non disponibile** non significa automaticamente un guasto. "
                        "Il setpoint di zona va letto insieme al metodo di regolazione: può riferirsi all'acqua, non alla stanza. "
                        "Le icone aprono solo i dettagli; le modifiche richiedono il percorso guidato dell'integrazione.",
                    }
                ],
            }
        )
        if "error" in entities:
            sections.insert(
                0,
                {
                    "type": "grid",
                    "cards": [
                        {
                            "type": "conditional",
                            "conditions": [{"entity": entities["error"], "state": "on"}],
                            "card": {
                                "type": "markdown",
                                "content": "## Errore segnalato\nControlla il codice nella sezione **Guasti e storico**. "
                                "Conserva il report diagnostico. Questa plancia non esegue reset.",
                            },
                        }
                    ],
                },
            )
        views.append(
            {
                "title": name,
                "path": f"pompa-{index}",
                "icon": "mdi:heat-pump",
                "type": "sections",
                "max_columns": 3,
                "sections": sections,
            }
        )
    if test_entity_ids:
        cards = [
            {
                "type": "heading",
                "heading": "Collaudo diagnostico",
                "icon": "mdi:clipboard-pulse-outline",
            }
        ]
        result_cards = [
            {
                "type": "heading",
                "heading": "Qualità e rapporto",
                "icon": "mdi:clipboard-check-outline",
            }
        ]
        for key, label in [
            ("test_status", "Stato della sessione"),
            ("test_progress", "Avanzamento temporale"),
            ("test_duration", "Durata prevista"),
            ("test_elapsed", "Trascorso"),
            ("test_remaining", "Residuo"),
            ("test_end", "Fine prevista"),
            ("test_success", "Letture riuscite"),
            ("test_failed", "Letture fallite"),
            ("test_last_acquisition", "Ultima lettura"),
            ("test_history", "Storico errori"),
            ("test_cloud", "Cloud"),
            ("test_storage", "Persistenza"),
            ("test_quality", "Qualità della raccolta"),
            ("test_stop", "Interrompi collaudo"),
            ("test_dropped", "Letture perse"),
            ("test_reason", "Motivo di arresto"),
            ("test_checks_passed", "Controlli PASS"),
            ("test_checks_failed", "Controlli FAIL"),
            ("test_checks_unknown", "Controlli non verificabili"),
        ]:
            if key not in test_entity_ids:
                continue
            card = {
                "type": "tile",
                "entity": test_entity_ids[key],
                "name": label,
                "tap_action": {"action": "more-info"},
                "icon_tap_action": {"action": "more-info"},
            }
            if key == "test_progress":
                card["features"] = [{"type": "bar-gauge", "min": 0, "max": 100}]
            if key == "test_stop":
                card["hide_state"] = True
                card["features"] = [{"type": "button", "action_name": "Interrompi collaudo"}]
            if key in (
                "test_status",
                "test_progress",
                "test_last_acquisition",
                "test_quality",
                "test_stop",
                "test_reason",
                "test_checks_unknown",
            ):
                card["grid_options"] = {"columns": 12}
            (
                cards
                if key
                in (
                    "test_status",
                    "test_progress",
                    "test_duration",
                    "test_elapsed",
                    "test_remaining",
                    "test_end",
                    "test_success",
                    "test_failed",
                    "test_last_acquisition",
                )
                else result_cards
            ).append(card)
        result_cards.append(
            {
                "type": "markdown",
                "content": "Per avviare: **Dispositivi e servizi → MELCloud Diagnostics → Configura → Diagnostica → Collaudo diagnostico**. "
                "La raccolta continua chiudendo il browser. Il pulsante interrompe solo il collaudo, senza comandi alla pompa. "
                "Il 100% indica il tempo trascorso, non la salute dell'impianto. Alla fine usa **Scarica la diagnostica** nel menu dell'integrazione.",
            }
        )
        views.append(
            {
                "title": "Diagnostica",
                "path": "diagnostica",
                "icon": "mdi:clipboard-pulse-outline",
                "type": "sections",
                "max_columns": 2,
                "sections": [
                    {"type": "grid", "cards": cards},
                    {"type": "grid", "cards": result_cards},
                ],
            }
        )
    return {"title": "Ecodan · Diagnostica", "views": views}


def dashboard_for_entry(hass, entry):
    registry = er.async_get(hass)
    units = {k: snapshot.name for k, snapshot in entry.runtime_data.data.items()}
    resolved = {identifier: {} for identifier in units}
    test_resolved = {}
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform != DOMAIN or entity.disabled_by is not None:
            continue
        if entity.unique_id.startswith(f"{entry.entry_id}_test_"):
            test_resolved[entity.unique_id.removeprefix(f"{entry.entry_id}_")] = entity.entity_id
        for identifier in units:
            prefix = f"{identifier}_"
            if entity.unique_id.startswith(prefix):
                resolved[identifier][entity.unique_id.removeprefix(prefix)] = entity.entity_id
    if not any(resolved.values()) and not test_resolved:
        return None
    return build_dashboard(units, resolved, test_resolved)
