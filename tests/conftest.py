"""Synthetic fixtures. No customer data or network access."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from custom_components.melcloud_diagnostics.core.models import Snapshot

UNIT = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 10, 30, 12, tzinfo=UTC)


@pytest.fixture
def raw_unit():
    return {
        "id": UNIT,
        "givenDisplayName": "Synthetic Ecodan",
        "isConnected": True,
        "isInError": False,
        "rssi": -60,
        "ftcModel": "FTC7",
        "capabilities": {
            "hasHotWater": True,
            "hasZone2": False,
            "hasHalfDegrees": True,
            "minSetTankTemperature": 30,
            "maxSetTankTemperature": 60,
            "minSetTemperature": 10,
            "maxSetTemperature": 30,
        },
        "settings": [
            {"name": k, "value": v}
            for k, v in {
                "Power": "True",
                "ErrorCode": "",
                "OperationMode": "Heating",
                "OperationModeZone1": "HeatRoomTemperature",
                "RoomTemperatureZone1": "22.5",
                "SetTemperatureZone1": "21",
                "SetTankWaterTemperature": "45",
                "TankWaterTemperature": "42",
                "ProhibitHotWater": "False",
            }.items()
        ],
    }


class MemorySource:
    def __init__(self, raw):
        self.raw = deepcopy(raw)
        self.writes = []

    async def read_unit(self, identifier, now):
        return Snapshot.parse(self.raw, now)

    def set(self, key, value):
        for item in self.raw["settings"]:
            if item["name"] == key:
                item["value"] = value
                return
        self.raw["settings"].append({"name": key, "value": value})

    async def write(self, identifier, field, value, *, authorize):
        authorize()
        self.writes.append((identifier, field, value))
        self.set(field, value)


@pytest.fixture
def source(raw_unit):
    return MemorySource(raw_unit)


@pytest.fixture
def auth():
    return AsyncMock(async_get_access_token=AsyncMock(return_value="synthetic-token"))
