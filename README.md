# Invoxia Triby for Home Assistant

> [!IMPORTANT]
> **Unofficial project.** This integration is not affiliated with, endorsed by, sponsored by,
> or supported by Invoxia. Please don't contact Invoxia support about it. See the
> [Disclaimer](#disclaimer).

Send notifications (text or images) from Home Assistant to an
[Invoxia Triby](https://en.wikipedia.org/wiki/Invoxia) e-ink display, the same way the
discontinued Triby mobile app sends "doodles".

It talks to the Invoxia cloud (`ws.invoxia.io`) using your Triby app account. The API was
reverse-engineered from the Android app, so it can stop working if Invoxia shuts the cloud down.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories** → add this repository's URL, type **Integration**.
2. Install **Invoxia Triby**, then restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *Invoxia Triby*, and log in with the
   email and password you use in the Triby app.

Manual install: copy `custom_components/triby` into your `config/custom_components/` folder and restart.

## Usage

### "Send a notification via triby"

In the automation editor, add the action **Notifications → Send a notification via triby**:

```yaml
action: notify.triby
data:
  title: Laundry          # optional, drawn as the first line
  message: The washing machine is done!
```

Send an image instead of text (scaled to 296×128 and dithered to black & white):

```yaml
action: notify.triby
data:
  message: ""
  data:
    image: /config/www/doorbell.png      # or an http(s):// URL
```

Local files must be inside an allowed directory (`/config/www` and `/media` by default,
see `allowlist_external_dirs`). With several Tribys, `notify.triby` sends to all of them; use
`target: ["<Triby title or profile id>"]` to pick one.

### Notify entity

Each Triby is also a `notify.triby` **entity**, usable with the standard action:

```yaml
action: notify.send_message
target:
  entity_id: notify.triby
data:
  title: Hi
  message: Dinner is ready
```

## How it works

1. `POST /profiles/{you}/doodlebox/` with the Triby as recipient
2. `POST /profiles/{you}/doodlebox/{id}/rasterimages/` with a 296×128 PNG
3. `POST /profiles/{you}/doodlebox/{id}/publish`

The server uses a private CA with legacy crypto (RSA-1024, SHA-1) that current OpenSSL
rejects, so the integration pins the server certificate's SHA-256 fingerprint instead of
lowering TLS security levels.

## Disclaimer

This is an independent, community-made project. It is **not affiliated with, endorsed by,
sponsored by, or in any way officially connected to Invoxia** or any of its subsidiaries or
affiliates. Invoxia has not reviewed or approved this integration and provides no support for it.

- The cloud API used here is private and undocumented. It was worked out by reverse-engineering
  the publicly available Triby Android app solely to keep a device the author owns working
  with Home Assistant after official support ended.
- No Invoxia source code, firmware, or artwork is included or redistributed in this repository.
  The icon is original artwork. Text is rendered with the bundled
  [DejaVu Sans](https://dejavu-fonts.github.io/) font (free license, see
  `custom_components/triby/fonts/LICENSE-DejaVu.txt`).
- Invoxia may change, restrict, or shut down its cloud service at any time without notice, and
  this integration may stop working as a result.
- You use this integration with your own Invoxia account, at your own risk. It is provided
  "as is", without warranty of any kind.

"Invoxia" and "Triby" are trademarks of their respective owner. They are used here only to
identify the device this integration works with, and their use does not imply any affiliation
with or endorsement by the trademark owner.
