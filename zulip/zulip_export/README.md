# Zulip Export to Static HTML

This project exports Zulip messages from a stream (optionally a single topic) into a static HTML viewer with local attachments.

## Features

- Exports stream messages (or one topic) and attachments via Zulip API.
- Converts image attachments to WEBP (when Pillow is installed).
- Renders other attachments as explicit download buttons.
- Includes text search and date jump in the viewer.
- Can embed all messages in HTML, or load from a generated JSON file.

## Requirements

- Python 3.9+
- `requests`
- Optional: `Pillow` (for WEBP conversion)

Install dependencies:

```bash
pip install requests pillow
```

## Usage

```bash
python zulip_export.py \
  --base-url https://zulip.yourcompany.com \
  --email you@company.com \
  --api-key YOUR_API_KEY \
  --stream "My Stream"
```

Export a single topic:

```bash
python zulip_export.py \
  --base-url https://zulip.yourcompany.com \
  --email you@company.com \
  --api-key YOUR_API_KEY \
  --stream "My Stream" \
  --topic "Some Topic"
```

## CLI options

- `--base-url` Zulip base URL.
- `--email` Zulip account email.
- `--api-key` Zulip API key.
- `--stream` Stream name.
- `--topic` Optional topic filter.
- `--out` Output folder (default: `zulip_export`).
- `--chunk-size` Render batch size in the HTML app.
- `--embed-html` Embed messages in generated HTML (default enabled).
- `--no-embed-html` Load messages from generated JSON instead.
- `--webp-quality` WEBP quality from 1 to 100.
- `--webp-workers` Parallel workers for WEBP conversion.
- `--delete-original-images` Delete `uploads_originalimages/` after a successful conversion pass where no message still depends on originals.

## Output naming

Output filenames are sanitized to contain only alphanumeric characters and underscores:

- Full stream export:
  - `<STREAM>.html`
  - `<STREAM>.json`
- Single topic export:
  - `<STREAM>_<TOPIC>.html`
  - `<STREAM>_<TOPIC>.json`

Any non-alphanumeric characters in stream/topic names are replaced with `_`.

## Output structure

Example output folder:

```text
zulip_export/
  <STREAM>.html or <STREAM>_<TOPIC>.html
  <STREAM>.json or <STREAM>_<TOPIC>.json
  uploads/
  uploads_originalimages/
  uploads_webp/
```

## Notes

- If Pillow is not installed, images are not converted and original files are used.
- For local `file://` viewing, some browsers may block JSON fetches. Use `--embed-html` (default) or serve the folder with a local HTTP server.
