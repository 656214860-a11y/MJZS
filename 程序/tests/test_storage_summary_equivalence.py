"""压平 storage_maintenance.storage_summary：旧实现原样内嵌，在多种项目布局上逐例对照完整盘点结果。

storage_summary 只读盘，所以旧、新两次调用落在同一份夹具上。"""
import json
import tempfile
import unittest
from pathlib import Path

import storage_maintenance as sm
from agent.core import file_hash, save
from engine import adopted_edit_version

LEGACY_SRC = r'''def _legacy_storage_summary(root, now=None, select_adopted=None):
    """只读盘点；未发现引用不等于可删除，同盘回收不等于释放容量。"""
    root = Path(root).resolve()
    now = time.time() if now is None else now
    protected, errors = source_protection(root, now)
    sizes = {'protected': 0, 'unclassified': 0, 'recycled': 0}
    file_sizes = {}
    for path in root.rglob('*'):
        if path.is_symlink() or path.is_junction() or not _within(path, root):
            continue
        try:
            if not path.is_file():
                continue
            key = 'recycled' if _within(path, _recycle_base(root)) else 'protected' if path.resolve() in protected else 'unclassified'
            file_sizes[path.resolve()] = path.stat().st_size
            sizes[key] += file_sizes[path.resolve()]
        except OSError as exc:
            errors.append(str(path.relative_to(root)) + '：' + str(exc))
    try:
        retention = retention_seconds(root)
    except (OSError, ValueError):
        retention = None
    versions, candidate_files, adopted_files, other_files = [], set(), set(), set()
    referenced, digests = edit_source_versions(root)
    if not errors and retention is not None:
        for ledger in list(root.glob('**/data/state.json')) + list(root.glob('**/06_本地生成/state.json')):
            if not _within(ledger, root) or _within(ledger, _recycle_base(root)):
                continue
            try:
                state = read_json(ledger)
                for shot, rows in state['shots'].items():
                    newest = max((v.get('version', 0) for v in rows), default=0)
                    adopted = select_adopted(rows, ledger.parent.parent)[0] if select_adopted else None
                    for version in rows:
                        if version.get('cleaned_at'):
                            continue
                        folder = _version_folder(root, ledger, shot, version)
                        reason = version_retention(version, shot, newest, referenced, digests, now, retention)
                        if folder is None:
                            versions.append({'shot': shot, 'version': version.get('version'), 'bytes': 0, 'reason': '生成目录无法安全定位', 'candidate': False})
                            continue
                        files = {p for p in file_sizes if p.is_relative_to(folder)}
                        if not reason and any(p == folder or p.is_relative_to(folder) for p in protected):
                            reason = '来源或授权资料仍被引用'
                        if not reason:
                            candidate_files.update(files)
                        (adopted_files if version is adopted else other_files).update(files)
                        versions.append({'shot': shot, 'version': version.get('version'), 'bytes': sum(file_sizes[p] for p in files),
                                         'reason': RETAIN_REASONS.get(reason, reason) or VERSION_CLEAN_REASON,
                                         'candidate': not bool(reason), 'adopted': version is adopted if select_adopted else None})
            except (OSError, ValueError, TypeError, KeyError) as exc:
                errors.append(str(ledger.relative_to(root)) + '：' + str(exc))
    return {'bytes': sizes, 'errors': errors, 'retention_days': retention // 86400 if retention else None,
            'versions': versions, 'recyclable_bytes': sum(file_sizes[p] for p in candidate_files) if not errors else None,
            'adopted_bytes': sum(file_sizes[p] for p in adopted_files) if select_adopted and not errors else None,
            'other_version_bytes': sum(file_sizes[p] for p in other_files - adopted_files) if select_adopted and not errors else None,
            'immediately_released_bytes': 0}
'''

NOW = 1700000000
DAY = 86400


def _version(root, base, shot, number, content, **extra):
    path = base / shot / ('v%03d' % number) / 'video.mp4'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    row = {'version': number, 'state': 'downloaded', 'created': NOW - 10 * DAY, 'review': 'reject',
           'qc_pass': True, 'file': path.relative_to(root).as_posix(), 'sha256': file_hash(path)}
    row.update(extra)
    return row


def _project(td, retention=7, layout='data'):
    root = Path(td) / 'project'
    root.mkdir()
    save(root / 'config.json', {})
    save(root / 'storage_policy.json', {'retention_days': retention})
    base = root / layout
    shots = {
        'S01': [_version(root, base, 'S01', 1, b'old'), _version(root, base, 'S01', 2, b'adopted!', review='pass')],
        'S02': [_version(root, base, 'S02', 1, b'cleaned', cleaned_at=NOW - DAY),
                _version(root, base, 'S02', 2, b'fresh', created=NOW - DAY)],
        'S03': [{'version': 1, 'file': '../outside/video.mp4'}, _version(root, base, 'S03', 2, b'x' * 11)],
        'S04': [],
    }
    save(base / 'state.json', {'shots': shots})
    return root


def f_basic(td):
    return _project(td)


def f_long_retention(td):
    return _project(td, retention=30)


def f_bad_retention(td):
    return _project(td, retention=0)


def f_local_generation_layout(td):
    return _project(td, layout='06_本地生成')


def f_corrupt_ledger(td):
    root = _project(td)
    save(root / 'other' / 'data' / 'state.json', {'no_shots': True})
    return root


def f_ledger_rows_not_list(td):
    root = _project(td)
    save(root / 'other' / 'data' / 'state.json', {'shots': {'S09': 5}})
    return root


def f_recycled_ledger_is_ignored(td):
    root = _project(td)
    save(sm.recycle_base(root) / 'batch' / 'data' / 'state.json', {'no_shots': True})
    (sm.recycle_base(root) / 'batch' / 'junk.bin').write_bytes(b'12345')
    return root


def f_referenced_source(td):
    root = _project(td)
    history = root / '历史版本'
    history.mkdir()
    (history / '授权.txt').write_text('proof', encoding='utf-8')
    (root / 'delivery.commercial.json').write_text(
        json.dumps({'authorization': {'file': 'data/S01/v001/video.mp4'}}), encoding='utf-8')
    return root


def f_corrupt_manifest(td):
    root = _project(td)
    (root / 'assets.json').write_text('{bad', encoding='utf-8')
    return root


def f_empty(td):
    root = Path(td) / 'project'
    root.mkdir()
    save(root / 'config.json', {})
    return root


FIXTURES = [value for key, value in sorted(globals().items()) if key.startswith('f_')]


class StorageSummaryEquivalence(unittest.TestCase):
    def setUp(self):
        namespace = dict(vars(sm))
        exec(compile(LEGACY_SRC, 'legacy_storage_summary', 'exec'), namespace)
        self.legacy = namespace['_legacy_storage_summary']

    def test_every_layout_matches(self):
        versions = candidates = 0
        for fixture in FIXTURES:
            for select in (None, adopted_edit_version):
                with tempfile.TemporaryDirectory() as td:
                    root = fixture(td)
                    old = self.legacy(root, NOW, select)
                    new = sm.storage_summary(root, NOW, select)
                    self.assertEqual(new, old, (fixture.__name__, select))
                    versions += len(new['versions'])
                    candidates += sum(1 for row in new['versions'] if row['candidate'])
        # 对照不能是空对空：确实盘点出了版本，也确实有可回收的候选
        self.assertGreater(versions, 40)
        self.assertGreater(candidates, 3)


if __name__ == '__main__':
    unittest.main()
