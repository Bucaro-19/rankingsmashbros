"""Bounded first-party load measurement. Plan only unless --execute is explicit.

No browser/assets crawler, redirects, providers or arbitrary endpoint arguments.
Production execution additionally requires the owner's chosen window and limits.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import fcntl
import gzip
from http.cookies import SimpleCookie
import http.client
import io
import json
import math
from pathlib import Path
import re
import ssl
import socket
import tempfile
import threading
import time
from urllib.parse import urlsplit

LEVELS = (1, 2, 5, 10, 20, 40)
MAX_USERS = 40
MAX_REQUESTS = 2000
MAX_WRITES = 10
STEP_SECONDS = 60
PACE_SECONDS = 10
COOLDOWN_SECONDS = 10
TIMEOUT_SECONDS = 4
MAX_BODY = 8 * 1024 * 1024
MAX_DECODED = 32 * 1024 * 1024
MAX_WALL_SECONDS = 1800
UA = 'SmashGT-LoadTest'
GT = timezone(timedelta(hours=-6))
SCENARIOS = ('visitor', 'static', 'php-no-db', 'php-read', 'php-write', 'analysis-local')
PATHS = {'/', '/data/public.json', '/arena.css', '/account-api.php', '/analisis-api.php', '/visita.php'}


def instant(text):
    at = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('La ventana necesita zona horaria, por ejemplo -06:00.')
    return at


def origin(text, production=False):
    p = urlsplit(text)
    if p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
        raise ValueError('Solo un origen raíz sin credenciales, ruta ni query.')
    if production:
        if p.scheme != 'https' or p.hostname != 'rankingsmashbros.com' or p.port not in (None, 443):
            raise ValueError('Producción: solo https://rankingsmashbros.com.')
    elif p.scheme != 'http' or p.hostname != '127.0.0.1' or not p.port:
        raise ValueError('Local: solo http://127.0.0.1:PUERTO.')
    return text.rstrip('/')


def production_window(start, end):
    a, b = instant(start).astimezone(GT), instant(end).astimezone(GT)
    if (a.date() != b.date() or a.weekday() >= 5 or a.hour >= 6 or b.hour >= 6
            or not 75 <= (b - a).total_seconds() <= MAX_WALL_SECONDS):
        raise ValueError('Ventana: lunes–viernes, madrugada Guatemala (00:00–05:59), 75 s–30 min.')
    return a, b


def safe_cron_slot(now, seconds=STEP_SECONDS):
    # No HTTP in the first 90 s after a 5-minute boundary, nor the 90 s before the next.
    # Owner must confirm that the worker actually finishes inside the excluded window.
    phase = (now.minute % 5) * 60 + now.second + now.microsecond / 1e6
    return 90 <= phase and phase + seconds + TIMEOUT_SECONDS + 10 < 210


def error_kind(error):
    # Enumerated diagnostics only, never exception text that could include private data.
    if isinstance(error,TimeoutError): return 'timeout'
    if isinstance(error,ssl.SSLCertVerificationError): return 'tls_validation'
    if isinstance(error,socket.gaierror): return 'dns_error'
    if isinstance(error,ConnectionRefusedError): return 'connection_refused'
    if isinstance(error,http.client.IncompleteRead): return 'incomplete_body'
    if isinstance(error,(ValueError,TypeError)): return 'invalid_content'
    return 'transport_error'



def json_body(content, encoding=None):
    if encoding and encoding != 'identity':
        if encoding != 'gzip': raise ValueError('Unsupported encoding')
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
            content=compressed.read(MAX_DECODED+1)
    if len(content)>MAX_DECODED: raise ValueError('Decoded body limit')
    data=json.loads(content)
    if not isinstance(data,dict): raise ValueError('Expected object')
    return data


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)], 6)


def metrics(samples, elapsed):
    values = [s['seconds'] for s in samples]
    n = len(samples)
    return dict(requests=n, requestsPerSecond=round(n / max(elapsed, .001), 3),
                p50=percentile(values, 50), p95=percentile(values, 95), p99=percentile(values, 99),
                errors=sum(bool(s['error']) for s in samples), errorRate=round(sum(bool(s['error']) for s in samples) / n, 6) if n else 0,
                statusCounts=dict(Counter(str(s['status']) for s in samples)),
                errorKinds=dict(Counter(s['error'] for s in samples if s['error'])),
                bodyBytes=sum(s['bytes'] for s in samples))


def brake(samples):
    if not samples:
        return None
    if sum(bool(s['error']) for s in samples) / len(samples) > .01:
        return 'errors_over_1_percent'
    if percentile([s['seconds'] for s in samples], 95) > 3:
        return 'p95_over_3_seconds'
    # Do not let many cheap static requests hide a degraded PHP endpoint.
    for endpoint in {s['endpoint'] for s in samples}:
        group = [s for s in samples if s['endpoint'] == endpoint]
        if percentile([s['seconds'] for s in group], 95) > 3:
            return 'endpoint_p95_over_3_seconds'
    return None


class Budget:
    """Counters are shared by every visitor/stage; no CLI override and no races."""
    def __init__(self):
        self.requests = self.writes = 0
        self.lock = threading.Lock()

    def reserve(self, write=False):
        with self.lock:
            if self.requests >= MAX_REQUESTS or (write and self.writes >= MAX_WRITES):
                return False
            self.requests += 1
            self.writes += int(write)
            return True


class Transport:
    def __init__(self, base, cookie=None):
        p = urlsplit(base)
        cls = http.client.HTTPSConnection if p.scheme == 'https' else http.client.HTTPConnection
        self.connection = cls(p.hostname, p.port, timeout=TIMEOUT_SECONDS,
                              **({'context': ssl.create_default_context()} if p.scheme == 'https' else {}))
        self.base, self.cookie, self.validator = base, cookie, None
        self.authenticated = bool(cookie)
        self.jar = SimpleCookie()
        if cookie: self.jar.load(cookie)

    def close(self):
        self.connection.close()

    def request(self, endpoint, conditional=False):
        path = endpoint.split('?', 1)[0]
        if path not in PATHS or ('?' in endpoint and not re.fullmatch(r'/analisis-api.php\?rival=[0-9]{1,20}',endpoint)):
            raise ValueError('Endpoint fuera de la allowlist.')
        headers = {'User-Agent': UA, 'Accept-Encoding': 'gzip', 'Accept': '*/*'}
        if self.jar:
            headers['Cookie'] = '; '.join(key+'='+value.value for key,value in self.jar.items())
        if conditional and self.validator:
            headers[self.validator[0]] = self.validator[1]
        write = path == '/visita.php'
        body = b'{"page":"inicio","cookies":false}' if write else None
        if write:
            headers.update({'Origin': self.base, 'Content-Type': 'application/json'})
        started = time.monotonic()
        result = dict(endpoint=path, status='transport_error', seconds=0, bytes=0, error=None)
        try:
            self.connection.request('POST' if write else 'GET', endpoint, body=body, headers=headers)
            response = self.connection.getresponse()
            result['status'] = response.status
            for key,value in response.getheaders():
                if key.lower() == 'set-cookie':
                    cookie = SimpleCookie(); cookie.load(value)
                    for name in ('PHPSESSID','smash_visita'):
                        if name in cookie: self.jar[name] = cookie[name].value
            content = response.read(MAX_BODY + 1)
            result['bytes'] = len(content)
            # Latency includes connection/TLS, headers and body; parsing is client work afterwards.
            result['seconds'] = time.monotonic() - started
            if len(content) > MAX_BODY:
                result['error'] = 'body_too_large'; self.close()
            elif response.status not in ({204} if write else {200, 304} if path == '/data/public.json' else
                                         {401} if path == '/analisis-api.php' and not self.authenticated else {200}):
                # Redirects, 429 and unexpected 4xx also count; never follow/retry them.
                result['error'] = 'unexpected_status'
            elif path == '/data/public.json':
                if response.status == 200:
                    tag, modified = response.getheader('ETag'), response.getheader('Last-Modified')
                    self.validator = ('If-None-Match', tag) if tag else ('If-Modified-Since', modified) if modified else None
                    if not self.validator:
                        result['error'] = 'validator_missing'
                    data = json_body(content,response.getheader('Content-Encoding'))
                    if data.get('rankingComputed') is not True or not data.get('players'):
                        result['error'] = 'invalid_public_json'
                elif not conditional or content:
                    result['error'] = 'unexpected_304'
            elif path == '/account-api.php':
                data = json_body(content,response.getheader('Content-Encoding'))
                if data.get('ok') is not True or data.get('authenticated') is not False:
                    result['error'] = 'not_anonymous'
            elif path == '/analisis-api.php' and self.authenticated:
                data = json_body(content,response.getheader('Content-Encoding'))
                if data.get('ok') is not True or data.get('state') != 'listo':
                    result['error'] = 'analysis_not_ready'
        except (OSError, http.client.HTTPException, ValueError, TypeError) as error:
            result['error'] = error_kind(error)
            self.close()
        result['seconds'] = result['seconds'] or time.monotonic() - started
        return result


def stage(base, scenario, users, budget, *, cookies=None, rival=None, stop=None, now=None):
    if users not in LEVELS or users > (2 if scenario == 'php-write' else MAX_USERS):
        raise ValueError('Escalón no permitido.')
    stop = stop or threading.Event()
    samples, lock, reason = [], threading.Lock(), [None]
    start = time.monotonic(); deadline = start + STEP_SECONDS
    cpu = time.process_time()

    def visitor(number):
        client = Transport(base, cookies[number] if cookies else None)
        pace = 20 if scenario == 'php-write' else PACE_SECONDS
        first = True; tick = start
        try:
            while time.monotonic() < deadline and not stop.is_set():
                if now and not safe_cron_slot(now(), seconds=0):
                    with lock: reason[0] = reason[0] or 'cron_guard'
                    stop.set(); break
                paths = {'visitor': ('/', '/data/public.json', '/account-api.php'),
                         'static': ('/', '/data/public.json', '/arena.css'), 'php-no-db': ('/analisis-api.php',),
                         'php-read': ('/account-api.php',), 'php-write': ('/visita.php',),
                         'analysis-local': (f'/analisis-api.php?rival={rival}',)}[scenario]
                # First visitor journey also probes its freshly received validator immediately.
                # Subsequent page journeys use conditional GET, with no cache-busting query.
                paths = list(paths)
                if scenario in ('visitor','static') and first:
                    paths.insert(2, '/data/public.json')
                for path in paths:
                    if stop.is_set() or time.monotonic() >= deadline:
                        break
                    if not budget.reserve(path == '/visita.php'):
                        with lock: reason[0] = reason[0] or 'hard_request_cap'
                        stop.set(); break
                    conditional = path == '/data/public.json' and client.validator is not None
                    row = client.request(path, conditional)
                    with lock:
                        samples.append(row)
                        failure = brake(samples)
                        if failure:
                            reason[0] = reason[0] or failure; stop.set()
                first = False; tick += pace
                stop.wait(max(0, min(tick, deadline) - time.monotonic()))
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=users) as pool:
        try:
            list(pool.map(visitor, range(users)))
        except KeyboardInterrupt:
            stop.set()
            raise
    elapsed = time.monotonic() - start
    summary = metrics(samples, elapsed)
    endpoints = {path: metrics([s for s in samples if s['endpoint'] == path], elapsed)
                 for path in sorted({s['endpoint'] for s in samples})}
    return dict(users=users, elapsedSeconds=round(elapsed, 3), complete=elapsed >= STEP_SECONDS and not reason[0],
                stopReason=reason[0], metrics=summary, endpoints=endpoints,
                driverProcessCpuSeconds=round(time.process_time()-cpu,3))


def save(path, report):
    # No response bodies, cookies, CSRF, sessions or credentials in the report.
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)


def run(base, scenario, output, *, production=False, window=None, limits=None, cookies=None, rival=None, progress=None):
    base = origin(base, production)
    if scenario not in SCENARIOS or (production and scenario in ('php-write', 'analysis-local')):
        raise ValueError('Escenario no permitido en este entorno.')
    if cookies and (production or scenario != 'analysis-local'):
        raise ValueError('Sesiones solo para analysis-local.')
    if scenario == 'analysis-local' and (not cookies or len(cookies) < MAX_USERS or not str(rival).isdigit()):
        raise ValueError('Análisis local requiere 40 sesiones independientes y un rival local.')
    if production and (not window or not limits):
        raise ValueError('Faltan horario del dueño y límites de cPanel.')
    report = dict(schemaVersion=1, origin=base, scenario=scenario, userAgent=UA,
                  production=production, startedAt=datetime.now(timezone.utc).isoformat(),
                  hardLimits=dict(users=MAX_USERS, requests=MAX_REQUESTS, writeRequests=MAX_WRITES,
                                  stepSeconds=STEP_SECONDS, timeoutSeconds=TIMEOUT_SECONDS, wallSeconds=MAX_WALL_SECONDS),
                  counter='excluded' if scenario != 'php-write' else 'local_only_verify_sql_delta',
                  responseBodiesStored=False, resources=limits, steps=[], stopReason=None)
    budget = Budget(); stop = threading.Event(); wall = time.monotonic()
    # Prevent parallel invocations by this machine from multiplying the hard cap.
    lock_file = Path(tempfile.gettempdir())/'smashgt-loadtest.lock'
    with lock_file.open('a') as mutex:
        try:
            fcntl.flock(mutex, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Ya hay una medición en esta máquina.') from None
        try:
            for users in ((1,2) if scenario == 'php-write' else LEVELS):
                if production:
                    while True:
                        at = datetime.now(GT)
                        if time.monotonic() - wall + STEP_SECONDS + TIMEOUT_SECONDS > MAX_WALL_SECONDS:
                            report['stopReason'] = 'hard_wall_cap'; break
                        if at < window[0]:
                            stop.wait(min(10, (window[0]-at).total_seconds())); continue
                        if at + timedelta(seconds=STEP_SECONDS + TIMEOUT_SECONDS + 10) >= window[1]:
                            report['stopReason'] = 'authorized_window_ended'; break
                        if safe_cron_slot(at): break
                        stop.wait(1)  # No requests while cron may run.
                    if report['stopReason']: break
                if time.monotonic() - wall + STEP_SECONDS + TIMEOUT_SECONDS > MAX_WALL_SECONDS:
                    report['stopReason'] = 'hard_wall_cap'; break
                result = stage(base, scenario, users, budget, cookies=cookies, rival=rival, stop=stop,
                               now=(lambda: datetime.now(GT)) if production else None)
                report['steps'].append(result); report['stopReason'] = result['stopReason']
                report['requestsAttempted'], report['writeRequestsAttempted'] = budget.requests, budget.writes
                save(output, report)
                if progress: progress(result)
                if report['stopReason']: break
                stop.wait(COOLDOWN_SECONDS)
            report['stopReason'] = report['stopReason'] or 'completed_capped_ladder'
        except KeyboardInterrupt:
            stop.set(); report['stopReason'] = 'operator_interrupt'
        finally:
            report['finishedAt'] = datetime.now(timezone.utc).isoformat()
            report['wallSeconds'] = round(time.monotonic()-wall, 3)
            save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--scenario', choices=SCENARIOS, default='visitor')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Sin esto solo muestra el plan, cero HTTP.')
    parser.add_argument('--production', action='store_true')
    parser.add_argument('--owner-authorized', action='store_true')
    parser.add_argument('--window-start'); parser.add_argument('--window-end')
    parser.add_argument('--resource-snapshot', type=Path)
    parser.add_argument('--limits-file', type=Path)
    args = parser.parse_args()
    try:
        base = origin(args.origin, args.production)
        if args.production and args.scenario in ('php-write','analysis-local'):
            raise ValueError('Producción solo anónimos, sin escrituras del contador.')
        plan = dict(origin=base, scenario=args.scenario, steps=LEVELS if args.scenario!='php-write' else (1,2),
                    stepSeconds=STEP_SECONDS, maxRequests=MAX_REQUESTS, maxWriteRequests=MAX_WRITES,
                    execute=args.execute, production=args.production, visitsExcluded=args.scenario!='php-write')
        if not args.execute:
            print(json.dumps(plan,ensure_ascii=False,indent=2)); return
        limits = window = None
        if args.production:
            if not args.owner_authorized or not args.window_start or not args.window_end:
                raise ValueError('Se necesita orden expresa del dueño y su ventana; no ejecutarlo por inferencia.')
            window = production_window(args.window_start, args.window_end)
            if window[1] <= datetime.now(GT) or window[0] > datetime.now(GT)+timedelta(seconds=MAX_WALL_SECONDS):
                raise ValueError('La ventana ya pasó o falta más de 30 minutos.')
            if not args.resource_snapshot or not args.resource_snapshot.is_file() or not args.limits_file:
                raise ValueError('Falta captura de Uso de recursos y archivo de límites.')
            limits = json.loads(args.limits_file.read_text())
            required = ('cpuPercent','memoryMiB','entryProcesses','ioKiBps','iops','processes','workerWindowConfirmed')
            if (any(type(limits.get(key)) not in (float,int) or limits[key] <= 0 for key in required[:-1])
                    or limits.get('workerWindowConfirmed') is not True):
                raise ValueError('Límites reales positivos y worker terminado dentro de 90 s deben confirmarse.')
            limits = {key: limits[key] for key in required}
        print('Medición limitada; las pausas de producción evitan el cron. Ctrl+C detiene toda la escalera.',flush=True)
        result = run(base,args.scenario,args.output,production=args.production,window=window,limits=limits,
                     progress=lambda step: print(json.dumps(dict(users=step['users'],requests=step['metrics']['requests'],
                         p95=step['metrics']['p95'],errors=step['metrics']['errors'],stopReason=step['stopReason']),ensure_ascii=False),flush=True))
        print(json.dumps(dict(output=str(args.output),stopReason=result['stopReason'],
                              steps=len(result['steps']),requests=result.get('requestsAttempted',0)),ensure_ascii=False))
        if result['stopReason']!='completed_capped_ladder':
            parser.exit(3,'Medición detenida: '+result['stopReason']+'; no subir de escalón.\n')
    except (ValueError,OSError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__': main()
