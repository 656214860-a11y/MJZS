"""storage_maintenance.source_protection 压平：旧实现原样内嵌，与新实现在各类夹具（含各种损坏输入）上逐例对照。"""
import json
import tempfile
import unittest
from pathlib import Path

import storage_maintenance as sm

LEGACY_SRC = r'''def _legacy_source_protection(root, now=None):
    """收集明确来源声明与其项目内文件；读坏的声明不能被解释为没有引用。"""
    root = Path(root).resolve()
    protected, errors = set(), []
    now = time.time() if now is None else now
    try:
        retention = retention_seconds(root)
    except (OSError, ValueError) as exc:
        return protected, [str(exc)]
    recycle = _recycle_base(root)
    names = {'episode.json', 'assets.json', *EXPORT_MANIFEST_NAMES}

    def collect(value, parent):
        if isinstance(value, dict):
            for child in value.values():
                collect(child, parent)
        elif isinstance(value, list):
            for child in value:
                collect(child, parent)
        elif isinstance(value, str) and value and len(value) < 1024:
            # 路径同时兼容项目根及清单目录；只保护确实存在的项目内文件。
            for base in (root, parent):
                try:
                    path = (base / value).resolve()
                    if path.is_relative_to(root) and path.is_file():
                        protected.add(path)
                except (OSError, ValueError):
                    continue

    referenced, digests = edit_source_versions(root)
    for path in root.rglob('*.json'):
        if not _within(path, root) or _within(path, recycle):
            continue
        ledger = path.name == 'state.json' and path.parent.name in ('data', '06_本地生成')
        if path.name not in names and '.commercial.' not in path.name and not ledger:
            continue
        protected.add(path.resolve())
        try:
            data = read_json(path)
            if not isinstance(data, (dict, list)):
                raise ValueError('来源声明不是对象或清单')
            if ledger:
                shots = data.get('shots') if isinstance(data, dict) else None
                if not isinstance(shots, dict):
                    raise ValueError('生成台账缺少镜头表')
                for shot, versions in shots.items():
                    if not isinstance(versions, list) or any(not isinstance(v, dict) for v in versions):
                        raise ValueError('生成版本列表无效')
                    numbers = [v.get('version', 0) for v in versions]
                    if any(type(number) is not int for number in numbers):
                        raise ValueError('生成版本编号无效')
                    newest = max(numbers, default=0)
                    for version in versions:
                        if version_retention(version, shot, newest, referenced, digests, now, retention):
                            collect(version, path.parent.parent)
                            folder = _version_folder(root, path, shot, version)
                            if folder is not None and (folder / 'assets_manifest.json').is_file():
                                protected.add((folder / 'assets_manifest.json').resolve())
                continue
            if path.name in EXPORT_MANIFEST_NAMES:
                rows = data.get('manifest') if isinstance(data, dict) else data
                if not isinstance(rows, list):
                    raise ValueError('成片来源清单缺失')
                if any(not isinstance(row, dict) or not row.get('shot') or
                       (not row.get('sha256') and type(row.get('version')) is not int) for row in rows):
                    raise ValueError('成片来源条目无法确认')
            collect(data, path.parent)
        except (OSError, ValueError) as exc:
            errors.append(str(path.relative_to(root)) + '：' + str(exc))
    # 只沿保留文件追踪旁证，不能把每个过期版本自己的清单变成永久保留理由。
    checked = set()
    while True:
        receipts = set()
        for path in protected:
            candidates = (path.with_name(path.name + '.source.json'),
                          path.parent / 'assets_manifest.json')
            if path.name == 'assets_manifest.json' or path.name.endswith('.source.json'):
                candidates += (path,)
            receipts.update(p.resolve() for p in candidates
                            if _within(p, root) and not _within(p, recycle) and p.is_file())
        pending = receipts - checked
        if not pending:
            break
        checked.update(pending)
        protected.update(pending)
        for path in sorted(pending):
            try:
                data = read_json(path)
                if not isinstance(data, dict):
                    raise ValueError('来源旁证不是对象')
                collect(data, path.parent)
            except (OSError, ValueError) as exc:
                errors.append(str(path.relative_to(root)) + '：' + str(exc))
    return protected, errors
'''

NOW = 1700000000
DAY = 86400


def _write(path, data, raw=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if raw else json.dumps(data, ensure_ascii=False), encoding='utf-8')


def _version(number, created_days_ago, **extra):
    row = {'version': number, 'state': 'downloaded', 'created': NOW - created_days_ago * DAY,
           'review': 'reject', 'file': 'data/S01/v%03d/video.mp4' % number}
    row.update(extra)
    return row


def _base(root):
    for name in ('adopted.mp4', 'frame.png', 'sub/a.png', 'other.bin'):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(b'x')
    _write(root / 'assets.json', {'file': 'adopted.mp4', 'nested': [{'p': 'sub/a.png'}, 'missing.png', 5, None],
                                  'long': 'y' * 1100, 'up': '../outside.txt', 'dir': 'sub'})
    _write(root / 'adopted.mp4.source.json', {'ref': 'frame.png', 'again': 'other.bin'})
    _write(root / 'episode.json', {'frame': 'frame.png'})
    _write(root / 'clip.commercial.v1.json', {'media': 'sub/a.png'})
    _write(root / 'other' / 'state.json', {'shots': {}})
    from project_stages import exports
    _write(exports(root) / 'edit_bundle.json', {'manifest': [{'shot': 'S01', 'version': 2, 'sha256': 'abc'},
                                                             {'shot': 'S01', 'sha256': 'def'}]})
    rows = []
    for number, ago in ((1, 40), (2, 40), (3, 1), (4, 40)):
        video = root / 'data' / 'S01' / ('v%03d' % number) / 'video.mp4'
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b'v%d' % number)
        extra = {'review': 'pass'} if number == 4 else {}
        rows.append(_version(number, ago, **extra))
    (root / 'data' / 'S01' / 'v004' / 'assets_manifest.json').write_text('{"file": "frame.png"}', encoding='utf-8')
    _write(root / 'data' / 'state.json', {'shots': {'S01': rows}})
    local = root / '06_本地生成' / 'S02' / 'v001'
    local.mkdir(parents=True, exist_ok=True)
    (local / 'video.mp4').write_bytes(b'l')
    _write(root / '06_本地生成' / 'state.json',
           {'shots': {'S02': [_version(1, 1, file='06_本地生成/S02/v001/video.mp4', output_dir='06_本地生成/S02/v001')]}})
    _write(sm._recycle_base(root) / 'assets.json', {'file': 'other.bin'})


def _edit_ledger(root, mutate):
    path = root / 'data' / 'state.json'
    state = json.loads(path.read_text(encoding='utf-8'))
    mutate(state)
    _write(path, state)


def _from_exports(root, name='edit_bundle.json'):
    from project_stages import exports
    return exports(root) / name


MUTATORS = {
    'base': lambda root: None,
    'empty_root': lambda root: [p.unlink() for p in root.rglob('*.json')],
    'assets_bad_json': lambda root: _write(root / 'assets.json', '[1,2', raw=True),
    'assets_scalar': lambda root: _write(root / 'assets.json', '5', raw=True),
    'episode_list': lambda root: _write(root / 'episode.json', [{'frame': 'frame.png'}, 'sub/a.png']),
    'commercial_bad': lambda root: _write(root / 'clip.commercial.v1.json', 'nope', raw=True),
    'receipt_bad_json': lambda root: _write(root / 'adopted.mp4.source.json', '{bad', raw=True),
    'receipt_not_dict': lambda root: _write(root / 'adopted.mp4.source.json', [1, 2]),
    'receipt_chain': lambda root: (_write(root / 'frame.png.source.json', {'x': 'sub/a.png'}),
                                   _write(root / 'sub' / 'a.png.source.json', {'x': 'other.bin'})),
    'receipt_chain_bad_tail': lambda root: (_write(root / 'frame.png.source.json', {'x': 'sub/a.png'}),
                                            _write(root / 'sub' / 'a.png.source.json', '{', raw=True)),
    'ledger_no_shots': lambda root: _write(root / 'data' / 'state.json', {}),
    'ledger_shots_list': lambda root: _write(root / 'data' / 'state.json', {'shots': []}),
    'ledger_scalar': lambda root: _write(root / 'data' / 'state.json', 3),
    'ledger_versions_not_list': lambda root: _edit_ledger(root, lambda s: s['shots'].update(S01={'a': 1})),
    'ledger_version_not_dict': lambda root: _edit_ledger(root, lambda s: s['shots']['S01'].append('v')),
    'ledger_number_float': lambda root: _edit_ledger(root, lambda s: s['shots']['S01'][0].update(version=1.5)),
    'ledger_number_bool': lambda root: _edit_ledger(root, lambda s: s['shots']['S01'][0].update(version=True)),
    'ledger_number_missing': lambda root: _edit_ledger(root, lambda s: s['shots']['S01'][0].pop('version')),
    'ledger_all_unsettled': lambda root: _edit_ledger(
        root, lambda s: [v.update(state='running') for v in s['shots']['S01']]),
    'ledger_locked': lambda root: _edit_ledger(root, lambda s: s['shots']['S01'][0].update(locked=True)),
    'ledger_bad_created': lambda root: _edit_ledger(
        root, lambda s: [v.update(created='x') for v in s['shots']['S01']]),
    'ledger_output_dir_nonstr': lambda root: _edit_ledger(root, lambda s: s['shots']['S01'][0].update(output_dir=3)),
    'ledger_output_dir_escape': lambda root: _edit_ledger(
        root, lambda s: s['shots']['S01'][0].update(output_dir='../../elsewhere')),
    'ledger_output_dir_root': lambda root: _edit_ledger(root, lambda s: s['shots']['S01'][0].update(output_dir='.')),
    'ledger_empty_versions': lambda root: _edit_ledger(root, lambda s: s['shots'].update(S09=[])),
    'ledger_extra_refs': lambda root: _edit_ledger(
        root, lambda s: s['shots']['S01'][0].update(ref='other.bin', refs=['sub/a.png', {'x': 'frame.png'}])),
    'export_not_list': lambda root: _write(_from_exports(root), {'manifest': 'nope'}),
    'export_bare_list': lambda root: _write(_from_exports(root), [{'shot': 'S01', 'version': 1}]),
    'export_row_not_dict': lambda root: _write(_from_exports(root), {'manifest': ['x']}),
    'export_row_no_shot': lambda root: _write(_from_exports(root), {'manifest': [{'sha256': 'a'}]}),
    'export_row_no_id': lambda root: _write(_from_exports(root), {'manifest': [{'shot': 'S01', 'version': 'x'}]}),
    'export_row_bool_version': lambda root: _write(_from_exports(root), {'manifest': [{'shot': 'S01', 'version': True}]}),
    'export_bad_json': lambda root: _write(_from_exports(root), '{', raw=True),
    'export_fallback_name': lambda root: _write(_from_exports(root, 'edit_manifest.json'),
                                                {'manifest': [{'shot': 'S01', 'version': 4}]}),
    'policy_zero': lambda root: _write(root / 'storage_policy.json', {'retention_days': 0}),
    'policy_text': lambda root: _write(root / 'storage_policy.json', {'retention_days': '7'}),
    'policy_bad_json': lambda root: _write(root / 'storage_policy.json', '{', raw=True),
    'policy_short': lambda root: _write(root / 'storage_policy.json', {'retention_days': 1}),
    'policy_long': lambda root: _write(root / 'storage_policy.json', {'retention_days': 3650}),
}


class SourceProtectionEquivalence(unittest.TestCase):
    def setUp(self):
        namespace = dict(vars(sm))
        exec(compile(LEGACY_SRC, 'legacy_source_protection', 'exec'), namespace)
        self.legacy = namespace['_legacy_source_protection']

    def _normalise(self, root, result):
        protected, errors = result
        return sorted(p.relative_to(root).as_posix() for p in protected), list(errors)

    def test_every_fixture_matches_the_legacy_result(self):
        seen_errors = seen_protected = 0
        for name, mutate in MUTATORS.items():
            with tempfile.TemporaryDirectory() as td:
                root = Path(td).resolve()
                _base(root)
                mutate(root)
                old = self._normalise(root, self.legacy(root, NOW))
                new = self._normalise(root, sm.source_protection(root, NOW))
                self.assertEqual(new, old, name)
                seen_errors += bool(new[1])
                seen_protected += bool(new[0])
        # 对照不能是空对空：既要有受保护文件的夹具，也要有报错的夹具
        self.assertGreater(seen_protected, 20)
        self.assertGreater(seen_errors, 10)

    def test_default_now_matches_too(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            _base(root)
            self.assertEqual(self._normalise(root, self.legacy(root)),
                             self._normalise(root, sm.source_protection(root)))


if __name__ == '__main__':
    unittest.main()
