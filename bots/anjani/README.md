# Anjani

A modern, fully async Telegram group management bot built with [Pyrogram](https://github.com/pyrogram/pyrogram) and Python 3.9+.

## Features

- Fully asynchronous — built on `asyncio` with optional `uvloop` on Linux
- Class-based plugin system — easy to extend with custom plugins
- Localization support — English, Indonesian, German out of the box
- MongoDB-backed — persistent data with replica set support
- Spam protection — SpamWatch integration + built-in spam prediction
- Prometheus metrics — exposed on port `8000`

## Plugins

| Plugin | Description |
|--------|-------------|
| Admins | Admin promotion/demotion tools |
| Backups | Group backup and restore |
| Debug | Developer debugging tools |
| Federation | Cross-group ban federation |
| Filters | Auto-reply keyword filters |
| Language | Per-chat language settings |
| Lockings | Lock specific message types |
| Misc | Miscellaneous utilities |
| Muting | Mute/unmute members |
| Notes | Saved notes per group |
| Purge | Bulk message deletion |
| Reporting | User reporting system |
| Restriction | Ban/kick/unban members |
| Rules | Group rules management |
| Spam Shield | Automated spam protection |
| Staff Tools | Tools for bot staff/owners |
| Stats | Bot usage statistics |
| Topic | Forum topic management |
| Users | User info and tracking |
| Welcome | Welcome/goodbye messages |

## Requirements

- Python 3.9+
- [Telegram API credentials](https://my.telegram.org/apps)
- [Bot token](https://t.me/botfather)
- MongoDB instance (local or [Atlas](https://cloud.mongodb.com))

## Setup

### 1. Clone and navigate

```bash
cd bots/anjani
```

### 2. Configure environment

```bash
cp config.env_sample config.env
```

Fill in `config.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | ✅ | From https://my.telegram.org/apps |
| `API_HASH` | ✅ | From https://my.telegram.org/apps |
| `BOT_TOKEN` | ✅ | From [@BotFather](https://t.me/botfather) |
| `OWNER_ID` | ✅ | Your Telegram user ID |
| `DB_URI` | ✅ | MongoDB connection URI (leave blank if using docker-compose) |
| `LOG_CHANNEL` | ☑️ | Channel ID for bot status logs |
| `ALERT_LOG` | ☑️ | Chat/channel for error alerts |
| `SW_API` | ☑️ | [SpamWatch](https://spamwat.ch) API key |
| `PLUGIN_FLAG` | ☑️ | Semicolon-separated list of plugins to disable |
| `WORKERS` | ☑️ | Number of update handler workers (default: pyrogram default) |
| `LOG_LEVEL` | ☑️ | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_COLOR` | ☑️ | Set to `true` to enable colored logs |

### 3. Run with Docker (recommended)

```bash
docker-compose up -d
```

This starts the bot and a local MongoDB replica set automatically.

### 4. Run manually

Install dependencies:

```bash
pip install poetry
poetry install -E uvloop   # omit -E uvloop on Windows
```

Start the bot:

```bash
poetry run anjani
# or
python -m anjani
```

## Custom Plugins

Drop your plugin file into `anjani/custom_plugins/`. See `anjani/custom_plugins/example.py` for the structure.

To disable a built-in plugin, add it to `PLUGIN_FLAG` in `config.env`:

```env
PLUGIN_FLAG="disable_spampredict_plugin;disable_canonical_plugin"
```

The flag name follows the pattern `disable_<plugin_name>_plugin` where `<plugin_name>` is the plugin's `name` attribute, lowercased with spaces replaced by underscores.

## Running Tests

```bash
poetry run pytest
```

## Tech Stack

- [Pyrofork](https://github.com/Mayuri-Chan/pyrofork) — Pyrogram fork
- [Motor / PyMongo](https://pymongo.readthedocs.io) — async MongoDB driver
- [aiorun](https://github.com/cjrh/aiorun) — async entry point
- [Pydantic v2](https://docs.pydantic.dev) — config validation
- [Prometheus Client](https://github.com/prometheus/client_python) — metrics

## License

GPL-3.0-or-later — see [LICENSE](../../LICENSE) for details.
