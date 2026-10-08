"""Measure an existing private SQL package offline. Never connects to start.gg or SQL."""
import argparse
import json
from pathlib import Path
import time

from ranking_package import canonical, validate_package
from publish_sql import MAX_BYTES, COMPRESSED_MAX, transport


def measure(path):
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Invalid package file')
    start = time.monotonic()
    package = json.loads(path.read_text())
    validate_package(package)
    body = transport(package)
    raw_bytes = len(canonical(package).encode())
    content = package['content']
    return package, dict(packageVersion=content['packageVersion'], sha256=package['sha256'],
        canonicalBytes=raw_bytes, gzipBytes=len(body), rawLimitBytes=MAX_BYTES, gzipLimitBytes=COMPRESSED_MAX,
        contextSets=len(content.get('gameContextSetIds', [])),
        entities={k:len(v) for k,v in content['entities'].items()},
        validationTransportSeconds=round(time.monotonic()-start, 3))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    try:
        package, result = measure(args.package)
        if args.baseline:
            baseline, previous = measure(args.baseline)
            result['baseline'] = previous
            result['publicIdentical'] = package['content']['public'] == baseline['content']['public']
            result['growthBytes'] = result['canonicalBytes'] - previous['canonicalBytes']
            result['gzipGrowthBytes'] = result['gzipBytes'] - previous['gzipBytes']
        print(json.dumps(result)); return 0
    except Exception:
        parser.exit(1, 'No se pudo medir: revisar paquete, hash, catálogo y límites.\n')


if __name__ == '__main__':
    main()
