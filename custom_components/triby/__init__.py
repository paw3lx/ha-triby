"""Invoxia Triby: send doodles/notifications to a Triby through the Invoxia cloud."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import TribyAuthError, TribyClient, TribyError
from .const import CONF_SENDER_ID, CONF_TRIBY_ID, DOMAIN
from .render import build_png

PLATFORMS = [Platform.NOTIFY]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class TribyData:
    client: TribyClient
    sender_id: int
    triby_id: int


type TribyConfigEntry = ConfigEntry[TribyData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # Legacy notify service `notify.triby` ("Send a notification via triby"),
    # alongside the notify entity created per config entry.
    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.NOTIFY, DOMAIN, {CONF_NAME: DOMAIN}, config)
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TribyConfigEntry) -> bool:
    client = TribyClient(
        async_get_clientsession(hass), entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )
    try:
        await client.profiles()
    except TribyAuthError as err:
        raise ConfigEntryAuthFailed("Invalid Triby credentials") from err
    except TribyError as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = TribyData(client, entry.data[CONF_SENDER_ID], entry.data[CONF_TRIBY_ID])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TribyConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_send(
    hass: HomeAssistant,
    data: TribyData,
    message: str | None,
    title: str | None = None,
    image: bytes | None = None,
) -> None:
    """Render and publish one doodle."""
    png = await hass.async_add_executor_job(build_png, message, title, image)
    try:
        await data.client.send_png(png, data.sender_id, data.triby_id)
    except TribyError as err:
        raise HomeAssistantError(f"Sending to Triby failed: {err}") from err
