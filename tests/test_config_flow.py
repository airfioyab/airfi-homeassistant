"""Tests for the Airfi config and options flows."""

import asyncio
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airfi.const import (
    CONF_DEVICE_TYPE,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    DOMAIN,
)
from custom_components.airfi.discovery import DiscoveredDevice

DEVICE = DiscoveredDevice(
    ip="192.168.1.50", udp_port=4000, serial=12345678, protocol_version=1, device_type=1
)


async def _discover_soon() -> list[DiscoveredDevice]:
    """Stand in for async_discover_devices that actually yields control.

    hass.async_create_task starts tasks eagerly, so a plain AsyncMock (whose
    coroutine never suspends) would finish before the first `done()` check in
    async_step_discover, skipping the SHOW_PROGRESS step entirely. A real
    discovery listener always awaits a socket operation before completing, so
    it never hits that edge case; this one-tick yield reproduces that.
    """
    await asyncio.sleep(0)
    return [DEVICE]


async def test_discovery_flow_creates_entry(
    hass: HomeAssistant, mock_modbus_client: AsyncMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.MENU

    with patch(
        "custom_components.airfi.config_flow.async_discover_devices",
        AsyncMock(side_effect=_discover_soon),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
        # Progress step: drive it to completion.
        while result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"]
            )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "12345678"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Model 60 L 12345678"
    assert result["data"] == {
        "host": "192.168.1.50",
        "port": 502,
        CONF_SERIAL: 12345678,
        CONF_DEVICE_TYPE: 1,
    }
    assert result["result"].unique_id == "12345678"


async def test_discovery_excludes_configured_serials(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="12345678", data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "custom_components.airfi.config_flow.async_discover_devices",
        AsyncMock(side_effect=_discover_soon),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
        while result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"]
            )
    # Only device already configured → falls through to manual entry.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_discovery_excludes_configured_hosts(hass: HomeAssistant) -> None:
    # Same host as DEVICE, but a different serial (e.g. a manual entry that
    # was never upgraded): the device must still be excluded, by host.
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.50:502",
        data={"host": "192.168.1.50", "port": 502},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "custom_components.airfi.config_flow.async_discover_devices",
        AsyncMock(side_effect=_discover_soon),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
        while result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"]
            )
    # Only device's host already configured → falls through to manual entry.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_manual_flow_aborts_on_configured_host(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345678",
        data={"host": "10.0.0.9", "port": 502},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "10.0.0.9", "port": 502}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_flow_same_host_different_port_not_aborted(
    hass: HomeAssistant, mock_modbus_client: AsyncMock
) -> None:
    # Two simulators on the same host at different ports are distinct
    # devices; the duplicate guard must key on (host, port), not host alone.
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="10.0.0.9:5020",
        data={"host": "10.0.0.9", "port": 5020},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "custom_components.airfi.config_flow.AirfiModbusClient", autospec=True
    ) as client_cls:
        client_cls.return_value.read_input_register = AsyncMock(return_value=1)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.0.9", "port": 5021}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": "10.0.0.9", "port": 5021}


async def test_manual_flow(
    hass: HomeAssistant, mock_modbus_client: AsyncMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["step_id"] == "manual"

    with patch(
        "custom_components.airfi.config_flow.AirfiModbusClient", autospec=True
    ) as client_cls:
        client_cls.return_value.read_input_register = AsyncMock(return_value=1)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.0.9", "port": 502}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airfi 10.0.0.9"
    assert result["data"] == {"host": "10.0.0.9", "port": 502}
    assert result["result"].unique_id == "10.0.0.9:502"


async def test_manual_flow_cannot_connect(hass: HomeAssistant) -> None:
    from custom_components.airfi.modbus import AirfiConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "custom_components.airfi.config_flow.AirfiModbusClient", autospec=True
    ) as client_cls:
        client_cls.return_value.read_input_register = AsyncMock(
            side_effect=AirfiConnectionError("nope")
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.0.9", "port": 502}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_modbus_client: AsyncMock,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_SCAN_INTERVAL] == 60
