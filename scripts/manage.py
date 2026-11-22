"""Lesson64 hybrid deployment control. Always execute with Conda agent-dev."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tarfile
import time
from datetime import datetime
from urllib.parse import quote
from urllib.request import urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
STATE = ROOT / '.deployment'
ENV_FILE = ROOT / '.env.docker'
PID_FILE = STATE / 'api.pid.json'
LOG_FILE = STATE / 'api.log'


def private_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write(text)


def initialize():
    if ENV_FILE.exists():
        print('.env.docker exists; left unchanged.')
        return
    template = (ROOT / '.env.docker.example').read_text()
    template = template.replace('POSTGRES_PASSWORD=\n', 'POSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n')
    fd = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write(template)
    print('Created private .env.docker with a generated database password; original .env unchanged.')


def configuration():
    from dotenv import dotenv_values
    if not ENV_FILE.is_file():
        raise RuntimeError('Run scripts/manage.sh init first')
    values = {k: v or '' for k, v in dotenv_values(ENV_FILE).items()}
    # Explicit deployment variables may override the file, but never read original .env.
    for key in values:
        if key in os.environ:
            values[key] = os.environ[key]
    name = values.get('DEPLOYMENT_NAME', '')
    if not re.fullmatch(r'agentops-rca(?:[-_][a-z0-9_-]+)?', name):
        raise RuntimeError('DEPLOYMENT_NAME must be agentops-rca or use an agentops-rca- prefix (isolate existing projects)')
    for key in ('POSTGRES_USER', 'POSTGRES_DB'):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', values.get(key, '')):
            raise RuntimeError(key + ' must be a simple SQL identifier')
    ports = []
    for key in ('POSTGRES_PORT', 'REDIS_PORT', 'API_PORT'):
        value = int(values[key])
        if not 1024 <= value <= 65535 or value in (55432, 56379, 8064, 56432, 56479):
            raise RuntimeError(key + ' must be an unprivileged, isolated port')
        ports.append(value)
    if len(set(ports)) != 3:
        raise RuntimeError('Deployment ports must be distinct')
    if len(values.get('POSTGRES_PASSWORD', '')) < 16:
        raise RuntimeError('Set a private POSTGRES_PASSWORD of at least 16 characters')
    data = Path(os.path.expanduser(values['AGENTOPS_DATA_DIR']))
    data = (ROOT / data).resolve() if not data.is_absolute() else data.resolve()
    protected = [(ROOT / 'data').resolve(), (ROOT / 'backups').resolve(), (STATE / 'secrets').resolve()]
    if data == ROOT or data in ROOT.parents or data == STATE or data in STATE.parents:
        raise RuntimeError('Deployment data must not contain source, secrets or deployment control files')
    if any(data == path or data in path.parents or path in data.parents for path in protected):
        raise RuntimeError('Deployment data must not overlap existing data, backups or secrets')
    values['AGENTOPS_DATA_DIR'] = str(data)
    for key in ('HF_HOME', 'RERANKER_MODEL_PATH', 'EMBEDDING_MODEL_PATH'):
        if values.get(key):
            values[key] = str(Path(os.path.expanduser(values[key])).resolve())
    password = values['POSTGRES_PASSWORD']
    values['POSTGRES_DSN'] = 'postgresql://{}:{}@127.0.0.1:{}/{}'.format(
        values['POSTGRES_USER'], quote(password, safe=''), values['POSTGRES_PORT'], values['POSTGRES_DB'])
    values['REDIS_URL'] = 'redis://127.0.0.1:{}/0'.format(values['REDIS_PORT'])
    values['AGENTOPS_API_URL'] = 'http://127.0.0.1:{}'.format(values['API_PORT'])
    values['AGENTOPS_ENV_FILE'] = str(ENV_FILE)
    values['PYTHONUNBUFFERED'] = '1'
    values['HF_HUB_OFFLINE'] = '1'
    values['TRANSFORMERS_OFFLINE'] = '1'
    return values


def compose(values, *args, **kwargs):
    private_write(STATE / 'secrets/postgres_password', values['POSTGRES_PASSWORD'])
    # Password is a file secret; it is absent from Compose configuration and command arguments.
    env = {**os.environ, **{k: values[k] for k in (
        'DEPLOYMENT_NAME', 'POSTGRES_USER', 'POSTGRES_DB', 'POSTGRES_PORT', 'REDIS_PORT')}}
    return subprocess.run(['docker', 'compose', '--project-name', values['DEPLOYMENT_NAME'], '--project-directory', str(ROOT),
        '--env-file', str(ENV_FILE), '-f', str(ROOT / 'docker-compose.yml'), *args],
        cwd=ROOT, env=env, check=True, **kwargs)


def process_record():
    if not PID_FILE.exists():
        return None
    try:
        record = json.loads(PID_FILE.read_text())
        proc = Path('/proc') / str(record['pid'])
        # Match both process creation time and our exact serve command before signalling.
        start = proc.joinpath('stat').read_text().split(') ', 1)[1].split()[19]
        cmd = proc.joinpath('cmdline').read_bytes().split(b'\0')
        if start == record['start'] and str(Path(__file__).resolve()).encode() in cmd and b'_serve' in cmd:
            return record
    except (OSError, ValueError, KeyError):
        pass
    return None


def stop_api():
    record = process_record()
    if not record:
        PID_FILE.unlink(missing_ok=True)
        return
    os.kill(record['pid'], signal.SIGTERM)
    for _ in range(100):
        if not process_record():
            PID_FILE.unlink(missing_ok=True)
            print('API and its managed MCP children stopped.')
            return
        time.sleep(0.2)
    raise RuntimeError('API did not stop within 20 seconds; dependencies left running. Check private logs.')


def check_health(values, quiet=False):
    import psycopg
    import redis
    with psycopg.connect(values['POSTGRES_DSN'], connect_timeout=3) as conn:
        assert conn.execute('SELECT 1').fetchone()[0] == 1
    client = redis.Redis.from_url(values['REDIS_URL'], socket_connect_timeout=3, socket_timeout=3)
    try:
        assert client.ping()
    finally:
        client.close()
    with urlopen(values['AGENTOPS_API_URL'] + '/health', timeout=5) as response:
        body = json.load(response)
    if body.get('status') != 'ok':
        raise RuntimeError('API health is degraded')
    if not quiet:
        print('PASS: PostgreSQL SELECT 1, Redis PING, API /health (status=ok).')


def preflight(values, offline):
    if Path(sys.prefix).name != 'agent-dev':
        raise RuntimeError('Use the Conda agent-dev interpreter')
    if not process_record():
        import socket
        with socket.socket() as probe:
            # Uvicorn uses SO_REUSEADDR; permit its TIME_WAIT connections while
            # still rejecting a live listener on the same loopback address.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', int(values['API_PORT'])))
            except OSError:
                raise RuntimeError('API_PORT is already occupied; choose a free deployment port') from None
    if not offline and not values.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('Set DEEPSEEK_API_KEY in .env.docker, or use up --offline for deployment acceptance')
    for name in ('vector.index', 'metadata.json', 'embedding_store.pkl', 'rag_mcp_server.py',
                 'utility_mcp_server.py', 'observability_mcp_server.py'):
        if not (ROOT / name).is_file():
            raise RuntimeError('Missing required project asset: ' + name)
    if not Path(values['RERANKER_MODEL_PATH']).is_dir():
        raise RuntimeError('RERANKER_MODEL_PATH directory is missing; provision offline weights first')
    if values.get('EMBEDDING_MODEL_PATH') and not Path(values['EMBEDDING_MODEL_PATH']).is_dir():
        raise RuntimeError('EMBEDDING_MODEL_PATH directory is missing')
    if not values.get('EMBEDDING_MODEL_PATH'):
        hub = Path(values['HF_HOME']) / 'hub/models--BAAI--bge-small-zh-v1.5/snapshots'
        if not hub.is_dir():
            raise RuntimeError('Offline embedding cache missing; set EMBEDDING_MODEL_PATH')
    Path(values['AGENTOPS_DATA_DIR']).mkdir(parents=True, exist_ok=True, mode=0o700)


def start_api(values, offline):
    if process_record():
        print('Managed API already running; use stop/up to change configuration.')
        check_health(values)
        return
    preflight(values, offline)
    env = {**os.environ, **values}
    env['AGENTOPS_OFFLINE'] = '1' if offline else '0'
    if offline:
        env['DEEPSEEK_API_KEY'] = 'offline-validation-no-real-key'
    private_write(LOG_FILE, '')
    with LOG_FILE.open('ab') as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '_serve'],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True)
    try:
        start = Path(f'/proc/{process.pid}/stat').read_text().split(') ', 1)[1].split()[19]
        private_write(PID_FILE, json.dumps({'pid': process.pid, 'start': start, 'offline': offline}))
        for _ in range(180):
            if process.poll() is not None:
                raise RuntimeError('API exited during startup; inspect scripts/manage.sh logs api')
            try:
                check_health(values, quiet=True)
                print('API ready at ' + values['AGENTOPS_API_URL'] + (' (offline validation)' if offline else ''))
                return
            except Exception:
                time.sleep(1)
        raise RuntimeError('API startup timed out; inspect private API log')
    except BaseException:
        stop_api()
        raise


def serve():
    # Never print credentials, DSNs, raw requests or Uvicorn access paths (session IDs).
    class RedactedStream:
        def __init__(self, wrapped):
            self.wrapped = wrapped
        def write(self, value):
            for key in ('DEEPSEEK_API_KEY', 'POSTGRES_PASSWORD', 'POSTGRES_DSN'):
                secret = os.getenv(key, '')
                if secret:
                    value = value.replace(secret, '[REDACTED]')
            return self.wrapped.write(value)
        def __getattr__(self, name):
            return getattr(self.wrapped, name)
    sys.stdout = RedactedStream(sys.stdout)
    sys.stderr = RedactedStream(sys.stderr)
    if os.getenv('AGENTOPS_OFFLINE') == '1':
        # Cover both transports used in the pinned SDK and its RAG client.
        import httpx
        import httpx2

        def restrict(module):
            original_sync, original_async = module.Client.send, module.AsyncClient.send

            def require_loopback(request):
                if request.url.host not in ('127.0.0.1', 'localhost', '::1'):
                    raise module.ConnectError('External HTTP blocked in offline validation', request=request)

            def send(client, request, *args, **kwargs):
                require_loopback(request)
                return original_sync(client, request, *args, **kwargs)

            async def asend(client, request, *args, **kwargs):
                require_loopback(request)
                return await original_async(client, request, *args, **kwargs)

            module.Client.send, module.AsyncClient.send = send, asend

        restrict(httpx)
        restrict(httpx2)
    import uvicorn
    uvicorn.run('main:app', host='127.0.0.1', port=int(os.environ['API_PORT']),
                workers=1, access_log=False, log_level='info')


def backup(values):
    record = process_record()
    if record:
        stop_api()
    target = ROOT / 'backups' / datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S')
    target.mkdir(parents=True, mode=0o700)
    try:
        with (target / 'postgres.dump').open('xb') as out:
            os.chmod(out.name, 0o600)
            compose(values, 'exec', '-T', 'postgres', 'pg_dump', '-U', values['POSTGRES_USER'],
                    '-d', values['POSTGRES_DB'], '-Fc', stdout=out)
        with tarfile.open(target / 'files.tar.gz', 'w:gz') as archive:
            data = Path(values['AGENTOPS_DATA_DIR'])
            if data.exists():
                for path in data.rglob('*'):
                    if path.is_symlink():
                        raise RuntimeError('Backup refuses symlinks in deployment data')
                archive.add(data, arcname='data')
            for name in ('documents', 'vector.index', 'metadata.json', 'embedding_store.pkl', 'bm25_store.pkl'):
                if (ROOT / name).exists():
                    archive.add(ROOT / name, arcname='knowledge/' + name)
        checksums = []
        for path in sorted(target.iterdir()):
            checksums.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
        private_write(target / 'SHA256SUMS', '\n'.join(checksums) + '\n')
        print('Backup complete: ' + str(target) + ' (database + memory/trace + knowledge; secrets/models excluded)')
    finally:
        if record:
            start_api(values, record['offline'])


def main():
    os.chdir(ROOT)
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'up', 'status', 'logs', 'stop', 'health',
                                           'backup', 'compose', 'index', 'test', 'package', 'acceptance', '_serve'])
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == '_serve':
        serve()
        return
    STATE.mkdir(exist_ok=True, mode=0o700)
    with (STATE / 'control.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == 'init':
            initialize()
            return
        if args.command in ('test', 'package'):
            script = 'run_tests.py' if args.command == 'test' else 'package_release.py'
            subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args.args], check=True)
            return
        values = configuration()
        if args.command == 'index':
            if args.args or process_record():
                raise RuntimeError('Run index with the managed API stopped and no extra arguments')
            env = {**os.environ, **values, 'AGENTOPS_OFFLINE': '1',
                   'DEEPSEEK_API_KEY': 'offline-index-placeholder'}
            subprocess.run([sys.executable, str(ROOT / 'ingest.py')], cwd=ROOT, env=env, check=True)
        elif args.command == 'up':
            if any(arg != '--offline' for arg in args.args):
                raise RuntimeError('up supports only --offline')
            preflight(values, '--offline' in args.args)
            compose(values, 'up', '-d', '--build', '--wait', '--wait-timeout', '120')
            start_api(values, '--offline' in args.args)
        elif args.command == 'stop':
            stop_api()
            compose(values, 'stop')
            print('Services stopped; named PostgreSQL volume and host data retained.')
        elif args.command == 'status':
            compose(values, 'ps', '-a')
            record = process_record()
            print('Managed API: ' + ('running, pid=' + str(record['pid']) if record else 'stopped'))
        elif args.command == 'health':
            check_health(values)
        elif args.command == 'logs':
            if args.args == ['api']:
                if LOG_FILE.exists():
                    print('\n'.join(LOG_FILE.read_text(errors='replace').splitlines()[-100:]))
            elif not args.args:
                compose(values, 'logs', '--tail', '80')
            else:
                raise RuntimeError('Use logs or logs api')
        elif args.command == 'backup':
            backup(values)
        elif args.command == 'acceptance':
            subprocess.run([sys.executable, str(ROOT / 'scripts/deployment_probe.py'), *args.args],
                           env={**os.environ, **values}, cwd=ROOT, check=True)
        elif args.command == 'compose':
            # Deliberate allowlist: no down/rm/prune or arbitrary mutations through this wrapper.
            if not args.args or args.args[0] not in ('config', 'build', 'ps', 'logs', 'images', 'version'):
                raise RuntimeError('Supported compose commands: config/build/ps/logs/images/version')
            compose(values, *args.args)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        # Avoid exception payloads which can contain DSNs/passwords from third-party libraries.
        if isinstance(error, RuntimeError):
            print('ERROR: ' + str(error), file=sys.stderr)
        else:
            print('ERROR: ' + type(error).__name__ + '; inspect service status and private logs.', file=sys.stderr)
        raise SystemExit(1)
