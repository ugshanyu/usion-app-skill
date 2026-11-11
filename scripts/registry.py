#!/usr/bin/env python3
"""Scoped registry helper. Never deploy this private skill with a game."""
import argparse
import json
import hashlib
import io
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from pathlib import Path
import sys
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE = 'https://agents.usions.com/v1'
FIELDS = ('id', 'name', 'iframe_url', 'image', 'is_published', 'visibility',
          'tags', 'game_config', 'realtime', 'leaderboard')

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def token_from(path):
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('\"\'')
    token = values.get('USION_API_TOKEN', '')
    if not token.startswith('usion_sk_') or any(c.isspace() for c in token):
        raise ValueError('Expected personal USION_API_TOKEN in credentials.env')
    return token

def clean(value, token=''):
    if isinstance(value, dict):
        return {k: clean(v, token) for k, v in value.items()
                if not any(x in k.lower() for x in ('secret', 'token', 'authorization', 'password'))}
    if isinstance(value, list):
        return [clean(v, token) for v in value]
    if isinstance(value, str) and token:
        return value.replace(token, '[REDACTED]')
    return value

def summarize(data, token):
    if isinstance(data, list):
        return [summarize(item, token) for item in data]
    if not isinstance(data, dict):
        raise ValueError('Unexpected API response; inspect privately before proceeding')
    return clean({key: data[key] for key in FIELDS if key in data}, token)

def request(method, route, token, payload=None, public=False, content_type=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'UsionsRegistryHelper/1.0'}
    if not public:
        headers['Authorization'] = 'Bearer ' + token
    body = None
    if payload is not None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        if token.encode() in body:
            raise ValueError('Refusing payload containing the private token')
        headers['Content-Type'] = content_type or 'application/json'
    req = Request(BASE + route, data=body, headers=headers, method=method)
    with build_opener(NoRedirect()).open(req, timeout=120) as response:
        return response.status, json.load(response)

def bundle_input(path, token):
    """Keep the deploy directory separate from the private skill directory."""
    if path.is_dir():
        output = io.BytesIO()
        files = sorted(p for p in path.rglob('*') if p.is_file() or p.is_symlink())
        if not files or len(files) > 128:
            raise ValueError('Use a deploy folder with 1–128 static files')
        total = 0
        with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
            for file in files:
                relative = file.relative_to(path)
                if file.is_symlink() or any(part.startswith('.') for part in relative.parts):
                    raise ValueError('Remove symlinks and hidden files from the deploy folder')
                if file.name == 'credentials.env' or file.stat().st_size > 8 * 1024 * 1024:
                    raise ValueError('Remove credentials or oversized files from deploy folder')
                data = file.read_bytes()
                total += len(data)
                if total > 24 * 1024 * 1024 or token.encode() in data:
                    raise ValueError('Bundle too large or contains private token')
                info = ZipInfo(relative.as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, data)
        data, mime = output.getvalue(), 'application/zip'
    else:
        if path.stat().st_size > 12 * 1024 * 1024:
            raise ValueError('Upload exceeds 12 MiB')
        data = path.read_bytes()
        mime = 'text/html' if path.suffix.lower() == '.html' else 'application/zip'
    if len(data) > 12 * 1024 * 1024 or token.encode() in data:
        raise ValueError('Bundle too large or contains private token')
    return data, mime


def registration_with_deployment(payload, receipt, icon=None):
    if receipt.get('status') != 'hosted' or not receipt.get('iframe_url', '').startswith('https://'):
        raise ValueError('Expected successful HTTPS hosting receipt')
    result = dict(payload, iframe_url=receipt['iframe_url'])
    if icon:
        matches = [file['url'] for file in receipt['files'] if file['path'] == icon]
        if not matches:
            raise ValueError('Icon is not in the hosted file manifest')
        result['image'] = matches[0]
    return result


def check_hosting(receipt):
    if receipt.get('status') != 'hosted' or not receipt.get('files'):
        raise ValueError('Expected hosting receipt with file manifest')
    total = 0
    for file in receipt['files']:
        if not file['url'].startswith('https://'):
            raise ValueError('Hosting URL must be HTTPS')
        req = Request(file['url'], headers={'User-Agent': 'UsionsRegistryHelper/1.0'})
        with build_opener(NoRedirect()).open(req, timeout=30) as response:
            data = response.read(8 * 1024 * 1024 + 65536)
        total += len(data)
        if total > 25 * 1024 * 1024 or len(data) != file['bytes'] or hashlib.sha256(data).hexdigest() != file['sha256']:
            raise ValueError('Hosted file does not match receipt')
    return {'status': 'hosted_bytes_verified', 'files_verified': len(receipt['files']), 'gameplay_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    sub.add_parser('check-hosting').add_argument('receipt', type=Path)
    for command in ('register', 'update'):
        register = sub.add_parser(command)
        if command == 'update':
            register.add_argument('id')
        register.add_argument('payload', type=Path)
        register.add_argument('--deployment', type=Path, help='JSON receipt written by upload --output')
        register.add_argument('--icon', help='Path in the hosted bundle, e.g. icon.png')
    sub.add_parser('verify').add_argument('id')
    upload = sub.add_parser('upload')
    upload.add_argument('bundle', type=Path, help='Game-only directory, ZIP or single HTML file')
    upload.add_argument('--output', type=Path, help='Save the hosting receipt for registration')
    sub.add_parser('deployment').add_argument('id')
    args = parser.parse_args()
    if args.command == 'check-hosting':
        print(json.dumps(check_hosting(json.loads(args.receipt.read_text())), indent=2))
        return 0
    token = token_from(Path(__file__).resolve().parents[1] / 'credentials.env')
    payload, content_type = None, None
    method, route, public = 'GET', '/games', False
    if args.command in ('register', 'update'):
        payload = json.loads(args.payload.read_text())
        if not isinstance(payload, dict):
            raise ValueError('Payload must be a JSON object')
        if args.deployment:
            payload = registration_with_deployment(payload, json.loads(args.deployment.read_text()), args.icon)
        elif args.icon:
            raise ValueError('--icon requires --deployment')
        if args.command == 'register':
            method, route = 'POST', '/games'
        else:
            method, route = 'PUT', '/games/' + quote(args.id, safe='')
    elif args.command == 'verify':
        route, public = '/games/' + quote(args.id, safe=''), False
    elif args.command == 'upload':
        payload, content_type = bundle_input(args.bundle, token)
        method, route = 'POST', '/games/uploads'
    elif args.command == 'deployment':
        route = '/games/uploads/' + quote(args.id, safe='')
    try:
        status, data = request(method, route, token, payload, public, content_type)
    except HTTPError as exc:
        detail = 'Request rejected; no automatic retry.'
        try:
            error = json.loads(exc.read(4096)).get('detail')
            if isinstance(error, str):
                detail = clean(error, token)
        except (ValueError, OSError):
            pass
        print(json.dumps({'http_status': exc.code, 'error': detail}), file=sys.stderr)
        return 1
    except (URLError, TimeoutError) as exc:
        cause = getattr(exc, 'reason', exc)
        category = ('dns_resolution_failed' if isinstance(cause, socket.gaierror) else
                    'tls_failed' if isinstance(cause, ssl.SSLError) else
                    'timeout' if isinstance(cause, TimeoutError) else 'connection_failed')
        print(json.dumps({'error': category, 'url': BASE + route,
                          'client': 'UsionsRegistryHelper/1.0',
                          'next_step': 'Check outbound HTTPS capability. Reconcile registration with list before retrying; identical uploads are idempotent.'}), file=sys.stderr)
        return 1
    if args.command in ('upload', 'deployment'):
        result = clean(data, token)
        if args.command == 'upload' and args.output:
            args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'http_status': status, 'deployment': result}, indent=2))
    else:
        print(json.dumps({'http_status': status, 'service_metadata': summarize(data, token)}, indent=2))
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError):
        print('Invalid input, credential file, or response. Inspect privately; do not print credentials.', file=sys.stderr)
        sys.exit(1)
