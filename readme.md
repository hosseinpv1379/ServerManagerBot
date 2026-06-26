# Hetzner Cloud Telegram Bot

A Telegram bot for managing Hetzner Cloud servers using the official [hcloud-python](https://github.com/hetznercloud/hcloud-python) SDK and python-telegram-bot v20+.

## Features

- **Multi-account** — manage multiple Hetzner API keys
- **Servers** — list, create, reboot, power on/off, set custom password via SSH, delete
- **SSH on server** — install Hetzner Cloud keys or paste a public key directly on the server
- **Images** — browse OS templates with filtering
- **Locations** — view datacenter locations
- **SSH Keys** — manage keys in Hetzner Cloud
- **Admin-only** — only configured Telegram user IDs can use the bot

## Setup

### 1. Install dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r bot/requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_USER_IDS` | Yes | Comma-separated Telegram user IDs ([@userinfobot](https://t.me/userinfobot)) |
| `HETZNER_TOKEN` | No | Bootstrap first Hetzner API account (or add via bot) |

Example `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABCDEF
ADMIN_USER_IDS=111111111,222222222
HETZNER_TOKEN=your_hetzner_api_token
```

### 3. Run the bot

```bash
python main.py
```

## Deploy notes

- Never commit `.env` or `data/accounts.json` (already in `.gitignore`)
- The bot needs outbound SSH (port 22) to server IPs for password/key operations
- Store secrets as GitHub Actions secrets if deploying via CI

## Project Structure

```
bot/
├── main.py
├── config.py
├── handlers/
├── services/
└── utils/
data/              # runtime API accounts (gitignored)
main.py            # entry point
```

## License

MIT
