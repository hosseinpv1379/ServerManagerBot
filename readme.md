# Hetzner Cloud Telegram Bot

A Telegram bot for managing Hetzner Cloud servers using the official [hcloud-python](https://github.com/hetznercloud/hcloud-python) SDK and python-telegram-bot v20+.

## Features

- **Servers** — list, create, reboot, power on/off, delete
- **Images** — browse OS templates with filtering
- **Locations** — view datacenter locations
- **SSH Keys** — list, add, delete

## Setup

### 1. Install dependencies

```bash
pip install -r bot/requirements.txt
```

Or with the project `pyproject.toml`:

```bash
pip install -e .
```

### 2. Configure environment

Copy the example env file and fill in your tokens:

```bash
cp bot/.env.example .env
```

Required variables:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_USER_IDS` | Comma-separated Telegram user IDs (from [@userinfobot](https://t.me/userinfobot)) |
| `HETZNER_TOKEN` | Optional — bootstrap first Hetzner API account |

Only users listed in `ADMIN_USER_IDS` can use the bot.

### 3. Run the bot

```bash
python main.py
```

## Project Structure

```
bot/
├── main.py              # Entry point
├── config.py            # Configuration
├── handlers/            # Feature handlers
│   ├── general.py       # /start, /help, /cancel
│   ├── server.py        # Server management
│   ├── image.py         # Image browsing
│   ├── location.py      # Location info
│   └── ssh_key.py       # SSH key management
└── utils/
    ├── api.py           # Hetzner API wrapper
    ├── formatters.py    # Message formatting
    └── validators.py    # Input validation
```

## License

MIT
