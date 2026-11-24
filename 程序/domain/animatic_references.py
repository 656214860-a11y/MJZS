"""L2 分镜预演参考库：按文件名归类、按镜配图与导入计划（纯函数，不写盘）。"""
import hashlib
import re
import unicodedata
from pathlib import Path

CATEGORIES = ('角色', '场景', '风格')
UNCATEGORIZED = '未分类'
IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')
MAX_IMAGE_BYTES = 20 * 1024 * 1024


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


def refs_for_shot(shot, lib):
    """命中角色图＋命中场景图＋全部风格图（去重保序）；全空退回未分类全部图。"""
    wanted = {normalize_name(name) for name in shot.get('characters', ()) or ()}
    location = normalize_name(shot.get('location', '') or '')
    picked, seen = [], set()

    def take(item):
        if item['path'] not in seen:
            seen.add(item['path'])
            picked.append(item['path'])

    for item in lib.get('角色', ()):
        if item['stem_key'] in wanted:
            take(item)
    for item in lib.get('场景', ()):
        if location and item['stem_key'] == location:
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
