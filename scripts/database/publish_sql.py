"""Deliver the published ranking to the private hosting queue over authenticated HTTPS."""
import argparse
import gzip
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import sys
import time
import urllib.error
import urllib.request

from ranking_package import canonical, validate_package

URL = 'https://rankingsmashbros.com/ranking-sync.php'
PATH = '/ranking-sync.php'
MAX_BYTES = 32 * 1024 * 1024
COMPRESSED_MAX = 4 * 1024 * 1024


class SyncStopped(Exception):
    pass


def transport(package):
    validate_package(package)
    def check(value):
        if isinstance(value, float) or (type(value) is int and not -9223372036854775808 <= value <= 9223372036854775807):
            raise SyncStopped('transport_type_unsupported')
        if isinstance(value, dict):
            for item in value.values(): check(item)
        elif isinstance(value, list):
            for item in value: check(item)
    check(package)
    raw = canonical(package).encode()
    if len(raw) > MAX_BYTES: raise SyncStopped('payload_too_large')
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', mtime=0) as f: f.write(raw)
    compressed = output.getvalue()
    if len(compressed) > COMPRESSED_MAX: raise SyncStopped('payload_too_large')
    return compressed


def signature(key, at, nonce, body):
    message = 'POST\n%s\n%s\n%s\n%s' % (PATH, at, nonce, hashlib.sha256(body).hexdigest())
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(key, body, content_type):
    at, nonce = str(int(time.time())), secrets.token_hex(16)
    req = urllib.request.Request(URL, data=body, method='POST', headers={
        'Content-Type': content_type, 'X-Smash-Timestamp': at, 'X-Smash-Nonce': nonce,
        'X-Smash-Signature': signature(key, at, nonce, body)})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=45) as r:
            if r.geturl() != URL: raise SyncStopped('receiver_unavailable')
            value = json.loads(r.read(8193))
        if not isinstance(value, dict) or value.get('ok') is not True: raise SyncStopped('receiver_rejected')
        return value
    except SyncStopped:
        raise
    except Exception:
        # Never expose urllib messages, authenticated headers, body or driver output.
        raise SyncStopped('receiver_unavailable') from None


def deliver(key, body, wait_seconds=600, *, pause=time.sleep, clock=time.monotonic):
    digest = hashlib.sha256(body).hexdigest()
    value = None
    for attempt in range(3):
        try:
            value = request(key, body, 'application/gzip'); break
        except SyncStopped:
            if attempt == 2: raise
            pause(5 * (attempt + 1))
    deadline = clock() + wait_seconds
    while True:
        if value.get('status') == 'succeeded':
            return {'ok': True, 'status': 'sql_synchronized', 'jobId': value.get('jobId'), 'transportSha256': digest}
        if value.get('status') == 'failed': raise SyncStopped('hosting_import_failed')
        if value.get('status') not in ('queued', 'running'): raise SyncStopped('receiver_response_invalid')
        if clock() >= deadline: raise SyncStopped('hosting_import_pending')
        pause(min(15, max(0, deadline - clock())))
        value = request(key, canonical({'operation': 'status', 'sha256': digest}).encode(), 'application/json')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'send', 'diagnostic'])
    parser.add_argument('package', type=Path, nargs='?')
    parser.add_argument('--wait-seconds', type=int, default=600)
    args = parser.parse_args(argv)
    try:
        if args.command == 'diagnostic': body = None
        else:
            if args.package is None or args.package.is_symlink() or args.package.stat().st_size > MAX_BYTES:
                raise SyncStopped('package_invalid')
            body = transport(json.loads(args.package.read_text()))
        if args.command == 'check': result = {'ok': True, 'status': 'transport_validated', 'compressedBytes': len(body)}
        else:
            key = os.environ.get('SMASH_SQL_SYNC_KEY', '')
            if len(key) != 64 or any(c not in '0123456789abcdef' for c in key): raise SyncStopped('sync_key_missing')
            if args.command == 'diagnostic':
                value = request(key, b'{"operation":"diagnostic"}', 'application/json')
                # Allowlist response: even a bad/misconfigured receiver must not print arbitrary content.
                result = {k: value.get(k) for k in ('ok', 'phpVersion', 'memoryLimit', 'postMaxSize', 'maxExecutionTime', 'inboxWritable')}
            else: result = deliver(key, body, args.wait_seconds)
        print(json.dumps(result)); return 0
    except Exception as error:
        reason = str(error) if isinstance(error, SyncStopped) else 'package_invalid'
        print(json.dumps({'ok': False, 'reason': reason})); return 1


if __name__ == '__main__': sys.exit(main())
