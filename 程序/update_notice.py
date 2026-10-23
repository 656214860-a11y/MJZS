"""L2 版本更新提示的纯判定：比较本机版本与服务端 ``/v1/meta`` 下发的最新／最低版本，不联网、不导入 Tk。

版本号口径宽松：只取开头的 ``数字(.数字)*``，``0.6-20260918``、``V0.7`` 都能比较；取不到的一律视为无法判断，不提示。
"""
import re

NONE, SOFT, HARD = 'none', 'soft', 'hard'
_LEAD = re.compile(r'[Vv]?(\d+(?:\.\d+)*)')
NOTES_MAX = 500


def parse_version(text):
    found = _LEAD.match(str(text or '').strip())
    return tuple(int(part) for part in found.group(1).split('.')) if found else None


def _newer(a, b):
    """a 比 b 新（短版本号按 0 补齐）。"""
    size = max(len(a), len(b))
    return tuple(a) + (0,) * (size - len(a)) > tuple(b) + (0,) * (size - len(b))


def _safe_url(url):
    url = str(url or '').strip()
    return url if url.startswith('https://') else ''


def evaluate(meta, current):
    """返回 ``{level, version, url, notes, text}``；``level`` 为 none／soft／hard。"""
    meta = meta if isinstance(meta, dict) else {}
    mine = parse_version(current)
    url, notes = _safe_url(meta.get('download_url')), str(meta.get('release_notes') or '')[:NOTES_MAX]
    result = {'level': NONE, 'version': '', 'url': url, 'notes': notes, 'text': ''}
    if mine is None:
        return result
    floor, latest = parse_version(meta.get('min_client_version')), parse_version(meta.get('latest_version'))
    if floor and _newer(floor, mine):
        result.update(level=HARD, version=str(meta.get('min_client_version')),
                      text='当前版本过低，已无法使用账号功能，请升级到 %s 或更新版本。' % meta.get('min_client_version'))
    elif latest and _newer(latest, mine):
        result.update(level=SOFT, version=str(meta.get('latest_version')),
                      text='有新版本 %s。%s' % (meta.get('latest_version'), notes))
    return result
