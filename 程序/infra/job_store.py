"""Durable per-project job store (I19, L1-H5).

One sqlite file per project under ``data/job_store/<sha256(root)>.sqlite`` in
WAL mode. State transitions commit atomically; a crash between commits leaves
the last committed state, and jobs abandoned in ``running`` are demoted to
``retrying`` on the next open.
"""
import hashlib
import json
import sqlite3
import threading
import time
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

_SCHEMA = (
    'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);'
    'CREATE TABLE IF NOT EXISTS jobs('
    ' id INTEGER PRIMARY KEY,'
    ' key TEXT NOT NULL UNIQUE,'
    ' kind TEXT NOT NULL,'
    ' payload TEXT,'
    ' state TEXT NOT NULL,'
    ' attempts INTEGER NOT NULL DEFAULT 0,'
    ' last_try REAL,'
    ' next_try REAL,'
    ' checkpoint TEXT,'
    ' digest TEXT,'
    ' created_at REAL NOT NULL,'
    ' updated_at REAL NOT NULL);'
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
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.executescript(_SCHEMA)
        now = time.time()
        self._conn.execute(
            "UPDATE jobs SET state=?, updated_at=? WHERE state=?",
            (RETRYING, now, RUNNING))
        self._conn.execute(
            'INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)',
            ('project_root', str(self.project)))
        self._conn.commit()

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

    def _row(self, where, arg):
        row = self._conn.execute(
            'SELECT id, key, kind, payload, state, attempts, last_try,'
            ' next_try, checkpoint, digest, created_at, updated_at'
            ' FROM jobs WHERE ' + where, (arg,)).fetchone()
        return dict(zip(self._KEYS, row)) if row else None

    def enqueue(self, key, kind, *, payload=None):
        """Idempotent enqueue: an existing key returns its job unchanged."""
        key = str(key)
        with self._lock:
            existing = self._row('key=?', key)
            if existing is not None:
                return existing
            now = time.time()
            cur = self._conn.execute(
                'INSERT INTO jobs(key, kind, payload, state, attempts,'
                ' created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)',
                (key, str(kind),
                 json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                 QUEUED, now, now))
            self._conn.commit()
            return self._row('id=?', int(cur.lastrowid))

    def get(self, job_id):
        with self._lock:
            row = self._row('id=?', int(job_id))
            if row is None:
                raise ConfigError('作业库无此条目：%s' % job_id)
            return row

    def by_key(self, key):
        with self._lock:
            return self._row('key=?', str(key))

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
        with self._lock:
            row = self._row('id=?', int(job_id))
            if row is None:
                raise ConfigError('作业库无此条目：%s' % job_id)
            if state not in _TRANSITIONS[row['state']]:
                raise ConfigError(
                    '非法作业状态迁移：%s → %s' % (row['state'], state))
            self._conn.execute(
                'UPDATE jobs SET state=?, updated_at=? WHERE id=?',
                (state, time.time(), int(job_id)))
            self._conn.commit()
            return dict(row, state=state)

    def note_attempt(self, job_id, *, step=60.0, limit=None, at=None):
        """Record one failed attempt: attempts+1, backoff ``step*attempts``.

        Reaching ``limit`` marks the job ``stopped`` with no next_try.
        """
        at = time.time() if at is None else float(at)
        with self._lock:
            row = self._row('id=?', int(job_id))
            if row is None:
                raise ConfigError('作业库无此条目：%s' % job_id)
            tries = int(row['attempts']) + 1
            stopped = limit is not None and tries >= limit
            state = STOPPED if stopped else RETRYING
            next_try = None if stopped else at + float(step) * tries
            self._conn.execute(
                'UPDATE jobs SET attempts=?, last_try=?, next_try=?,'
                ' state=?, updated_at=? WHERE id=?',
                (tries, at, next_try, state, at, int(job_id)))
            self._conn.commit()
            return self._row('id=?', int(job_id))

    def checkpoint(self, job_id, data, *, digest=None):
        """Persist a resumption checkpoint (JSON) with optional digest."""
        with self._lock:
            row = self._row('id=?', int(job_id))
            if row is None:
                raise ConfigError('作业库无此条目：%s' % job_id)
            self._conn.execute(
                'UPDATE jobs SET checkpoint=?, digest=?, updated_at=? WHERE id=?',
                (json.dumps(data, ensure_ascii=False), digest,
                 time.time(), int(job_id)))
            self._conn.commit()
            return self._row('id=?', int(job_id))

    def mirror(self, key, kind, *, attempts, next_try, state):
        """Upsert for ledger dual-write pilots: force the row to ledger values."""
        state = str(state)
        if state not in STATES:
            raise ConfigError('未知作业状态：%s' % state)
        with self._lock:
            now = time.time()
            self._conn.execute(
                'INSERT INTO jobs(key, kind, state, attempts, next_try,'
                ' created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)'
                ' ON CONFLICT(key) DO UPDATE SET kind=excluded.kind,'
                ' state=excluded.state, attempts=excluded.attempts,'
                ' next_try=excluded.next_try, updated_at=excluded.updated_at',
                (str(key), str(kind), state, int(attempts),
                 next_try, now, now))
            self._conn.commit()
            return self._row('key=?', str(key))

    def reconcile(self, ledger, *, state_map=None):
        """Diff this store against a legacy ledger mapping.

        ``ledger`` is ``{key: {attempts, next_try, state}}``; ``state_map``
        translates ledger states to job states (default: identity). Returns
        ``{missing_in_store, missing_in_ledger, field_diffs}``.
        """
        state_map = state_map or {}
        with self._lock:
            jobs = {row['key']: row for row in self._conn.execute(
                'SELECT key, attempts, next_try, state FROM jobs').fetchall()
                for row in [dict(zip(('key', 'attempts', 'next_try', 'state'), row))]}
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
