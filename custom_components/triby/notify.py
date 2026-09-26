"""Notify platform for Invoxia Triby.

Provides both:
- a notify entity per Triby (`notify.triby`, used with the `notify.send_message` action), and
- the legacy service `notify.triby` ("Send a notification via triby"), which also accepts
  `data: {image: /config/www/picture.png | https://...}` to send an image instead of text.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TribyConfigEntry, async_send
from .const import ATTR_IMAGE, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TribyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([TribyNotifyEntity(entry)])


class TribyNotifyEntity(NotifyEntity):
    """The Triby as a notify entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: TribyConfigEntry) -> None:
        self._entry = entry
        triby_id = entry.runtime_data.triby_id
        self._attr_unique_id = f"{triby_id}_notify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(triby_id))},
            name=entry.title,
            manufacturer="Invoxia",
            model="Triby",
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await async_send(self.hass, self._entry.runtime_data, message, title)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TribyNotificationService:
    return TribyNotificationService()


class TribyNotificationService(BaseNotificationService):
    """Legacy `notify.triby` service; sends to every configured Triby (or `target` titles/ids)."""

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        entries: list[TribyConfigEntry] = [
            e
            for e in self.hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]
        if targets := kwargs.get(ATTR_TARGET):
            wanted = {str(t).lower() for t in targets}
            entries = [
                e
                for e in entries
                if e.title.lower() in wanted or str(e.runtime_data.triby_id) in wanted
            ]
        if not entries:
            raise ServiceValidationError("No matching Triby is configured and loaded")

        data = kwargs.get(ATTR_DATA) or {}
        image = await self._load_image(data[ATTR_IMAGE]) if data.get(ATTR_IMAGE) else None
        for entry in entries:
            await async_send(self.hass, entry.runtime_data, message, kwargs.get(ATTR_TITLE), image)

    async def _load_image(self, src: str) -> bytes:
        if src.startswith(("http://", "https://")):
            async with async_get_clientsession(self.hass).get(src) as resp:
                if resp.status >= 400:
                    raise HomeAssistantError(f"Could not download image {src}: HTTP {resp.status}")
                return await resp.read()
        if not self.hass.config.is_allowed_path(src):
            raise ServiceValidationError(
                f"{src} is not in allowlist_external_dirs (put it under /config/www or /media)"
            )

        def _read() -> bytes:
            with open(src, "rb") as f:
                return f.read()

        try:
            return await self.hass.async_add_executor_job(_read)
        except OSError as err:
            raise HomeAssistantError(f"Could not read image {src}: {err}") from err
