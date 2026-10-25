# ESTOFEX Warning Bot

A small Python bot that watches [ESTOFEX](https://www.estofex.org) (European Storm Forecast Experiment) and sends a **Telegram message with the forecast map** whenever a storm forecast with **threat level 1 or higher** is published.

> **Disclaimer:** This is an unofficial, private hobby tool. It is not affiliated with or endorsed by ESTOFEX. ESTOFEX products assist meteorologists; they are **not** official warnings. Official warnings are issued by your national weather service (see [meteoalarm.eu](https://www.meteoalarm.eu)). The bot may fail or miss a forecast. Do not rely on it for safety-critical decisions.

## Acknowledgements

All forecast content (maps, texts, threat levels) is produced by the volunteer forecasters of **[ESTOFEX](https://www.estofex.org)**, which offers its service without funding or advertisement. Many thanks to the whole team for their work.

ESTOFEX forecasts are published under the [Creative Commons Attribution-NonCommercial-ShareAlike 3.0 license](https://creativecommons.org/licenses/by-nc-sa/3.0/). Every message sent by this bot links back to the original forecast. Please keep use of the bot **non-commercial**, keep the attribution, and be considerate: the bot polls only every 10 minutes by default. Please don't lower that interval much.

## Features

- Detects the currently valid forecasts on estofex.org and their threat level (0–3)
- Sends the forecast map (PNG) plus validity, issue time, level summary and a link via Telegram
- Sends each forecast only once (state kept in `estofex_state.json`)
- Telegram command `/last`: sends the latest storm forecast on demand (from the archive if none is currently valid)
- Configurable minimum level and polling interval
- Only dependency: `requests`

## Quick start

```bash
git clone https://github.com/<your-user>/estofex_warning_bot.git
cd estofex_warning_bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit .env
```

### Create the Telegram bot

1. Open Telegram, talk to [@BotFather](https://t.me/BotFather), send `/newbot` and follow the steps. Put the token in `TELEGRAM_BOT_TOKEN`.
2. Send any message to your new bot (or add it to a group or channel).
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy `chat` → `id` into `TELEGRAM_CHAT_IDS`. Several IDs can be comma separated.

### Configuration (`.env` or environment variables)

| Variable             | Required | Default | Description                                      |
|----------------------|----------|---------|--------------------------------------------------|
| `TELEGRAM_BOT_TOKEN` | yes      |         | Bot token from @BotFather                        |
| `TELEGRAM_CHAT_IDS`  | yes      |         | Comma separated chat IDs that receive alerts     |
| `MIN_LEVEL`          | no       | `1`     | Minimum threat level that triggers an alert      |
| `POLL_SECONDS`       | no       | `600`   | Seconds between checks                           |
| `ESTOFEX_STATE_FILE` | no       | `estofex_state.json` next to the script | Where the "already sent" list is stored (set to `/data/...` in Docker) |

## Usage

```bash
python estofex_warning_bot.py            # run forever
python estofex_warning_bot.py --once     # check once and exit (for cron)
python estofex_warning_bot.py --test     # send a test message
python estofex_warning_bot.py --archive  # send the newest archived level 2 forecast
```

`--archive` is handy to check the whole chain (parsing, map download, Telegram) when ESTOFEX has no active forecast. It does not touch the "already sent" state.

### Running permanently

- **Docker / Docker Compose** (from the repository root, after creating `.env`):
  ```bash
  docker compose -f contrib/docker-compose.yml up -d --build
  docker compose -f contrib/docker-compose.yml logs -f
  # one-off checks:
  docker compose -f contrib/docker-compose.yml run --rm estofex-warning-bot python estofex_warning_bot.py --archive
  ```
  The "already sent" state is kept in the `estofex-data` volume, so a restart or rebuild doesn't resend alerts. The token is read from `.env` at runtime and is not baked into the image.
- **systemd:** see [contrib/estofex-warning-bot.service](contrib/estofex-warning-bot.service)
- **cron** (every 10 minutes):
  ```cron
  */10 * * * * cd /path/to/estofex_warning_bot && .venv/bin/python estofex_warning_bot.py --once >> bot.log 2>&1
  ```
- Or simply in `tmux`/`screen`.

## How it works

ESTOFEX has no API. The bot reads the HTML list of valid forecasts (`showforecast.cgi?listvalid=yes`), takes the threat level from the level icon of each row, and downloads the map and text of new forecasts. If ESTOFEX changes its page layout, the parser may need an update. The bot logs a warning if it finds neither forecasts nor the "No valid forecast" notice.

## Development

```bash
pip install pytest
pytest
```

## Security

Keep your bot token secret. `.env` is excluded via `.gitignore`. If a token ever leaks, revoke it with `/revoke` in @BotFather.

## License

Code: [MIT](LICENSE). Forecast content belongs to ESTOFEX and is subject to its own license (see above).
