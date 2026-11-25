"""Durable per-project job store (I19, L1-H5).

One sqlite file per project under ``data/job_store/<sha256(root)>.sqlite`` in
WAL mode. Readers never reclaim work. Workers renew their running lease;
an explicit recovery pass requeues jobs whose lease has expired.
"""
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from contract.infra_errors import ConfigError

__all__ = ['open_store', 'store_path', 'JobStore',
           'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'RETRYING', 'STOPPED', 'STATES']

PROGRAM = Path(__file__).resolve().parents[1]
DIR = PROGRAM / 'data' / 'job_store'

QUEUED = 'queued'
RUNNING = 'running'
SUCCEEDED = 'succeeded'
FAILED = 'failed'
RETRYING = 'retrying'
STOPPED = 'stopped'
STATES = (QUEUED, RUNNING, SUCCEEDED, FAILED, RETRYING, STOPPED)

_TRANSITIONS = {
    QUEUED: (RUNNING,),
    RUNNING: (SUCCEEDED, FAILED, RETRYING),
    RETRYING: (RUNNING, STOPPED),
    FAILED: (RETRYING,),
    STOPPED: (RETRYING,),
    SUCCEEDED: (),
}

LEASE_SECONDS = 300

_JOBS = (
    'CREATE TABLE IF NOT EXISTS jobs('
    ' id INTEGER PRIMARY KEY,'
    ' key TEXT NOT NULL,'
    ' kind TEXT NOT NULL,'
    ' payload TEXT,'
    ' state TEXT NOT NULL,'
    ' attempts INTEGER NOT NULL DEFAULT 0,'
    ' last_try REAL,'
    ' next_try REAL,'
    ' checkpoint TEXT,'
    ' digest TEXT,'
    ' created_at REAL NOT NULL,'
    ' updated_at REAL NOT NULL, lease_owner TEXT, lease_until REAL, UNIQUE(kind,key));'
)


def store_path(project):
    """Store file for a project root; always outside the project directory."""
    root = str(Path(project).resolve())
    digest = hashlib.sha256(root.encode('utf-8')).hexdigest()[:16]
    return DIR / ('%s.sqlite' % digest)


class JobStore:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self._path = store_path(self.project)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._owner = uuid.uuid4().hex
        self._claims = set()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute('PRAGMA journal_mode=WAL')
        with self._write():
            self._conn.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)')
            self._conn.execute(_JOBS)
            if 'lease_owner' not in {row[1] for row in self._conn.execute('PRAGMA table_info(jobs)')}:
                self._conn.execute('ALTER TABLE jobs RENAME TO jobs_legacy')
                self._conn.execute(_JOBS)
                names = ', '.join(self._KEYS)
                self._conn.execute(f'INSERT INTO jobs({names}) SELECT {names} FROM jobs_legacy')
                self._conn.execute('DROP TABLE jobs_legacy')
            self._conn.execute('INSERT OR IGNORE INTO meta(key,value) VALUES (?,?)',
                               ('project_root', str(self.project)))

    @contextmanager
    def _write(self):
        with self._lock, self._conn:
            self._conn.execute('BEGIN IMMEDIATE')
            yield

    def close(self):
        with self._lock:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    _KEYS = ('id', 'key', 'kind', 'payload', 'state', 'attempts',
             'last_try', 'next_try', 'checkpoint', 'digest',
             'created_at', 'updated_at')

    def _row(self, where, *args):
        row = self._conn.execute(
            'SELECT id, key, kind, payload, state, attempts, last_try,'
            ' next_try, checkpoint, digest, created_at, updated_at'
            ' FROM jobs WHERE ' + where, args).fetchone()
        return dict(zip(self._KEYS, row)) if row else None

    def enqueue(self, key, kind, *, payload=None):
        """Idempotently enqueue a key within its job kind."""
        key = str(key)
        with self._write():
            existing = self._row('key=? AND kind=?', key, str(kind))
            if existing is not None:
                return existing
            now = time.time()
            cur = self._conn.execute(
                'INSERT INTO jobs(key, kind, payload, state, attempts,'
                ' created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)',
                (key, str(kind),
                 json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                 QUEUED, now, now))
            return self._row('id=?', int(cur.lastrowid))

    def get(self, job_id):
        with self._lock:
            row = self._row('id=?', int(job_id))
            if row is None:
                raise ConfigError('作业库无此条目：%s' % job_id)
            return row

    def by_key(self, key, *, kind=None):
        with self._lock:
            if kind is not None:
                return self._row('key=? AND kind=?', str(key), str(kind))
            rows = self._conn.execute('SELECT ' + ', '.join(self._KEYS) + ' FROM jobs WHERE key=? LIMIT 2',
                                      (str(key),)).fetchall()
            if len(rows) > 1:
                raise ConfigError('多类作业共用编号，请指定作业类型')
            return dict(zip(self._KEYS, rows[0])) if rows else None

    def list(self, state=None):
        with self._lock:
            if state is None:
                rows = self._conn.execute(
                    'SELECT id, key, kind, payload, state, attempts, last_try,'
                    ' next_try, checkpoint, digest, created_at, updated_at'
                    ' FROM jobs ORDER BY id').fetchall()
            else:
                rows = self._conn.execute(
                    'SELECT id, key, kind, payload, state, attempts, last_try,'
                    ' next_try, checkpoint, digest, created_at, updated_at'
                    ' FROM jobs WHERE state=? ORDER BY id',
                    (str(state),)).fetchall()
            return [dict(zip(self._KEYS, row)) for row in rows]

    def transition(self, job_id, state):
        """Move a job to ``state``; illegal moves raise ``ConfigError``."""
        state = str(state)
        if state not in STATES:
            raise ConfigError('未知作业状态：%s' % state)
        with self._write():
            row = self._row('id=?', int(job_id))
            if row is None:
                raise ConfigError('作业库无此条目：%s' % job_id)
            if state not in _TRANSITIONS[row['state']]:
                raise ConfigError(
                    '非法作业状态迁移：%s → %s' % (row['state'], state))
            if state != RUNNING:
                self._check_running_owner(job_id)
            self._conn.execute(
                'UPDATE jobs SET state=?, updated_at=?, lease_owner=?, lease_until=? WHERE id=?',
                (state, time.time(), self._owner if state == RUNNING else None,
                 time.time() + LEASE_SECONDS if state == RUNNING else None, int(job_id)))
            if state == RUNNING:
                self._claims.add(int(job_id))
            else:
                self._claims.discard(int(job_id))
            return dict(row, state=state)

    def _check_running_owner(self, job_id):
        row = self._conn.execute('SELECT lease_owner, lease_until FROM jobs WHERE id=? AND state=?',
                                 (int(job_id), RUNNING)).fetchone()
        if ((row and (row[0] != self._owner or row[1] is None or row[1] <= time.time()))
                or (row is None and int(job_id) in self._claims)):
            raise ConfigError('当前连接未持有此作业的有效运行租约')

    def renew_lease(self, job_id):
        """Extend this worker's unexpired lease."""
        now = time.time()
        with self._write():
            updated = self._conn.execute(
                'UPDATE jobs SET lease_until=? WHERE id=? AND state=? AND lease_owner=? AND lease_until>?',
                (now + LEASE_SECONDS, int(job_id), RUNNING, self._owner, now))
            if not updated.rowcount:
                raise ConfigError('当前连接未持有此作业的有效运行租约')

    def recover_expired(self, *, confirmed_legacy_ids=()):
        """Requeue expired leases. Pass legacy IDs only after confirming their workers stopped."""
        now = time.time()
        with self._write():
            expired = self._conn.execute(
                'UPDATE jobs SET state=?, updated_at=?, lease_owner=NULL, lease_until=NULL'
                ' WHERE state=? AND lease_until<=?', (RETRYING, now, RUNNING, now)).rowcount
            old = self._conn.executemany(
                'UPDATE jobs SET state=?, updated_at=? WHERE id=? AND state=?'
                ' AND lease_owner IS NULL AND lease_until IS NULL',
                [(RETRYING, now, int(jid), RUNNING) for jid in confirmed_legacy_ids])
            return expired + old.rowcount

    def note_attempt(self, job_id, *, step=60.0, limit=None, at=None):
        """Record one failed attempt: attempts+1, backoff ``step*attempts``.

        Reaching ``limit`` marks the job ``stopped`` with no next_try.
        """
        at = time.time() if at is None else float(at)
        with self._write():
            row = self._row('id=?', int(job_id))
            self._check_running_owner(job_id)
            if row is None:
                raise ConfigError('作业库无此条目：%s' % job_id)
            tries = int(row['attempts']) + 1
            stopped = limit is not None and tries >= limit
            state = STOPPED if stopped else RETRYING
            next_try = None if stopped else at + float(step) * tries
            self._conn.execute(
                'UPDATE jobs SET attempts=?, last_try=?, next_try=?,'
                ' state=?, updated_at=?, lease_owner=NULL, lease_until=NULL WHERE id=?',
                (tries, at, next_try, state, at, int(job_id)))
            self._claims.discard(int(job_id))
            return self._row('id=?', int(job_id))

    def checkpoint(self, job_id, data, *, digest=None):
        """Persist a resumption checkpoint (JSON) with optional digest."""
        with self._write():
            row = self._row('id=?', int(job_id))
            self._check_running_owner(job_id)
            if row is None:
                raise ConfigError('作业库无此条目：%s' % job_id)
            self._conn.execute(
                'UPDATE jobs SET checkpoint=?, digest=?, updated_at=? WHERE id=?',
                (json.dumps(data, ensure_ascii=False), digest,
                 time.time(), int(job_id)))
            return self._row('id=?', int(job_id))

    def mirror(self, key, kind, *, attempts, next_try, state):
        """Upsert for ledger dual-write pilots: force the row to ledger values."""
        state = str(state)
        if state not in STATES:
            raise ConfigError('未知作业状态：%s' % state)
        with self._write():
            self._mirror(key, kind, attempts, next_try, state)
            return self._row('key=? AND kind=?', str(key), str(kind))

    def _mirror(self, key, kind, attempts, next_try, state):
        now = time.time()
        self._conn.execute(
            'INSERT INTO jobs(key, kind, state, attempts, next_try, created_at, updated_at)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(kind,key) DO UPDATE SET'
            ' state=excluded.state, attempts=excluded.attempts, next_try=excluded.next_try,'
            ' updated_at=excluded.updated_at, lease_owner=NULL, lease_until=NULL',
            (str(key), str(kind), state, int(attempts), next_try, now, now))

    def sync_mirror(self, kind, entries):
        """Replace one ledger's active snapshot atomically; retain completed history."""
        with self._write():
            active = self._conn.execute('SELECT id,key FROM jobs WHERE kind=? AND state<>?',
                                        (kind, SUCCEEDED)).fetchall()
            self._conn.executemany(
                'UPDATE jobs SET state=?, next_try=NULL, updated_at=?, lease_owner=NULL, lease_until=NULL WHERE id=?',
                [(SUCCEEDED, time.time(), jid) for jid, key in active if key not in entries])
            for key, entry in entries.items():
                self._mirror(key, kind, entry['attempts'], entry['next_try'], entry['state'])

    def reconcile(self, ledger, *, state_map=None, kind=None):
        """Diff this store against a legacy ledger mapping.

        ``ledger`` is ``{key: {attempts, next_try, state}}``; ``state_map``
        translates ledger states to job states (default: identity). Returns
        ``{missing_in_store, missing_in_ledger, field_diffs}``.
        """
        state_map = state_map or {}
        query = 'SELECT key, attempts, next_try, state FROM jobs'
        with self._lock:
            rows = (self._conn.execute(query) if kind is None else
                    self._conn.execute(query + ' WHERE kind=?', (kind,))).fetchall()
        jobs = {row[0]: dict(zip(('key', 'attempts', 'next_try', 'state'), row)) for row in rows
                if kind is None or row[3] != SUCCEEDED or row[0] in ledger}
        if kind is None and len(jobs) != len(rows):
            raise ConfigError('对账中存在同名作业，请指定作业类型')
        missing_in_store = [k for k in ledger if k not in jobs]
        missing_in_ledger = [k for k in jobs if k not in ledger]
        diffs = {}
        for key in set(ledger) & set(jobs):
            want = ledger[key] or {}
            got = jobs[key]
            for field in ('attempts', 'next_try'):
                if want.get(field) != got.get(field):
                    diffs.setdefault(key, {})[field] = {
                        'ledger': want.get(field), 'store': got.get(field)}
            want_state = state_map.get(want.get('state'), want.get('state'))
            if want.get('state') is not None and want_state != got.get('state'):
                diffs.setdefault(key, {})['state'] = {
                    'ledger': want.get('state'), 'store': got.get('state')}
        return {'missing_in_store': sorted(missing_in_store),
                'missing_in_ledger': sorted(missing_in_ledger),
                'field_diffs': diffs}


def open_store(project):
    return JobStore(project)
