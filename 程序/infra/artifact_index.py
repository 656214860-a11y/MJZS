"""Per-project artifact index (L1-H4).

Each project gets ``data/artifact_index/<sha256(project-root)>.sqlite`` in WAL
mode. The index never writes into the user project directory; loss or damage is
repaired by ``rebuild`` on a background executor.
"""
import hashlib
import sqlite3
import threading
import time
from pathlib import Path

from contract.infra_errors import ConfigError, StorageError
from infra import executors
from infra.file_cache import file_digest

__all__ = ['open_index', 'index_path', 'ArtifactIndex',
           'CANDIDATE', 'ADOPTED', 'ARCHIVED', 'RECYCLED', 'STATES']

PROGRAM = Path(__file__).resolve().parents[1]
DIR = PROGRAM / 'data' / 'artifact_index'

CANDIDATE = '候选'
ADOPTED = '采用'
ARCHIVED = '归档'
RECYCLED = '回收'
STATES = (CANDIDATE, ADOPTED, ARCHIVED, RECYCLED)

_TRANSITIONS = {
    CANDIDATE: (ADOPTED, RECYCLED),
    ADOPTED: (ARCHIVED,),
    ARCHIVED: (RECYCLED,),
    RECYCLED: (CANDIDATE,),
}

_SCHEMA = (
    'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);'
    'CREATE TABLE IF NOT EXISTS artifacts('
    ' id INTEGER PRIMARY KEY,'
    ' path TEXT NOT NULL UNIQUE,'
    ' logical_id INTEGER NOT NULL,'
    ' stage TEXT NOT NULL,'
    ' kind TEXT NOT NULL,'
    ' digest TEXT NOT NULL,'
    ' state TEXT NOT NULL,'
    ' at REAL NOT NULL);'
    'CREATE TABLE IF NOT EXISTS parents('
    ' child INTEGER NOT NULL REFERENCES artifacts(id), parent INTEGER NOT NULL REFERENCES artifacts(id),'
    ' PRIMARY KEY(child, parent));'
)

_MEDIA_SUFFIXES = frozenset({
    '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif',
    '.mp4', '.mov', '.avi', '.mkv', '.webm',
    '.mp3', '.wav', '.aac', '.flac', '.m4a',
})


def index_path(project):
    """Index file for a project root; always outside the project directory."""
    root = str(Path(project).resolve())
    digest = hashlib.sha256(root.encode('utf-8')).hexdigest()[:16]
    return DIR / ('%s.sqlite' % digest)


def _digest_of(path):
    try:
        return file_digest(path)
    except OSError:
        return ''


def _scan_media(root):
    root = Path(root)
    found = []
    for path in sorted(root.rglob('*')):
        try:
            if path.is_file() and path.suffix.lower() in _MEDIA_SUFFIXES:
                found.append(path)
        except OSError:
            continue
    return found


def _upgrade_lineage(conn):
    """Migrate old indexes without guessing which file a missing parent represented."""
    if conn.execute('PRAGMA foreign_key_list(parents)').fetchone():
        return
    conn.execute('ALTER TABLE parents RENAME TO legacy_parents')
    conn.execute('CREATE TABLE parents(child INTEGER NOT NULL REFERENCES artifacts(id),'
                 ' parent INTEGER NOT NULL REFERENCES artifacts(id), PRIMARY KEY(child,parent))')
    conn.execute('INSERT INTO parents SELECT p.child,p.parent FROM legacy_parents p'
                 ' JOIN artifacts c ON c.id=p.child JOIN artifacts a ON a.id=p.parent')
    # Keep the unresolved pairs for inspection; active lineage contains only live references.
    conn.execute('DELETE FROM legacy_parents WHERE (child,parent) IN (SELECT child,parent FROM parents)')
    conn.execute('ALTER TABLE legacy_parents RENAME TO orphaned_parents')
    conn.execute('CREATE TABLE orphaned_roots AS SELECT logical_id AS lost_id, MIN(id) AS surviving_id'
                 ' FROM artifacts WHERE logical_id NOT IN (SELECT id FROM artifacts) GROUP BY logical_id')
    conn.execute('UPDATE artifacts SET logical_id=(SELECT surviving_id FROM orphaned_roots'
                 ' WHERE lost_id=artifacts.logical_id) WHERE logical_id IN (SELECT lost_id FROM orphaned_roots)')


class ArtifactIndex:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self._path = index_path(self.project)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.execute('PRAGMA foreign_keys=ON')
        self._conn.executescript(_SCHEMA)
        with self._conn:
            self._conn.execute('BEGIN IMMEDIATE')
            _upgrade_lineage(self._conn)
        self._conn.execute(
            'INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)',
            ('project_root', str(self.project)))
        self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def register(self, path, *, stage, kind, parents=()):
        """Register an artifact file; returns its id (state 候选)."""
        target = Path(path).resolve()
        digest = _digest_of(target)
        parent_ids = tuple(dict.fromkeys(int(pid) for pid in parents))
        with self._lock, self._conn:
            self._conn.execute('BEGIN IMMEDIATE')
            existing = self._conn.execute('SELECT id FROM artifacts WHERE path=?', (str(target),)).fetchone()
            if existing:
                aid = existing[0]
                if parent_ids:
                    stored = self._conn.execute('SELECT parent FROM parents WHERE child=?', (aid,))
                    if set(parent_ids) != {row[0] for row in stored}:
                        raise ConfigError('同路径产物不能替换已有版本关系')
                self._conn.execute('UPDATE artifacts SET stage=?,kind=?,digest=?,state=? WHERE id=?',
                                   (str(stage), str(kind), digest, CANDIDATE, aid))
                return aid
            logical = self._row(parent_ids[0])['logical_id'] if parent_ids else 0
            cur = self._conn.execute(
                'INSERT INTO artifacts(path,logical_id,stage,kind,digest,state,at) VALUES (?,?,?,?,?,?,?)',
                (str(target), logical, str(stage), str(kind), digest, CANDIDATE, time.time()))
            aid = cur.lastrowid
            if parent_ids:
                try:
                    self._conn.executemany('INSERT INTO parents(child,parent) VALUES (?,?)',
                                           [(aid, pid) for pid in parent_ids])
                except sqlite3.IntegrityError as exc:
                    raise ConfigError('产物版本的父节点不存在') from exc
            else:
                self._conn.execute('UPDATE artifacts SET logical_id=? WHERE id=?', (aid, aid))
            return aid

    def _row(self, artifact_id):
        row = self._conn.execute(
            'SELECT id, path, logical_id, stage, kind, digest, state, at'
            ' FROM artifacts WHERE id=?', (int(artifact_id),)).fetchone()
        if row is None:
            raise ConfigError('产物索引无此条目：%s' % artifact_id)
        keys = ('id', 'path', 'logical_id', 'stage', 'kind', 'digest', 'state', 'at')
        return dict(zip(keys, row))

    def get(self, artifact_id):
        with self._lock:
            return self._row(artifact_id)

    def versions(self, logical_id):
        """All versions sharing ``logical_id``, oldest first."""
        with self._lock:
            rows = self._conn.execute(
                'SELECT id, path, logical_id, stage, kind, digest, state, at'
                ' FROM artifacts WHERE logical_id=? ORDER BY at, id',
                (int(logical_id),)).fetchall()
        keys = ('id', 'path', 'logical_id', 'stage', 'kind', 'digest', 'state', 'at')
        return [dict(zip(keys, row)) for row in rows]

    def set_state(self, artifact_id, state):
        """Transition artifact state; illegal moves raise ``ConfigError``.

        Moving to 回收 routes the on-disk file through
        ``storage_maintenance.recycle_paths`` before the state is written.
        """
        state = str(state)
        if state not in STATES:
            raise ConfigError('未知产物状态：%s' % state)
        with self._lock:
            row = self._row(artifact_id)
            if state not in _TRANSITIONS[row['state']]:
                raise ConfigError(
                    '非法产物状态迁移：%s → %s' % (row['state'], state))
            if state == RECYCLED:
                target = Path(row['path'])
                if target.exists():
                    from infra.storage_maintenance import recycle_paths
                    if not recycle_paths(self.project, (target,), '产物索引回收'):
                        raise StorageError('产物未能安全移入项目回收站：%s' % target)
            self._conn.execute(
                'UPDATE artifacts SET state=?, at=? WHERE id=?',
                (state, time.time(), int(artifact_id)))
            self._conn.commit()
            return dict(row, state=state)

    def duplicates(self):
        """Groups of artifacts sharing the same non-empty content digest."""
        with self._lock:
            rows = self._conn.execute(
                'SELECT id, path, logical_id, stage, kind, digest, state, at'
                " FROM artifacts WHERE digest<>''"
                ' AND digest IN (SELECT digest FROM artifacts'
                " WHERE digest<>'' GROUP BY digest HAVING COUNT(*)>1)"
                ' ORDER BY digest, at, id').fetchall()
        keys = ('id', 'path', 'logical_id', 'stage', 'kind', 'digest', 'state', 'at')
        groups = {}
        for row in rows:
            groups.setdefault(row[5], []).append(dict(zip(keys, row)))
        return list(groups.values())

    def _revision(self):
        return self._conn.total_changes, self._conn.execute('PRAGMA data_version').fetchone()[0]

    def rebuild(self, *, executor=None):
        """Re-derive the index from the project tree on an executor (I10).

        Deterministic: media files are scanned in sorted order, each becomes a
        候选 entry with itself as logical root. Returns the entries written.
        """
        submit = executor or executors.submit
        with self._lock:
            revision = self._revision()
        def scan():
            return [(p.resolve(), _digest_of(p)) for p in _scan_media(self.project)]
        media = submit('io', scan).result()
        with self._lock, self._conn:
            self._conn.execute('BEGIN IMMEDIATE')
            if revision != self._revision():
                raise StorageError('扫描期间产物索引已修改，请重试重建')
            self._conn.execute('DELETE FROM parents')
            self._conn.execute('DELETE FROM artifacts')
            for target, digest in media:
                cur = self._conn.execute(
                    'INSERT INTO artifacts'
                    '(path, logical_id, stage, kind, digest, state, at)'
                    ' VALUES (?, 0, ?, ?, ?, ?, ?)',
                    (str(target), 'rebuild', target.suffix.lower().lstrip('.'),
                     digest, CANDIDATE, time.time()))
                self._conn.execute(
                    'UPDATE artifacts SET logical_id=? WHERE id=?',
                    (int(cur.lastrowid), int(cur.lastrowid)))
            rows = self._conn.execute(
                'SELECT id, path, logical_id, stage, kind, digest, state, at'
                ' FROM artifacts ORDER BY id').fetchall()
        keys = ('id', 'path', 'logical_id', 'stage', 'kind', 'digest', 'state', 'at')
        return [dict(zip(keys, row)) for row in rows]


def open_index(project):
    return ArtifactIndex(project)
