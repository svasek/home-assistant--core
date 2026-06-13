"""NeoPool integration for Home Assistant."""

import logging

from neopool_modbus import NeoPoolModbusClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, REMOVED_ENTITY_KEYS
from .coordinator import NeoPoolCoordinator
from .services import async_setup_services

type NeoPoolConfigEntry = ConfigEntry[NeoPoolCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


def _cleanup_removed_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove orphaned entity-registry entries for entities no longer in definitions."""
    registry = er.async_get(hass)
    # Match both old ({entry_id}_{key}) and new ({unique_id}_{key}) unique_id formats
    prefixes = {entry.entry_id}
    if entry.unique_id:
        prefixes.add(entry.unique_id)
    removed_uids = {
        f"{prefix}_{key}" for prefix in prefixes for key in REMOVED_ENTITY_KEYS
    }
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity_entry.unique_id in removed_uids:
            _LOGGER.debug(
                "Removing orphaned entity %s (unique_id=%s)",
                entity_entry.entity_id,
                entity_entry.unique_id,
            )
            registry.async_remove(entity_entry.entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NeoPool integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Set up the NeoPool integration from a config entry."""
    # Initialize Modbus client and coordinator
    client = NeoPoolModbusClient(entry.data)
    coordinator = NeoPoolCoordinator(hass, client, entry, entry.entry_id)

    # Wait for the first update from the coordinator
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator as runtime_data for easy access
    entry.runtime_data = coordinator

    # Remove orphaned entity-registry entries for sensors that no longer exist
    _cleanup_removed_entities(hass, entry)

    # Forward entities setup to Home Assistant
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Unload a NeoPool config entry."""
    coordinator = entry.runtime_data
    coordinator.cancel_follow_up_refresh()
    if coordinator.client is not None:
        await coordinator.client.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
