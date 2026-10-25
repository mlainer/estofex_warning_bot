#!/usr/bin/env python3
"""Watch ESTOFEX for valid forecasts with threat level >= 1 and notify via
Telegram (with the forecast map attached).

Configuration (environment variables or a .env file next to this script):
    TELEGRAM_BOT_TOKEN           token from @BotFather
    TELEGRAM_CHAT_IDS            comma separated chat ids
    POLL_SECONDS                 optional, default 600
    MIN_LEVEL                    optional, default 1
    ESTOFEX_STATE_FILE           optional, path of the "already sent" state file
Usage:
    estofex_warning_bot.py            run forever
    estofex_warning_bot.py --once     check once and exit
    estofex_warning_bot.py --test     send a test message and exit
    estofex_warning_bot.py --archive  send the newest archived level 2 storm forecast and exit
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

BASE = 'https://www.estofex.org'
LIST_URL = BASE + '/cgi-bin/polygon/showforecast.cgi?listvalid=yes'
ARCHIVE_URL = BASE + '/cgi-bin/polygon/showforecast.cgi?list=yes'
HEADERS = {'User-Agent': 'estofex-warning-bot (personal alert tool; polite polling)'}
HERE = Path(__file__).resolve().parent
STATE_FILE = Path(os.environ.get('ESTOFEX_STATE_FILE', HERE / 'estofex_state.json'))


def load_env():
    env_file = HERE / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def csv_env(name):
    return [x.strip() for x in os.environ.get(name, '').split(',') if x.strip()]


def log(msg):
    print(f'{datetime.now():%Y-%m-%d %H:%M:%S} {msg}', flush=True)


# ---------------------------------------------------------------- ESTOFEX

ROW_RE = re.compile(
    r'fcstfile=(?P<file>[^"\'&>\s]+)["\']?>\s*<P[^>]*>(?P<title>.*?)<BR>\s*issued:(?P<issued>.*?)</P>.*?'
    r'graphics/(?P<level>\d)\.png',
    re.I | re.S)


def fetch_valid_forecasts(url=LIST_URL):
    """Return list of dicts for all products listed on the given page."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    page = r.text
    out = []
    for m in ROW_RE.finditer(page):
        out.append({
            'file': m['file'],
            'title': html.unescape(m['title']).strip(),
            'issued': html.unescape(m['issued']).strip(),
            'level': int(m['level']),
        })
    if not out and 'No valid' not in page:
        log('WARNING: no forecast rows parsed and no "No valid" marker; page layout may have changed')
    return out


def fetch_details(fcst):
    """Add url, map image bytes, validity and summary text."""
    q = urllib.parse.quote(fcst['file'])
    fcst['url'] = f'{BASE}/cgi-bin/polygon/showforecast.cgi?text=yes&fcstfile={q}'
    img_url = f'{BASE}/cgi-bin/polygon/showforecast.cgi?lightningmap=yes&fcstfile={q}'

    fcst['image'] = None
    try:
        r = requests.get(img_url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        if r.headers.get('content-type', '').startswith('image/'):
            fcst['image'] = r.content
    except requests.RequestException as e:
        log(f'could not fetch map: {e}')

    fcst['valid'] = ''
    fcst['summary'] = ''
    try:
        r = requests.get(fcst['url'], headers=HEADERS, timeout=30)
        r.raise_for_status()
        text = r.text
        m = re.search(r'Valid:\s*(.*?)<BR>', text, re.I | re.S)
        if m:
            fcst['valid'] = html.unescape(m[1]).strip()
        m = re.search(r'<P CLASS=["\']bulletin["\']>((?:(?!</P>).)*?\blevel\b.*?)(?:SYNOPSIS|DISCUSSION|</P>)',
                      text, re.I | re.S)
        if m:
            s = re.sub(r'<BR\s*/?>', '\n', m[1], flags=re.I)
            s = re.sub(r'<[^>]+>', '', s)
            fcst['summary'] = re.sub(r'\n{3,}', '\n\n', html.unescape(s)).strip()
    except requests.RequestException as e:
        log(f'could not fetch forecast text: {e}')
    return fcst


def build_text(f):
    lines = [f"ESTOFEX {f['title']}: LEVEL {f['level']}"]
    if f['valid']:
        lines.append(f"Valid: {f['valid']}")
    lines.append(f"Issued: {f['issued']}")
    if f['summary']:
        lines += ['', f['summary']]
    lines += ['', f['url'], '',
              'This is an automatically generated message.',
              'Please refer to the official website for further information: ' + BASE]
    return '\n'.join(lines)


# ---------------------------------------------------------------- senders

def send_telegram(text, image=None):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chats = csv_env('TELEGRAM_CHAT_IDS')
    if not (token and chats):
        log('telegram not configured, skipping')
        return False
    api = f'https://api.telegram.org/bot{token}/'
    ok = False
    for chat in chats:
        try:
            if image:
                # photo captions are limited to 1024 chars: send the rest as text
                caption, rest = text[:1024], text[1024:]
                r = requests.post(api + 'sendPhoto', data={'chat_id': chat, 'caption': caption},
                                  files={'photo': ('estofex.png', image, 'image/png')}, timeout=60)
                r.raise_for_status()
                if rest:
                    r = requests.post(api + 'sendMessage', data={'chat_id': chat, 'text': rest[:4096]}, timeout=30)
                    r.raise_for_status()
            else:
                r = requests.post(api + 'sendMessage', data={'chat_id': chat, 'text': text[:4096]}, timeout=30)
                r.raise_for_status()
            log(f'telegram sent to {chat}')
            ok = True
        except Exception as e:
            log(f'telegram failed for {chat}: {e}')
    return ok


# ---------------------------------------------------------------- main loop

def load_state():
    try:
        return set(json.loads(STATE_FILE.read_text()))
    except (OSError, ValueError):
        return set()


def save_state(sent):
    STATE_FILE.write_text(json.dumps(sorted(sent)))


def check():
    min_level = int(os.environ.get('MIN_LEVEL', '1'))
    sent = load_state()
    forecasts = fetch_valid_forecasts()
    log(f'{len(forecasts)} valid product(s): ' + ', '.join(f"{f['title']} L{f['level']}" for f in forecasts))
    for f in forecasts:
        if f['level'] < min_level or f['file'] in sent:
            continue
        if send_telegram(build_text(fetch_details(f)), f['image']):
            sent.add(f['file'])
            save_state(sent)


def send_archive_test(level):
    """Send the newest archived storm forecast of the given level (does not touch the state file)."""
    for f in fetch_valid_forecasts(ARCHIVE_URL):
        if f['level'] == level and 'storm' in f['title'].lower():
            log(f"sending archived forecast: {f['title']} L{f['level']} issued {f['issued']}")
            send_telegram(build_text(fetch_details(f)), f['image'])
            return
    log(f'no archived level {level} storm forecast found')


def main():
    load_env()
    if '--archive' in sys.argv:
        send_archive_test(2)
        return
    if '--test' in sys.argv:
        send_telegram('Test message from the ESTOFEX watcher.')
        return
    if '--once' in sys.argv:
        check()
        return
    log('starting...')
    poll = int(os.environ.get('POLL_SECONDS', '600'))
    while True:
        try:
            check()
        except Exception as e:
            log(f'check failed: {e}')
        time.sleep(poll)


if __name__ == '__main__':
    main()
