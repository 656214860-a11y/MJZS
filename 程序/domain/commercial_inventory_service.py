"""商用交付采用素材的只读递归盘点与人工补录比对。

本模块不写项目文件、不推断授权：只从交付成片已经登记的来源边出发，
读取 edit_bundle、镜头 assets_manifest 与产物来源关系账本的 frozen sha256，
列出当前仍必须由人工授权审核覆盖的文件。外部精修或自定义流程没有登记边时
只能标为未知，不能假装自动链完整。
"""
import os
from pathlib import Path

from contract.artifact_lineage import check as lineage_check
from infra.file_cache import file_digest, read_json

IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.bmp'})
VIDEO_SUFFIXES = frozenset({'.mp4', '.mov', '.mkv'})
AUDIO_SUFFIXES = frozenset({'.wav', '.mp3', '.m4a', '.aac', '.flac'})
FONT_SUFFIXES = frozenset({'.ttf', '.ttc', '.otf'})

UNKNOWN_GAP_KINDS = frozenset({
    'missing_edit_bundle', 'invalid_edit_bundle', 'invalid_assets_manifest',
    'invalid_lineage', 'invalid_reference_category', 'unresolved_script', 'receipt_mismatch',
})

CATEGORY_ERRORS = {
    'script': '剧本授权清单未覆盖当前分镜实际来源',
    'reference': '参考授权未覆盖镜头生成时采用的素材版本',
    'image': '图像授权未覆盖镜头生成时采用的首帧或图像版本',
    'video': '视频授权未覆盖成片实际镜头来源版本',
    'music': '音乐授权未覆盖成片实际使用的背景音乐版本',
    'font': '字体授权未覆盖成片实际使用的字体版本',
    'voice': '声音授权未覆盖成片实际使用的配音或音源版本',
}


def _norm(path):
    return os.path.normcase(str(Path(path).resolve()))


def _inside(root, path):
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return False


def _relative(root, path):
    path = Path(path).resolve()
    if _inside(root, path):
        return path.relative_to(Path(root).resolve()).as_posix()
    return str(path)


def _read_json(path):
    try:
        return read_json(path), ''
    except (OSError, ValueError, TypeError) as exc:
        return None, str(exc)


def _lineage_category(path, role='', artifact_type=''):
    text = (str(role) + ' ' + str(artifact_type)).casefold()
    suffix = Path(path).suffix.lower()
    if suffix in FONT_SUFFIXES:
        return 'font'
    if suffix in VIDEO_SUFFIXES:
        return 'video'
    if suffix in AUDIO_SUFFIXES:
        return 'music' if any(word in text for word in ('music', 'bgm', '配乐', '音乐')) else 'voice'
    if suffix in IMAGE_SUFFIXES:
        return 'reference' if 'reference' in text or '参考' in text else 'image'
    return 'script'


class _Collector:
    """单个交付版本的盘点状态；每次调用新建，避免缓存旧文件摘要。"""

    def __init__(self, root, scope, outputs, script_path=None, script_warning=''):
        self.root = Path(root).resolve()
        self.scope = scope
        self.outputs = outputs
        self.script_path = Path(script_path).resolve() if script_path is not None else None
        self.script_warning = script_warning
        self.categories = {key: {'items': [], 'unused_reason': ''}
                           for key in ('script', 'reference', 'image', 'video', 'music', 'font', 'voice')}
        self.warnings = []
        self.gaps = []
        self.requirements = []
        self._items = {}
        self._requirement_keys = set()
        self._queue = []
        self._inspected = set()
        self._asset_scan_keys = set()
        self._inspected_manifests = set()

    def collect(self):
        self._add_script()
        for output in self.outputs:
            self._add_output(output)
        self._drain()
        return {'categories': self.categories, 'warnings': self.warnings,
                'requirements': self.requirements, 'trace_gaps': self.gaps}

    def _warn(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def _gap(self, kind, message, path=''):
        row = {'kind': kind, 'message': message, 'path': path}
        if row not in self.gaps:
            self.gaps.append(row)
        self._warn(message)

    def _require(self, category, path, sha256, kind, error, edge='', base=''):
        base_text = _relative(self.root, base) if base else ''
        row = {'category': category, 'path': str(path or ''), 'sha256': str(sha256 or ''),
               'kind': kind, 'error': error, 'edge': edge, 'base': base_text}
        key = (row['category'], row['path'], row['sha256'], row['kind'], row['error'], row['base'])
        if key not in self._requirement_keys:
            self._requirement_keys.add(key)
            self.requirements.append(row)

    def _structural(self, error, edge):
        self._require('video', '', '', 'structural', error, edge)

    def _receipt_origin(self, path, digest):
        receipt_path = path.with_name(path.name + '.source.json')
        if not receipt_path.is_file():
            return '', None
        snapshot = {'path': _relative(self.root, receipt_path), 'sha256': file_digest(receipt_path)}
        receipt, error = _read_json(receipt_path)
        valid = (isinstance(receipt, dict) and receipt.get('sha256') == digest
                 and receipt.get('imported_file') == path.name)
        if not valid:
            self._gap('receipt_mismatch', '导入来源记录与当前素材不一致：' + str(path),
                      _relative(self.root, path))
            return '', snapshot
        if isinstance(receipt.get('source'), str):
            return '外部导入：' + receipt['source'], snapshot
        return '', snapshot

    def _register(self, category, path, expected=None, edge='', kind='', error='', base=''):
        path = Path(path).resolve()
        expected = str(expected or '')
        rel = _relative(self.root, path)
        error = error or CATEGORY_ERRORS[category]
        if not _inside(self.root, path) or not path.is_file() or not path.stat().st_size:
            self._gap('missing_source', '来源缺失、为空或越出项目：' + str(path), rel)
            self._require(category, rel, expected, kind, error, edge, base)
            return None
        digest = file_digest(path)
        status = 'current'
        if expected and expected != digest:
            status = 'stale'
            self._gap('stale_source', '来源版本已改变：' + str(path), rel)
        self._require(category, rel, expected or digest, kind, error, edge, base)
        key = (category, _norm(path))
        if kind in ('shot_source', 'lineage_video'):
            self._asset_scan_keys.add(_norm(path))
        item = self._items.get(key)
        if item is None:
            source, receipt = self._receipt_origin(path, digest)
            item = {'path': rel, 'sha256': digest, 'source': source,
                    'rights_holder': '', 'license': '', 'commercial_allowed': False,
                    'derivative_allowed': False, 'obligations_fulfilled': False,
                    'authorization': {'path': '', 'sha256': ''},
                    'trace_status': status, 'source_edges': []}
            if receipt:
                item['source_receipt'] = receipt
            self._items[key] = item
            self.categories[category]['items'].append(item)
            self._queue.append(path)
        elif status == 'stale':
            item['trace_status'] = 'stale'
        if edge and edge not in item['source_edges']:
            item['source_edges'].append(edge)
        return path

    def _add_script(self):
        if self.script_warning:
            self._gap('unresolved_script', self.script_warning)
            return
        if self.script_path is not None:
            self._register('script', self.script_path, edge='adopted_storyboard:script',
                           kind='script', error=CATEGORY_ERRORS['script'])

    def _add_output(self, output):
        path = (self.root / output['path']).resolve()
        self._register('video', path, output.get('sha256'), 'delivery:output',
                       'delivery_master', '视频授权清单未覆盖实际交付成片')
        bundle_path = path.parent / 'edit_bundle.json'
        edge = 'edit_bundle:' + bundle_path.name
        if not bundle_path.is_file():
            self._gap('missing_edit_bundle',
                      '成片无来源清单，须人工补齐镜头及其他采用素材：' + output['path'],
                      output['path'])
            return
        bundle, error = _read_json(bundle_path)
        if not isinstance(bundle, dict):
            self._gap('invalid_edit_bundle', '成片来源清单格式无效：' + output['path'], output['path'])
            self._structural('成片来源清单与交付文件不一致', edge)
            return
        if bundle.get('master') != path.name or bundle.get('master_sha256') != output.get('sha256'):
            self._structural('成片来源清单与交付文件不一致', edge)
        self._add_manifest_rows(bundle, path, edge)
        self._add_reference_rows(bundle, path, edge)
        self._add_music_rows(bundle, path, edge)
        self._add_font_rows(bundle, path, edge)

    def _add_manifest_rows(self, bundle, output_path, edge):
        rows = bundle.get('manifest')
        if not isinstance(rows, list) or not rows:
            self._structural('成片来源清单为空或无效', edge + ':manifest')
            return
        for row in rows:
            if not isinstance(row, dict):
                self._require('video', '', '', 'shot_hash', '授权清单未覆盖成片已登记的镜头来源',
                              edge + ':manifest')
                continue
            sha256 = str(row.get('sha256') or '')
            if 'source' not in row:
                self._warn('来源清单缺少路径，须人工补齐：manifest')
                self._require('video', '', sha256, 'shot_hash', '授权清单未覆盖成片已登记的镜头来源',
                              edge + ':manifest')
            elif not isinstance(row['source'], str) or not row['source'].strip():
                self._require('video', '', sha256, 'invalid_shot_path', '成片镜头来源路径无效',
                              edge + ':manifest')
            else:
                self._register('video', output_path.parent / row['source'], sha256,
                               edge + ':manifest', 'shot_source', CATEGORY_ERRORS['video'])
            self._add_audio_rows(row, output_path, edge)

    def _add_audio_rows(self, row, output_path, edge):
        rows = row.get('audio', [])
        if rows is None:
            return
        if not isinstance(rows, list):
            self._structural('成片声音来源清单无效', edge + ':audio')
            return
        for audio in rows:
            if not isinstance(audio, dict) or not isinstance(audio.get('path'), str) or not audio['path'].strip():
                self._require('voice', '', str((audio or {}).get('sha256') if isinstance(audio, dict) else ''),
                              'invalid_voice_path', CATEGORY_ERRORS['voice'], edge + ':audio')
                continue
            self._register('voice', output_path.parent / audio['path'], audio.get('sha256'),
                           edge + ':audio', 'voice', CATEGORY_ERRORS['voice'])

    def _add_reference_rows(self, bundle, output_path, edge):
        rows = bundle.get('references', [])
        if not isinstance(rows, list):
            self._structural('成片参考来源清单无效', edge + ':references')
            return
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('path'), str) or not row['path'].strip():
                self._structural('成片参考来源清单无效', edge + ':references')
                continue
            category = row.get('category', 'reference')
            if category not in ('reference', 'image'):
                self._gap('invalid_reference_category', '参考来源类别无效', row['path'])
                self._structural('成片参考来源类别无效', edge + ':references')
                continue
            self._register(category, output_path.parent / row['path'], row.get('sha256'),
                           edge + ':references', category, CATEGORY_ERRORS['reference'])

    def _add_music_rows(self, bundle, output_path, edge):
        rows = bundle.get('music', [])
        if not isinstance(rows, list):
            self._structural('成片配乐来源清单无效', edge + ':music')
            return
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('path'), str) or not row['path'].strip():
                self._require('music', '', '', 'invalid_music_path', CATEGORY_ERRORS['music'], edge + ':music')
                continue
            self._register('music', output_path.parent / row['path'], row.get('sha256'),
                           edge + ':music', 'music', CATEGORY_ERRORS['music'])

    def _add_font_rows(self, bundle, output_path, edge):
        rows = bundle.get('fonts', [])
        if not isinstance(rows, list):
            self._structural('成片字体来源清单无效', edge + ':fonts')
            return
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('path'), str):
                self._structural('成片字体来源清单无效', edge + ':fonts')
                continue
            self._register('font', output_path.parent / row['path'], row.get('sha256'),
                           edge + ':fonts', 'font', CATEGORY_ERRORS['font'], output_path.parent)
        local_font = output_path.parent / 'font.ttc'
        if local_font.is_file():
            try:
                digest = file_digest(local_font)
            except OSError:
                digest = ''
            self._register('font', local_font, digest, edge + ':font.ttc', 'font', CATEGORY_ERRORS['font'])

    def _drain(self):
        while self._queue:
            path = self._queue.pop(0)
            key = _norm(path)
            if key in self._inspected:
                continue
            self._inspected.add(key)
            self._inspect_lineage(path)
            if key in self._asset_scan_keys:
                self._inspect_assets_manifest(path)

    def _inspect_lineage(self, path):
        if not _inside(self.root, path):
            return
        try:
            report = lineage_check(self.root, path)
        except (OSError, ValueError, TypeError):
            self._gap('invalid_lineage', '产物来源关系账本无法读取：' + str(path), _relative(self.root, path))
            return
        for source in report.get('sources') or []:
            rel = str(source.get('path') or '')
            if not rel:
                continue
            source_path = (self.root / rel).resolve()
            category = _lineage_category(source_path, source.get('role'), report.get('artifact_type'))
            self._register(category, source_path, source.get('recorded_sha256'),
                           '产物来源关系:' + str(source.get('role') or 'source'),
                           'lineage_' + category, CATEGORY_ERRORS[category])

    def _inspect_assets_manifest(self, video_path):
        if video_path.suffix.lower() not in VIDEO_SUFFIXES:
            return
        manifest_path = video_path.parent / 'assets_manifest.json'
        key = _norm(manifest_path)
        if key in self._inspected_manifests or not manifest_path.is_file():
            return
        self._inspected_manifests.add(key)
        manifest, error = _read_json(manifest_path)
        if not isinstance(manifest, dict):
            self._gap('invalid_assets_manifest', '镜头参考资产清单无法读取：' + str(manifest_path),
                      _relative(self.root, manifest_path))
            return
        rows = manifest.get('assets', [])
        if not isinstance(rows, list):
            self._gap('invalid_assets_manifest', '镜头参考资产清单无效：' + str(manifest_path),
                      _relative(self.root, manifest_path))
            return
        source_rows = [('assets', row) for row in rows]
        for key_name in ('first_frame', 'white_model_reference'):
            if isinstance(manifest.get(key_name), dict):
                source_rows.append((key_name, manifest[key_name]))
        for edge_name, asset in source_rows:
            if (not isinstance(asset, dict) or not isinstance(asset.get('path'), str)
                    or not asset['path'].strip() or not asset.get('sha256')):
                self._gap('invalid_assets_manifest', '镜头参考资产缺少路径或摘要：' + str(manifest_path),
                          _relative(self.root, manifest_path))
                continue
            category = asset.get('category') if asset.get('category') in ('reference', 'image') else 'reference'
            self._register(category, manifest_path.parent / asset['path'], asset.get('sha256'),
                           'assets_manifest:' + edge_name,
                           'asset_' + category, CATEGORY_ERRORS[category])


def collect_inventory(root, scope, outputs, *, script_path=None, script_warning=''):
    """递归枚举交付版本实际采用文件，返回 categories/warnings/requirements/trace_gaps。"""
    return _Collector(root, scope, outputs, script_path, script_warning).collect()


def _item_key(root, category, value):
    text = str(value or '')
    path = Path(text)
    resolved = path.resolve() if path.is_absolute() else (Path(root).resolve() / text).resolve()
    return category, _norm(resolved)


def _declared_items(root, evidence):
    rows = {}
    categories = evidence.get('categories') if isinstance(evidence, dict) else None
    if not isinstance(categories, dict):
        return rows
    for category, group in categories.items():
        items = group.get('items') if isinstance(group, dict) else None
        for item in items or []:
            if isinstance(item, dict) and item.get('path'):
                rows[_item_key(root, category, item['path'])] = item
    return rows


def _review_source_receipts(root, declared, missing, changed):
    """来源记录也是版本凭据：缺失或内容变化在交付页列为事实，不自动判授权。"""
    for (category, _path), item in declared.items():
        receipt = item.get('source_receipt') if isinstance(item, dict) else None
        if not isinstance(receipt, dict) or not receipt.get('path'):
            continue
        raw = Path(str(receipt['path']))
        receipt_path = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
        rel = _relative(root, receipt_path)
        if not _inside(root, receipt_path) or not receipt_path.is_file() or not receipt_path.stat().st_size:
            if all(row['path'] != rel for row in missing):
                missing.append({'category': category, 'path': rel,
                                'sha256': str(receipt.get('sha256') or '')})
            continue
        digest = file_digest(receipt_path)
        if digest != receipt.get('sha256') and all(row['path'] != rel for row in changed):
            changed.append({'category': category, 'path': rel,
                            'expected_sha256': str(receipt.get('sha256') or ''),
                            'actual_sha256': digest})


def review_inventory(root, inventory, evidence):
    """把人工已填资料与当前自动盘点比对，分出遗漏、来源变更和人工补录。"""
    root = Path(root).resolve()
    automatic = {}
    for category, group in (inventory.get('categories') or {}).items():
        for item in (group or {}).get('items') or []:
            automatic[_item_key(root, category, item['path'])] = item
    declared = _declared_items(root, evidence)
    missing, changed, manual = [], [], []
    for key, item in automatic.items():
        row = declared.get(key)
        if row is None:
            missing.append({'category': key[0], 'path': item['path'], 'sha256': item['sha256']})
        elif row.get('sha256') != item.get('sha256'):
            changed.append({'category': key[0], 'path': item['path'],
                            'expected_sha256': item['sha256'], 'actual_sha256': str(row.get('sha256') or '')})
    for key, item in declared.items():
        if key not in automatic:
            manual.append({'category': key[0], 'path': str(item.get('path') or ''),
                           'sha256': str(item.get('sha256') or '')})
    _review_source_receipts(root, declared, missing, changed)
    for gap in inventory.get('trace_gaps') or []:
        path = str(gap.get('path') or '')
        if gap.get('kind') == 'missing_source' and path and all(row['path'] != path for row in missing):
            missing.append({'category': '', 'path': path, 'sha256': ''})
        elif gap.get('kind') == 'stale_source' and path and all(row['path'] != path for row in changed):
            changed.append({'category': '', 'path': path, 'expected_sha256': '', 'actual_sha256': ''})
    unknown = [row for row in inventory.get('trace_gaps') or []
               if row.get('kind') in UNKNOWN_GAP_KINDS]
    return {'missing': missing, 'changed': changed, 'manual': manual, 'unknown': unknown}


def review_text(review):
    """交付页一行计数＋少量明细；不代替打开 pending/commercial 原文核对。"""
    counts = (len(review['missing']), len(review['changed']),
              len(review['manual']), len(review['unknown']))
    lines = ['商用素材盘点：遗漏 %d，来源变更 %d，人工补录 %d，未登记或异常来源边 %d' % counts]
    for label, rows in (('遗漏', review['missing']), ('来源变更', review['changed']),
                        ('人工补录', review['manual'])):
        if rows:
            names = [row['path'] for row in rows[:3]]
            suffix = ' 等 %d 项' % len(rows) if len(rows) > 3 else ''
            lines.append(label + '：' + '、'.join(names) + suffix)
    if review['unknown']:
        messages = [row['message'] for row in review['unknown'][:2]]
        suffix = ' 等 %d 项' % len(review['unknown']) if len(review['unknown']) > 2 else ''
        lines.append('未登记或异常：' + '；'.join(messages) + suffix)
    if not any(counts):
        lines.append('未发现遗漏、来源变更或未登记来源边；仍须人工核对授权与内容。')
    return '\n'.join(lines)
