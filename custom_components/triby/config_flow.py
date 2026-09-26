"""Config flow for Invoxia Triby."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from .api import TribyAuthError, TribyClient, TribyError
from .const import CONF_SENDER_ID, CONF_TRIBY_ID, DOMAIN

USER_SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})


class TribyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Log in with the Triby app account and pick the Triby to notify."""

    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict[str, str] = {}
        self._sender_id: int = 0
        self._tribys: list[dict[str, Any]] = []

    async def _fetch_profiles(self, email: str, password: str) -> list[dict[str, Any]]:
        return await TribyClient(async_get_clientsession(self.hass), email, password).profiles()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                profiles = await self._fetch_profiles(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            except TribyAuthError:
                errors["base"] = "invalid_auth"
            except TribyError:
                errors["base"] = "cannot_connect"
            else:
                senders = [p for p in profiles if p.get("type") != "triby"]
                self._tribys = [p for p in profiles if p.get("type") == "triby"]
                if not senders or not self._tribys:
                    errors["base"] = "no_triby"
                else:
                    self._creds = user_input
                    self._sender_id = senders[0]["id"]
                    if len(self._tribys) == 1:
                        return await self._create(self._tribys[0])
                    return await self.async_step_pick()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            triby = next(t for t in self._tribys if str(t["id"]) == user_input[CONF_TRIBY_ID])
            return await self._create(triby)
        options = [SelectOptionDict(value=str(t["id"]), label=t["name"]) for t in self._tribys]
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {vol.Required(CONF_TRIBY_ID): SelectSelector(SelectSelectorConfig(options=options))}
            ),
        )

    async def _create(self, triby: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(str(triby["id"]))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=triby.get("sip_displayname") or "Triby",
            data={**self._creds, CONF_SENDER_ID: self._sender_id, CONF_TRIBY_ID: triby["id"]},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._fetch_profiles(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            except TribyAuthError:
                errors["base"] = "invalid_auth"
            except TribyError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )
