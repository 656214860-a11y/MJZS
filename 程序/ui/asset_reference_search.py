# -*- coding: utf-8 -*-
"""资产参考图的候选搜索、打分与确认入库。

本模块不直连图库：检索走调用方注入的 transport，下载默认走 agent.core.request（只允许 HTTPS）。
没配置图库接口时，可以让助手把候选清单写成 JSON／JSONL 再走 candidates_from_file，
于是「打分 → 阈值 → 版权 → 确认入库」整条链路都能离线单测；入库本身仍只由
asset_reference_images.attach 落盘，内容散列去重、角色分类和路径安全都只有那一处实现。
"""
import hashlib
import json
import re
import tempfile
from pathlib import Path

from infra.file_cache import read_json, read_text

DEFAULT_THRESHOLD = 60        # 低于这个分数不上候选图墙
DEFAULT_LIMIT = 6             # 图墙最多展示几张
MIN_EDGE = 512                # 短边小于这个像素数，做参考图没有价值
MIN_BYTES = 1024              # 太小多半是占位图或缩略图
CREDITS = 'assets/参考图/版权.json'
CATEGORY_WORDS = {'CHAR': '角色设定', 'LOC': '场景概念', 'PROP': '道具设定'}
STOPWORDS = {'参考', '图片', '高清', '素材', '壁纸', '下载', '免费', 'the', 'and', 'for', 'with', 'of'}
SPLIT = re.compile(r'[，,;；、\s/|]+')
LICENSES = {'cc0': ('CC0 公共领域', True), 'public domain': ('公有领域', True),
            'cc by-sa': ('CC BY-SA 相同方式共享', True), 'cc by-nc': ('CC BY-NC 非商用', False),
            'cc by-nd': ('CC BY-ND 禁止演绎', False), 'cc by': ('CC BY 署名', True),
            'all rights reserved': ('保留所有权利', False), 'fair use': ('合理使用', False)}


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _tags(value):
    if isinstance(value, str):
        return SPLIT.split(value)
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return []


def _license(text):
    """只接受完整许可标识或本程序输出的标签；不从任意说明中猜授权。"""
    raw = str(text or '').strip()
    key = raw.casefold()
    if key in LICENSES:
        return LICENSES[key]
    if key == 'cc0 1.0':
        return LICENSES['cc0']
    for label, commercial in LICENSES.values():
        if key == label.casefold():
            return label, commercial
    match = re.fullmatch(r'cc[ -]+by((?:[ -](?:nc|nd|sa))*)(?:\s+[1-4]\.0)?', key)
    if match:
        terms = match[1].strip(' -').replace(' ', '-').split('-') if match[1] else []
        if len(terms) == len(set(terms)) and set(terms) <= {'nc', 'nd', 'sa'}:
            if 'nc' in terms:
                return 'CC BY-' + '-'.join(term.upper() for term in terms) + ' 非商用', False
            if 'nd' in terms:
                return LICENSES['cc by-nd']
            return LICENSES['cc by-sa' if 'sa' in terms else 'cc by']
    return raw, False


def normalize(candidate):
    """补成统一形状；许可缺失一律按「未知、不可商用」处理，绝不给未声明许可的图开绿灯。"""
    item = dict(candidate) if isinstance(candidate, dict) else {}
    license_text, commercial = _license(item.get('license'))
    return {'url': str(item.get('url') or '').strip(),
            'page': str(item.get('page') or item.get('source') or '').strip(),
            'title': str(item.get('title') or '').strip(),
            'author': str(item.get('author') or item.get('owner') or '').strip(),
            'license': str(license_text).strip(),
            'license_url': str(item.get('license_url') or '').strip(),
            'collected_at': str(item.get('collected_at') or item.get('fetched_at') or item.get('date') or '').strip(),
            'commercial': bool(commercial),
            'width': _int(item.get('width')), 'height': _int(item.get('height')),
            'bytes': _int(item.get('bytes')),
            'tags': [tag.strip() for tag in _tags(item.get('tags')) if tag.strip()]}


def usable(candidate):
    """版权三要素缺一不可：图片地址、来源页、许可名（作者或站点名用来追溯）。"""
    item = normalize(candidate)
    return bool(item['url'] and item['page'] and item['license'] and (item['author'] or item['page']))


def copyright_decision(candidate):
    """商用且可能改编的参考图入口共用判定；返回阻断原因与交付义务。"""
    item = normalize(candidate)
    if not usable(item):
        return '版权信息不全（缺图片地址、来源页或许可名），不能入库', ''
    if not item['commercial']:
        return '许可不允许商用改编或无法确认：' + item['license'], ''
    if item['license'].startswith('CC BY'):
        if not item['author']:
            return '署名许可缺作者／署名方，请补充后入库', ''
        duties = '署名、保留许可链接、说明改动'
        if item['license'] == LICENSES['cc by-sa'][0]:
            duties += '；改编作品相同方式共享'
        return '', duties
    return '', '保留来源和许可凭据'


def _words(text):
    words = []
    for word in SPLIT.split(str(text or '')):
        word = word.strip('《》「」“”"()（）').casefold()
        if len(word) >= 2 and word not in STOPWORDS and word not in words:
            words.append(word)
    return words


def prompt_words(asset):
    """图片提示词里的特征词：没有提示词时，候选图只能按清晰度和许可判断。"""
    asset = asset if isinstance(asset, dict) else {}
    return _words(asset.get('image_prompt') or asset.get('prompt'))


def keywords(asset):
    """资产侧命中用词：资产名在前（用户就是按这个名字找图的），提示词特征词在后。"""
    asset = asset if isinstance(asset, dict) else {}
    words = _words(asset.get('name'))
    for word in prompt_words(asset):
        if word not in words:
            words.append(word)
    return words


def queries(asset, limit=3):
    """检索词：资产名＋类别词打底，再挂上提示词里最靠前的特征词。"""
    asset = asset if isinstance(asset, dict) else {}
    name = str(asset.get('name') or asset.get('id') or '').strip()
    if not name:
        raise ValueError('资产缺少名称，无法生成检索词')
    prefix = str(asset.get('id') or '').split('_')[0]
    words = prompt_words(asset)
    out = []
    for text in (f'{name} {CATEGORY_WORDS.get(prefix, "设定")}', f'{name} {" ".join(words[:3])}'.strip(),
                 f'{name} {CATEGORY_WORDS.get(prefix, "设定")} 参考图'):
        text = ' '.join(text.split())
        if text and text not in out:
            out.append(text)
    return out[:max(1, _int(limit) or 3)]


def _sharpness(width, height):
    edge = min(abs(width), abs(height))
    if not edge:
        return 0, '没有尺寸信息'
    if edge < MIN_EDGE:
        return 0, f'短边只有 {edge}px，太小'
    for ceiling, value in ((768, 12), (1024, 20), (1536, 28)):
        if edge < ceiling:
            return value, f'短边 {edge}px'
    return 35, f'短边 {edge}px，清晰度足够'


def _shape(width, height):
    if not width or not height:
        return 8, '缺少长宽比'
    ratio = width / height
    if 0.4 <= ratio <= 2.5:
        return 15, '构图比例正常'
    return 6, f'长宽比 {ratio:.2f} 偏极端'


def score_parts(candidate, asset):
    """0-100 的逐项打分：每项给名称、得分与说明，供图墙逐项复核与事后追溯。"""
    item = normalize(candidate)
    parts = []
    points, why = _sharpness(item['width'], item['height'])
    parts.append({'label': '清晰度', 'points': points, 'note': why})
    if prompt_words(asset):
        words = keywords(asset)
        text = ' '.join([item['title'], *item['tags']]).casefold()
        hits = [word for word in words if word in text]
        bonus = min(30, round(30 * len(hits) / min(len(words), 6)))
        note = ('命中提示词：' + '、'.join(hits[:5])) if hits else '标题与标签里没有提示词特征'
        parts.append({'label': '提示词命中', 'points': bonus, 'note': note})
    else:
        parts.append({'label': '提示词命中', 'points': 15, 'note': '资产还没有图片提示词，只能按清晰度和许可判断'})
    points, why = _shape(item['width'], item['height'])
    parts.append({'label': '构图比例', 'points': points, 'note': why})
    points = 10 if item['page'] and item['author'] else (6 if item['page'] else 0)
    note = '来源页与作者齐全' if item['page'] and item['author'] else ('只有来源页，缺作者' if item['page'] else '没有来源页')
    parts.append({'label': '来源完整度', 'points': points, 'note': note})
    if item['commercial']:
        points, note = 10, f'许可 {item["license"]}，可商用'
    else:
        points = 4 if item['license'] else 0
        note = f'许可 {item["license"]}，不可商用' if item['license'] else '没有声明许可，不能入库'
    parts.append({'label': '许可', 'points': points, 'note': note})
    return min(100, max(0, sum(part['points'] for part in parts))), parts


def score(candidate, asset):
    """0-100 确定性打分，并给出人话理由（图墙上直接显示，便于用户复核）。"""
    value, parts = score_parts(candidate, asset)
    return value, [part['note'] for part in parts]


STATE_NOTES = {
    'adoptable': '来源与许可齐全，可商用',
    'missing_url': '候选没有图片地址',
    'missing_source': '缺少来源页，无法追溯出处，不能入库',
    'missing_license': '未声明许可，不能入库',
    'missing_attribution': '署名许可缺作者／署名方，请补充后入库',
    'non_commercial': '许可不允许商用，默认不入库',
    'source_conflict': '同图多来源的许可不一致，需人工核对',
    'duplicate': '同图已有更高分来源，未重复展示',
    'low_score': '得分低于阈值，默认不上墙',
}


def _state(item, value, threshold):
    """单个候选最有解释力的状态：缺地址／缺来源／缺许可／低分／不可商用 优先于「可入库」。"""
    if not item['url']:
        return 'missing_url'
    if not item['page']:
        return 'missing_source'
    if not item['license']:
        return 'missing_license'
    if value < _int(threshold):
        return 'low_score'
    if not item['commercial']:
        return 'non_commercial'
    if copyright_decision(item)[0]:
        return 'missing_attribution'
    return 'adoptable'


def explain(candidate, asset, threshold=DEFAULT_THRESHOLD):
    """候选的可解释视图：分项、状态与人话说明；图墙与批量决策共用同一判据。"""
    item = normalize(candidate)
    value, parts = score_parts(item, asset)
    state = _state(item, value, threshold)
    return {'score': value, 'breakdown': parts, 'state': state, 'note': STATE_NOTES[state],
            'reasons': [part['note'] for part in parts]}


def fingerprint(candidate):
    """同一张图在不同站点地址不同：有标题和尺寸时按内容取指纹，否则退化成地址。"""
    item = normalize(candidate)
    if item['title'] and item['width'] and item['height']:
        text = f"{item['width']}x{item['height']}|{item['title'].casefold()}|{item['author'].casefold()}"
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    return item['url']


def rank(candidates, asset, threshold=DEFAULT_THRESHOLD, limit=DEFAULT_LIMIT):
    """候选图墙的内容：打分 → 同图去重（记同图其它来源）→ 阈值 → 按分排序截断。"""
    groups, order = {}, []
    for candidate in candidates or []:
        item = normalize(candidate)
        value, parts = score_parts(item, asset)
        entry = {**item, 'score': value, 'breakdown': parts,
                 'reasons': [part['note'] for part in parts],
                 'fingerprint': fingerprint(item), 'alts': []}
        if entry['fingerprint'] not in groups:
            groups[entry['fingerprint']] = []
            order.append(entry['fingerprint'])
        groups[entry['fingerprint']].append(entry)
    kept = []
    for key in order:
        group = groups[key]
        group.sort(key=lambda entry: -entry['score'])          # 稳定排序：同分保留先出现的来源
        best = group[0]
        best['alts'] = [{'url': other['url'], 'page': other['page'], 'author': other['author'],
                         'license': other['license'], 'commercial': other['commercial'],
                         'collected_at': other['collected_at']} for other in group[1:]]
        best['conflict'] = any(alt['commercial'] != best['commercial'] or alt['license'] != best['license']
                               for alt in best['alts'])
        state = _state(best, best['score'], threshold)
        if state == 'adoptable' and best['conflict']:
            state = 'source_conflict'
        best['state'], best['note'] = state, STATE_NOTES[state]
        if best['score'] >= _int(threshold):
            kept.append(best)
    kept.sort(key=lambda item: (-item['score'], item['url']))
    return kept[:max(0, _int(limit) if limit is not None else DEFAULT_LIMIT)]


def suppressed(candidates, asset, threshold=DEFAULT_THRESHOLD):
    """被「缺许可／低分／同图重复」挡在图墙外的候选：逐条给可解释状态，解释「为什么没上墙」。"""
    groups, order = {}, []
    for candidate in candidates or []:
        item = normalize(candidate)
        value, _parts = score_parts(item, asset)
        key = fingerprint(item)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((value, item))
    out = []
    for key in order:
        pairs = groups[key]
        pairs.sort(key=lambda pair: -pair[0])
        best_value, best = pairs[0]
        for value, item in pairs[1:]:
            out.append({'url': item['url'], 'score': value, 'state': 'duplicate',
                        'note': f'同图已有更高分来源：{best["url"]}'})
        state = _state(best, best_value, threshold)
        if state != 'adoptable':
            out.append({'url': best['url'], 'score': best_value, 'state': state, 'note': STATE_NOTES[state]})
    return out


def search(transport, asset, threshold=DEFAULT_THRESHOLD, limit=DEFAULT_LIMIT):
    """跑一遍检索：一条检索词失败只记明细，不影响其他检索词和图墙。"""
    asked = queries(asset)
    found, errors = [], []
    for query in asked:
        try:
            found.extend(transport(query) or [])
        except Exception as exc:
            errors.append({'query': query, 'error': str(exc)})
    return {'queries': asked, 'candidates': rank(found, asset, threshold, limit), 'errors': errors}


def candidates_from_file(path):
    """读助手或手工导出的候选清单：JSON 数组、带 candidates 字段的对象，或逐行 JSONL。"""
    try:
        data = read_json(path)
    except ValueError:
        decoder = json.JSONDecoder()
        data = [decoder.decode(line) for line in read_text(path).splitlines() if line.strip()]
    if isinstance(data, dict):
        data = data.get('candidates') or data.get('items') or []
    if not isinstance(data, list):
        raise ValueError('候选清单格式不正确：应为数组或逐行 JSON')
    return [item for item in data if isinstance(item, dict)]


def suffix_of(raw):
    """按字节判断后缀：地址上的 .jpg 常常装着 PNG，写进资产库前必须先看内容。"""
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if raw.startswith(b'\xff\xd8'):
        return '.jpg'
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return '.webp'
    return ''


def fetch_bytes(url, timeout=60):
    """内置下载：只走 HTTPS，返回原始字节，交给 asset_reference_images 做格式校验。"""
    from urllib.parse import urlparse
    if urlparse(str(url)).scheme != 'https':
        raise ValueError('参考图只允许从 HTTPS 地址下载')
    from agent.core import request
    return request(str(url), raw=True)


def _credit(item, digest):
    return {'url': item['url'], 'page': item['page'], 'title': item['title'], 'author': item['author'],
            'license': item['license'], 'license_url': item['license_url'],
            'collected_at': item['collected_at'], 'commercial': item['commercial'], 'sha256': digest,
            'obligations': copyright_decision(item)[1]}


def _write_credits(base, aid, table, read, save, image_bytes):
    """把版权记到资产库相对路径上：同一份字节被多个资产引用时，各自都能查到许可。"""
    plan = read(base / 'assets/资产清单/assets.json')
    records = {}
    for relative in (plan.get(aid) or {}).get('reference_images', []):
        path = base / relative
        if not path.is_file():
            continue
        record = table.get(hashlib.sha256(image_bytes(path)).hexdigest())
        if record:
            records[relative] = record
    if records:
        file = base / CREDITS
        existing = read(file) if file.is_file() else {}
        existing = existing if isinstance(existing, dict) else {}
        existing.update(records)
        save(file, existing)
    return records


def adopt(base, aid, picks, fetch=None, role=None):
    """确认入库：下载 → 按字节判格式 → attach 落盘 → 记版权。

    版权不全的候选直接跳过；单张失败只记明细不中断——勾了 5 张，不能因为第 2 张 404 就全废。
    """
    from asset_reference_images import attach, image_bytes
    from agent.core import read, save, save_bytes
    base = Path(base).resolve()
    fetch = fetch or fetch_bytes
    adopted, skipped, table = [], [], {}
    with tempfile.TemporaryDirectory() as td:
        for pick in picks or []:
            item = normalize(pick)
            if not item['url']:
                skipped.append({'url': '', 'reason': '候选没有图片地址'})
                continue
            reason, _ = copyright_decision(item)
            if reason:
                skipped.append({'url': item['url'], 'reason': reason})
                continue
            try:
                raw = fetch(item['url'])
            except Exception as exc:
                skipped.append({'url': item['url'], 'reason': '下载失败：' + str(exc)})
                continue
            suffix = suffix_of(raw)
            if not suffix:
                skipped.append({'url': item['url'], 'reason': '不是 PNG／JPG／WebP 图片'})
                continue
            if len(raw) < MIN_BYTES:
                skipped.append({'url': item['url'], 'reason': '图片太小，可能是占位图'})
                continue
            digest = hashlib.sha256(raw).hexdigest()
            path = Path(td) / (digest[:16] + suffix)
            # 下载完成后一次性替换候选文件；attach 只会看到完整图片。
            save_bytes(path, raw)
            try:
                attach(base, aid, [path], role)
            except Exception as exc:
                skipped.append({'url': item['url'], 'reason': '入库失败：' + str(exc)})
                continue
            table[digest] = _credit(item, digest)
            adopted.append({'url': item['url'], 'sha256': digest, 'license': item['license'],
                            'commercial': item['commercial']})
    return {'adopted': adopted, 'skipped': skipped,
            'credits': _write_credits(base, aid, table, read, save, image_bytes)}
