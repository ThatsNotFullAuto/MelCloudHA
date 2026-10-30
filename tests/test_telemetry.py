"""Entirely synthetic FTC4–FTC7 facts: no Mitsubishi capture or hardware validation."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.melcloud_diagnostics.coordinator import DiagnosticCoordinator
from custom_components.melcloud_diagnostics.core.capabilities import (
    REGISTRY,
    Capability,
    CapabilityRegistry,
    EvidenceStatus,
)
from custom_components.melcloud_diagnostics.core.cloud import CloudError, CloudReader
from custom_components.melcloud_diagnostics.core.cloud_telemetry import cloud_observations
from custom_components.melcloud_diagnostics.core.control import ConfirmationGate
from custom_components.melcloud_diagnostics.core.journal import Journal
from custom_components.melcloud_diagnostics.core.models import Snapshot
from custom_components.melcloud_diagnostics.core.telemetry import (
    Availability,
    FTCGeneration,
    Observation,
    Source,
    Validation,
    compare,
)
from custom_components.melcloud_diagnostics.diagnostics import async_get_config_entry_diagnostics

from .conftest import NOW, UNIT
from .test_cloud import session_for


def observed(**changes):
    values = dict(
        unit_id=UNIT,
        parameter="FlowTemperature",
        value=0.0,
        unit="°C",
        acquired_at=NOW,
        source=Source.MELCLOUD_HOME,
        availability=Availability.AVAILABLE,
        validation=Validation.STRUCTURAL,
    )
    return Observation(**(values | changes))


def comparison(*items, **changes):
    return compare(
        items,
        **(dict(now=NOW, max_age=timedelta(minutes=3), max_skew=timedelta(seconds=30)) | changes),
    )


@pytest.mark.parametrize("generation", ["FTC4", "FTC5", "FTC6", "FTC7"])
def test_synthetic_generations_do_not_imply_cloud_compatibility(raw_unit, generation):
    raw_unit["ftcModel"] = generation
    facts = cloud_observations(Snapshot.parse(raw_unit, NOW))
    assert all(o.generation == FTCGeneration(generation) for o in facts)
    assert all(o.validation != Validation.VERIFIED_REAL for o in facts)
    assert (
        REGISTRY.lookup(FTCGeneration(generation), Source.MELCLOUD_HOME, "FlowTemperature").status
        == EvidenceStatus.UNKNOWN
    )
    assert (
        REGISTRY.lookup(
            FTCGeneration(generation), Source.ESPHOME, "controller_identification"
        ).status
        == EvidenceStatus.UNKNOWN
    )
    assert (
        REGISTRY.lookup(
            FTCGeneration(generation),
            Source.ESPHOME,
            "controller_identification",
            transport="cn105",
        ).status
        == EvidenceStatus.DOCUMENTED
    )


@pytest.mark.parametrize("name", [None, "ERST20F-VM2E", "7", "FTC7 presumed", "FTC8"])
def test_generation_never_inferred_from_model_or_number(name):
    assert FTCGeneration.from_declared(name) == FTCGeneration.UNKNOWN


def test_capability_restrictions_and_ambiguity():
    entry = Capability(
        generation=FTCGeneration.FTC7,
        source=Source.ESPHOME,
        parameter="example",
        status=EvidenceStatus.DOCUMENTED,
        model="synthetic",
        firmware="example-1",
        adapter="example",
        transport="native_api",
        reference="synthetic test evidence",
    )
    registry = CapabilityRegistry((entry,))
    context = dict(
        model="synthetic", firmware="example-1", adapter="example", transport="native_api"
    )
    assert registry.lookup(entry.generation, entry.source, entry.parameter, **context) == entry
    for key in context:
        assert (
            registry.lookup(
                entry.generation, entry.source, entry.parameter, **(context | {key: "other"})
            ).status
            == EvidenceStatus.UNKNOWN
        )
    assert (
        CapabilityRegistry((entry, replace(entry, status=EvidenceStatus.UNAVAILABLE)))
        .lookup(entry.generation, entry.source, entry.parameter, **context)
        .status
        == EvidenceStatus.UNKNOWN
    )
    with pytest.raises(ValueError):
        replace(entry, reference=None)
    assert (
        REGISTRY.lookup(
            FTCGeneration.FTC5, Source.ESPHOME, "realtime_energy_consumption", transport="cn105"
        ).status
        == EvidenceStatus.UNAVAILABLE
    )
    assert (
        REGISTRY.lookup(
            FTCGeneration.FTC4, Source.ESPHOME, "realtime_energy_consumption", transport="cn105"
        ).status
        == EvidenceStatus.UNKNOWN
    )


def test_zero_missing_and_invalid_values_are_distinct(raw_unit):
    raw_unit["settings"] = [
        {"name": "FlowTemperature", "value": "0"},
        {"name": "ReturnTemperature", "value": "nan"},
        {"name": "SetTemperatureZone1", "value": None},
    ]
    facts = {o.parameter: o for o in cloud_observations(Snapshot.parse(raw_unit, NOW))}
    assert facts["FlowTemperature"].value == 0
    assert facts["FlowTemperature"].availability == Availability.AVAILABLE
    assert facts["ReturnTemperature"].value is None
    assert facts["ReturnTemperature"].validation == Validation.INVALID
    assert facts["SetTemperatureZone1"].availability == Availability.MISSING
    assert facts["RoomTemperatureZone1"].availability == Availability.MISSING
    assert facts["RoomTemperatureZone1"].validation == Validation.UNVERIFIED
    assert all(o.origin_at is None and o.protocol_revision is None for o in facts.values())
    assert not any("sensor_selection" in o.parameter for o in facts.values())


def test_timestamp_normalization_staleness_and_delayed_imports():
    local_time = NOW.astimezone(timezone(timedelta(hours=2)))
    assert observed(acquired_at=local_time).acquired_at == NOW
    with pytest.raises(ValueError):
        observed(acquired_at=datetime(2026, 10, 30))
    with pytest.raises(ValueError):
        observed(origin_at=datetime(2026, 10, 30))
    old = observed(origin_at=NOW - timedelta(days=1), source=Source.SD_EXPORT)
    assert old.at(NOW, timedelta(minutes=3)).availability == Availability.STALE
    assert old.availability == Availability.AVAILABLE  # immutable original
    future = observed(origin_at=NOW + timedelta(seconds=1))
    assert not comparison(future).candidates
    assert (
        observed().at(NOW + timedelta(minutes=3), timedelta(minutes=3)).availability
        == Availability.AVAILABLE
    )
    with pytest.raises(ValueError):
        observed().at(NOW, timedelta(seconds=-1))


@pytest.mark.parametrize("value", [float("inf"), float("nan"), {}, []])
def test_non_scalar_or_nonfinite_facts_rejected(value):
    with pytest.raises(ValueError):
        observed(value=value)


@pytest.mark.parametrize(
    "availability",
    [
        Availability.MISSING,
        Availability.UNSUPPORTED,
        Availability.UNKNOWN,
        Availability.ACQUISITION_ERROR,
    ],
)
def test_unavailable_values_cannot_masquerade_as_measurements(availability):
    with pytest.raises(ValueError):
        observed(availability=availability)
    assert observed(value=None, availability=availability).value is None
    with pytest.raises(ValueError):
        observed(value=None)


def test_comparison_preserves_sources_duplicates_and_conflicting_values():
    cloud = observed()
    local = observed(source=Source.ESPHOME, value=1.0)
    result = comparison(cloud, local, cloud)
    assert result.observations == (cloud, local)
    assert result.candidates == (cloud, local) and result.disagreement is True
    assert comparison(cloud, replace(local, value=0.0)).disagreement is False
    assert comparison(cloud, replace(local, unit="K")).disagreement is None
    assert comparison(cloud, replace(local, value=False)).disagreement is None
    assert (
        comparison(cloud, replace(local, origin_at=NOW - timedelta(minutes=1))).disagreement is None
    )
    assert not comparison(cloud, now=NOW + timedelta(minutes=4)).candidates
    with pytest.raises(ValueError):
        comparison(cloud, replace(local, unit_id="different-unit"))
    with pytest.raises(ValueError):
        comparison(cloud, replace(local, parameter="another-parameter"))


def test_latest_unavailable_source_does_not_resurrect_old_readings():
    old = observed(acquired_at=NOW - timedelta(seconds=10))
    failure = observed(value=None, availability=Availability.ACQUISITION_ERROR)
    local = observed(source=Source.ESPHOME, value=2.0)
    result = comparison(old, local, failure)
    assert result.candidates == (local,)
    assert result.disagreement is None and len(result.observations) == 3
    # Two independent local devices and same-time conflicts are not silently overwritten.
    other = replace(local, source_instance="other", value=3.0)
    assert len(comparison(local, other).candidates) == 2
    assert comparison(local, replace(local, value=3.0)).disagreement is True


def test_comparison_never_deduplicates_false_into_zero_and_validates_empty_input():
    zero = observed(value=0.0)
    false = observed(value=False)
    result = comparison(zero, false)
    assert len(result.observations) == 2 and result.disagreement is None
    with pytest.raises(ValueError):
        comparison(max_age=timedelta(seconds=-1))
    with pytest.raises(ValueError):
        comparison(now=datetime(2026, 10, 30))


async def test_cloud_poll_populates_normalized_view_without_new_requests(raw_unit, tmp_path):
    reader = AsyncMock(spec=CloudReader)
    reader.discover.return_value = {UNIT: Snapshot.parse(raw_unit, NOW)}
    reader.history.return_value = []
    coordinator = DiagnosticCoordinator(
        HomeAssistant(str(tmp_path)), None, reader, AsyncMock(), Journal()
    )
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.telemetry[UNIT] == cloud_observations(coordinator.data[UNIT])
    reader.discover.assert_awaited_once()
    reader.history.assert_awaited_once_with(UNIT)
    reader.read_unit.assert_not_awaited()
    assert not hasattr(reader, "write")
    previous = coordinator.telemetry.copy()
    reader.discover.side_effect = CloudError("synthetic transport failure")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.telemetry == previous
    assert coordinator.last_poll_error["type"] == "CloudError"


async def test_real_reader_and_new_adapter_only_use_existing_get(raw_unit, auth):
    session = session_for({"buildings": [{"airToWaterUnits": [raw_unit]}]})
    snapshots = await CloudReader(session, auth).discover(NOW)
    facts = cloud_observations(snapshots[UNIT])
    assert facts
    assert len(session.request.call_args_list) == 1
    assert session.request.call_args.args == ("GET", "https://mobile.bff.melcloudhome.com/context")
    assert session.request.call_args.kwargs["json"] is None


async def test_normalized_report_redacts_identity_and_marks_old_data(raw_unit):
    journal = Journal()
    snapshot = Snapshot.parse(raw_unit, NOW - timedelta(days=365))
    journal.observe(snapshot)
    runtime = SimpleNamespace(
        journal=journal, data={UNIT: snapshot}, history_status={}, gate=ConfirmationGate(None)
    )
    result = await async_get_config_entry_diagnostics(None, SimpleNamespace(runtime_data=runtime))
    assert UNIT not in json.dumps(result) and "Synthetic Ecodan" not in json.dumps(result)
    facts = result["units"]["unit_1"]["normalized_telemetry"]
    assert all(o["availability"] != "available" for o in facts)
    assert all(o["origin_at"] is None for o in facts)


def test_adapter_cannot_normalize_an_unrelated_source(raw_unit):
    with pytest.raises(ValueError):
        cloud_observations(replace(Snapshot.parse(raw_unit, NOW), source="esphome"))


def test_journal_nulls_neither_change_settings_nor_duplicate_p1_after_restore(raw_unit):
    journal = Journal()
    raw_unit["isInError"] = True
    raw_unit["settings"] = [
        {"name": "ErrorCode", "value": "P1"},
        {"name": "OperationModeZone1", "value": "HeatCurve"},
    ]
    assert len(journal.observe(Snapshot.parse(raw_unit, NOW))) == 1
    raw_unit["isInError"] = None
    raw_unit["settings"][1]["value"] = None
    assert journal.observe(Snapshot.parse(raw_unit, NOW + timedelta(seconds=60))) == []
    # Exact storage-v1 JSON round trip, including retained faults/observations.
    saved = json.loads(json.dumps(journal.data))
    restored = Journal(saved)
    raw_unit["isInError"] = True
    raw_unit["settings"][1]["value"] = "HeatCurve"
    assert restored.observe(Snapshot.parse(raw_unit, NOW + timedelta(seconds=120))) == []
    raw_unit["settings"][1]["value"] = "HeatFlowTemperature"
    events = restored.observe(Snapshot.parse(raw_unit, NOW + timedelta(seconds=180)))
    assert len(events) == 1 and events[0]["old"] == "HeatCurve"
    assert events[0]["source"] == "melcloud_home"
    raw_unit["settings"] = []
    assert restored.observe(Snapshot.parse(raw_unit, NOW+timedelta(seconds=240))) == []
