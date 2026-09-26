"""Client for the Invoxia cloud API used by the Triby app (reverse-engineered)."""

from __future__ import annotations

import base64
import uuid
from typing import Any

import aiohttp

API_URL = "https://ws.invoxia.io"

# ws.invoxia.io uses a private "invoxia CA" with 2015-era crypto (RSA-1024 leaf,
# SHA-1 CA) that modern OpenSSL rejects. Instead of lowering security levels we
# pin the exact server certificate (valid until 2045).
CERT_SHA256 = "f17a211550b06100772dec6aa643ead08804bd6d8ddcab38900a57e1dc03f69b"
_SSL = aiohttp.Fingerprint(bytes.fromhex(CERT_SHA256))

WIDTH, HEIGHT = 296, 128  # Triby e-ink canvas


class TribyError(Exception):
    """Generic Triby cloud error."""


class TribyAuthError(TribyError):
    """Invalid credentials."""


class TribyClient:
    """Minimal async client: list profiles and publish PNG doodles."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._auth = aiohttp.BasicAuth(email, password)

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.request(
                method,
                API_URL + path,
                json=body,
                auth=self._auth,
                ssl=_SSL,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise TribyAuthError(await resp.text())
                if resp.status >= 400:
                    raise TribyError(f"{method} {path} -> {resp.status}: {(await resp.text())[:300]}")
                if "json" in resp.headers.get("content-type", ""):
                    return await resp.json()
                return await resp.text()
        except aiohttp.ServerFingerprintMismatch as err:
            raise TribyError("ws.invoxia.io certificate changed; pinned fingerprint no longer matches") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TribyError(f"{method} {path} failed: {err}") from err

    async def profiles(self) -> list[dict[str, Any]]:
        """Return all profiles of the account (the app user and each Triby)."""
        return await self._request("GET", "/profiles/")

    async def send_png(self, png: bytes, sender_id: int, triby_id: int) -> int:
        """Publish a 296x128 PNG from the sender profile to the Triby profile."""
        doodle_uuid = str(uuid.uuid4()).upper()
        box = await self._request(
            "POST",
            f"/profiles/{sender_id}/doodlebox/",
            {"uuid": doodle_uuid, "profile_id": triby_id, "all_smart_devices": 1},
        )
        box_id = box["id"]
        await self._request(
            "POST",
            f"/profiles/{sender_id}/doodlebox/{box_id}/rasterimages/",
            {
                "png": base64.b64encode(png).decode(),
                "canvas_size": f"{WIDTH}x{HEIGHT}",
                "uuid": str(uuid.uuid4()).upper(),
            },
        )
        await self._request(
            "POST", f"/profiles/{sender_id}/doodlebox/{box_id}/publish", {"serial": doodle_uuid}
        )
        return box_id
