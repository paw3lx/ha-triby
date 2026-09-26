"""Tests for the Triby integration (Invoxia cloud mocked)."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.triby.api import TribyAuthError
from custom_components.triby.const import CONF_SENDER_ID, CONF_TRIBY_ID, DOMAIN

PROFILES = [
    {"id": 42371, "name": "Pawel", "type": "iphone", "sip_displayname": "Pawel"},
    {"id": 42372, "name": "triby_18B79E0350B0", "type": "triby", "sip_displayname": "Triby"},
]
CREDS = {CONF_EMAIL: "me@example.com", CONF_PASSWORD: "pw"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def client():
    with (
        patch("custom_components.triby.api.TribyClient.profiles", AsyncMock(return_value=PROFILES)) as prof,
        patch("custom_components.triby.api.TribyClient.send_png", AsyncMock(return_value=1)) as send,
    ):
        yield prof, send


async def test_config_flow(hass: HomeAssistant, client) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.triby.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Triby"
    assert result["data"] == {**CREDS, CONF_SENDER_ID: 42371, CONF_TRIBY_ID: 42372}
    assert result["result"].unique_id == "42372"


async def test_config_flow_invalid_auth(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch("custom_components.triby.api.TribyClient.profiles", AsyncMock(side_effect=TribyAuthError)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="Triby", unique_id="42372",
        data={**CREDS, CONF_SENDER_ID: 42371, CONF_TRIBY_ID: 42372},
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return entry


async def test_legacy_service(hass: HomeAssistant, client) -> None:
    _, send = client
    await _setup(hass)
    assert hass.services.has_service("notify", "triby")
    await hass.services.async_call("notify", "triby", {"message": "Hello", "title": "Hi"}, blocking=True)
    png, sender, triby = send.call_args.args
    assert (sender, triby) == (42371, 42372)
    assert png.startswith(b"\x89PNG")


async def test_notify_entity(hass: HomeAssistant, client) -> None:
    _, send = client
    await _setup(hass)
    assert hass.states.get("notify.triby") is not None
    await hass.services.async_call(
        "notify", "send_message", {"entity_id": "notify.triby", "message": "Dinner"}, blocking=True
    )
    assert send.call_args.args[1:] == (42371, 42372)


def test_render() -> None:
    from PIL import Image
    import io
    from custom_components.triby.render import build_png

    for png in (
        build_png("A fairly long message that has to wrap onto several lines", "Title"),
        build_png(None, image=_png(Image.new("RGB", (800, 600), "gray"))),
    ):
        img = Image.open(io.BytesIO(png))
        assert img.size == (296, 128)


def _png(img) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
