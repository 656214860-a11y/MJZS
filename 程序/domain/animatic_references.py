"""L2 分镜预演参考库：按文件名归类、按镜配图与导入计划（纯函数，不写盘）。"""
import hashlib
import re
import unicodedata
from pathlib import Path

CATEGORIES = ('角色', '场景', '风格')
UNCATEGORIZED = '未分类'
IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')
MAX_IMAGE_BYTES = 20 * 1024 * 1024
_ASSET_ID_RE = re.compile(r'^(CHAR|LOC)_\d{3,}$', re.IGNORECASE)
_EXCLUDED_IMPORTANCE = frozenset({'background', 'extra', 'non_face'})


def _asset_id_key(text):
    """完整资产编号精确键（CHAR_001/LOC_001）；避免被 normalize_name 按 _ 截断串图。"""
    raw = unicodedata.normalize('NFKC', str(text or '')).strip().upper()
    return raw if _ASSET_ID_RE.fullmatch(raw) else ''


def normalize_name(text):
    """归类键：NFKC 统一 → 去扩展名 → 首个 ``_``/``-`` 前段 → 去首尾空白。"""
    stem = Path(unicodedata.normalize('NFKC', str(text or '')).strip()).stem
    return re.split(r'[_-]', stem, maxsplit=1)[0].strip()


def classify(filename, characters=(), locations=()):
    """返回 (类别, 匹配名)：命中角色归角色，命中场景归场景，否则归风格。"""
    key = normalize_name(filename)
    for name in characters:
        if key and key == normalize_name(name):
            return '角色', str(name)
    for name in locations:
        if key and key == normalize_name(name):
            return '场景', str(name)
    return '风格', key


def library(read_dirs):
    """扫描全部参考目录：角色/场景/风格 子目录各归其类，其余图归未分类。"""
    grouped = {name: [] for name in (*CATEGORIES, UNCATEGORIZED)}
    seen = set()
    for folder in read_dirs:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES or path in seen:
                continue
            seen.add(path)
            category = path.parent.name if path.parent.name in CATEGORIES else UNCATEGORIZED
            grouped[category].append({'path': path, 'name': path.name,
                                      'stem_key': normalize_name(path.name), 'category': category})
    return grouped


def formal_asset_entries(plan, registry, base):
    """REQ-S04-113：从 S05 清单与图片登记表构造可复用的正式角色／场景图索引（纯函数，只读）。

    编号键（CHAR_###／LOC_###）单独做完整大写精确匹配，绝不被 normalize_name 按 _ 截断；
    图片严格以登记表 registry[aid]['image'] 为准且须在 base 内、非空、格式合法。
    """
    plan = plan if isinstance(plan, dict) else {}
    registry = registry if isinstance(registry, dict) else {}
    root = Path(base).resolve()
    grouped = {'角色': [], '场景': []}
    for aid in sorted({str(key) for key in plan} | {str(key) for key in registry}):
        id_key = _asset_id_key(aid)
        if not id_key:
            continue
        item = plan.get(aid) if isinstance(plan.get(aid), dict) else {}
        reg = registry.get(aid) if isinstance(registry.get(aid), dict) else {}
        if item.get('requires_asset') is False:
            continue
        if str(item.get('character_importance') or '').strip() in _EXCLUDED_IMPORTANCE:
            continue
        image = str(reg.get('image') or '').strip()
        if not image:
            continue
        try:
            candidate = (root / image).resolve()
            if (not candidate.is_relative_to(root)
                    or candidate.suffix.lower() not in IMAGE_SUFFIXES
                    or not candidate.is_file() or not candidate.stat().st_size):
                continue
        except (OSError, ValueError):
            continue
        names = [item.get('name'), reg.get('name')]
        for source in (item, reg):
            aliases = source.get('aliases')
            if isinstance(aliases, (list, tuple)):
                names.extend(aliases)
        name_keys = []
        for raw in names:
            if not isinstance(raw, str) or not raw.strip() or _asset_id_key(raw):
                continue
            key = normalize_name(raw)
            if key and key not in name_keys:
                name_keys.append(key)
        category = '角色' if id_key.startswith('CHAR_') else '场景'
        display = str(item.get('name') or reg.get('name') or aid).strip()
        grouped[category].append({
            'path': candidate, 'aid': aid, 'name': display, 'id_key': id_key,
            'name_keys': tuple(name_keys), 'category': category, 'source': 'formal_asset',
        })
    return grouped


def _match_formal(token, entries):
    id_key = _asset_id_key(token)
    if id_key:
        return [item for item in entries if item.get('id_key') == id_key]
    name_key = normalize_name(token)
    if not name_key:
        return []
    return [item for item in entries if name_key in (item.get('name_keys') or ())]


def refs_for_shot(shot, lib, *, formal_assets=None):
    """命中角色图＋命中场景图＋全部风格图（去重保序）；全空退回未分类全部图。

    传入 formal_assets 时（REQ-S04-113）：每个角色／场景优先匹配 S05 已入库正式资产图，
    未命中再回退共享参考库同类别图，风格图始终附加。
    """
    picked, seen = [], set()

    def take(item):
        key = Path(item['path']).resolve()
        if key not in seen:
            seen.add(key)
            picked.append(item['path'])

    if formal_assets is None:
        wanted = {normalize_name(name) for name in shot.get('characters', ()) or ()}
        location = normalize_name(shot.get('location', '') or '')
        for item in lib.get('角色', ()):
            if item['stem_key'] in wanted:
                take(item)
        for item in lib.get('场景', ()):
            if location and item['stem_key'] == location:
                take(item)
    else:
        formal_chars = formal_assets.get('角色', ())
        formal_scenes = formal_assets.get('场景', ())
        for raw in shot.get('characters', ()) or ():
            hits = _match_formal(raw, formal_chars)
            if hits:
                for item in hits:
                    take(item)
            else:
                key = normalize_name(raw)
                for item in lib.get('角色', ()):
                    if key and item['stem_key'] == key:
                        take(item)
        raw_loc = shot.get('location', '') or ''
        if raw_loc:
            hits = _match_formal(raw_loc, formal_scenes)
            if hits:
                for item in hits:
                    take(item)
            else:
                key = normalize_name(raw_loc)
                for item in lib.get('场景', ()):
                    if key and item['stem_key'] == key:
                        take(item)
    for item in lib.get('风格', ()):
        take(item)
    if not picked:
        for item in lib.get(UNCATEGORIZED, ()):
            take(item)
    return tuple(picked)


def import_plan(sources, *, characters=(), locations=(), existing=(), category=None):
    """导入计划：校验后缀与大小、按内容摘要与已有图去重、同名自动编号。

    返回 {相对路径: 字节}；分类键为 ``<类别>/<文件名>``，未分类写库根（键为纯文件名）。
    """
    if category is not None and category not in (*CATEGORIES, UNCATEGORIZED):
        raise ValueError('参考图分类无效：' + str(category))
    digests = set()
    taken = {name: set() for name in (*CATEGORIES, UNCATEGORIZED)}
    for path in existing:
        path = Path(path)
        taken[path.parent.name if path.parent.name in CATEGORIES else UNCATEGORIZED].add(path.name)
        if path.is_file():
            digests.add(hashlib.sha256(path.read_bytes()).hexdigest())
    plan = {}
    for source in sources:
        path = Path(source)
        if (path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file()
                or not 0 < path.stat().st_size <= MAX_IMAGE_BYTES):
            raise ValueError('请选择不超过 20 MB 的 PNG、JPEG 或 WebP 参考图')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest in digests:
            continue
        digests.add(digest)
        bucket = category if category is not None else classify(path.name, characters, locations)[0]
        filename = _numbered(path.name, taken[bucket])
        taken[bucket].add(filename)
        plan[filename if bucket == UNCATEGORIZED else bucket + '/' + filename] = raw
    return plan


def _numbered(name, taken):
    """同名加序号：林夏.png → 林夏(2).png → 林夏(3).png。"""
    if name not in taken:
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    index = 2
    while f'{stem}({index}){suffix}' in taken:
        index += 1
    return f'{stem}({index}){suffix}'
