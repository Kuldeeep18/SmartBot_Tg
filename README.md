# SmartBot Monorepo

A monorepo housing multiple independent Telegram bots. Each bot lives in its own folder under `bots/` with its own dependencies, config, and Docker setup — fully isolated and independently deployable.

## Structure

```
bots/
├── anjani/       # Telegram group management bot
└── ...           # future bots go here
```

Each bot folder is self-contained:

```
bots/<bot-name>/
├── <bot-name>/       # Python source
├── test/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
├── config.env        # gitignored — copy from config.env_sample
└── config.env_sample
```

## Adding a New Bot

1. Create a new folder under `bots/`
2. Add its source code, `Dockerfile`, `docker-compose.yml`, and `pyproject.toml`
3. Copy `config.env_sample` → `config.env` and fill in the values
4. Run it independently from its own folder

## Bots

| Bot | Description | Docs |
|-----|-------------|------|
| [anjani](./bots/anjani) | Telegram group management bot | [README](./bots/anjani/README.md) |

## Repo-level Files

- `.github/` — CI/CD workflows shared across all bots
- `.editorconfig` — consistent editor settings
- `.gitignore` — ignores `config.env` across all bot folders
