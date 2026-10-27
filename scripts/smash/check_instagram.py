"""Read public, sanitized cron health only. Never connects to Instagram, FTP or SQL."""
import json
from datetime import datetime, timezone
import urllib.request

URL = 'https://rankingsmashbros.com/data/instagram-status.json'
MAX_AGE_SECONDS = 3 * 3600


def check(status, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        if not isinstance(status, dict) or set(status) != {'schemaVersion', 'checkedAt', 'ok', 'status', 'code'}:
            return False
        if type(status['schemaVersion']) is not int or status['schemaVersion'] != 1 or status['ok'] is not True or status['status'] != 'ready' or status['code'] is not None:
            return False
        if not isinstance(status['checkedAt'], str):
            return False
        at = datetime.fromisoformat(status['checkedAt'].replace('Z', '+00:00'))
        return at.tzinfo is not None and -300 <= (now - at).total_seconds() <= MAX_AGE_SECONDS
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def main():
    try:
        req = urllib.request.Request(URL, headers={'Accept': 'application/json', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.geturl() != URL or response.status != 200:
                raise ValueError()
            raw = response.read(2049)
        ok = len(raw) <= 2048 and check(json.loads(raw))
    except Exception:
        ok = False
    # Allowlisted output; source errors/URLs/content/credentials are never echoed.
    print(json.dumps({'ok': ok, 'status': 'instagram_ready' if ok else 'instagram_capture_needs_attention'}))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
