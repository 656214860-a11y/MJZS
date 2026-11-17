# -*- coding: utf-8 -*-
"""白模视频当参考视频接进视频接口（第 8 轮收口）。

「白模 · 上传」那一列勾上之后，这一镜的白模预演视频（白模预演阶段做出来的 mp4）要跟着这一次
视频生成一起提交。这一份管三件事，别处不再各写一遍：

1. **认产物**：从镜头目录的 `预演记录.json` 取 `preview`，验存在／后缀／空文件／大小 → 一份描述；
2. **认目标**：这一次用哪个接口（本地 ComfyUI 还是线上哪家哪个模型）——它认不认参考视频；
3. **拼槽位**：按目标接口的形状把参考视频塞进请求（万相那支进 `media`，火山那支进 `content`）。

**能力表只有下面 `SUPPORT` 这一处**：谁认、放哪个槽位、上限多少，全在那一张表里。表里没有的
组合就是「这个接口不吃参考视频」——照旧当场拦下、不扣预算，而且那句话里要写清「换哪个模型」。

一句话口径（第 8 轮）：**接不上的仍然拦，但不再是一句「不支持」**。
"""
import base64
import hashlib
from pathlib import Path
import contract.pet_bus as pet_bus

SUFFIXES = ('.mp4', '.webm', '.mov')
MIME = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime'}
DEFAULT_MAX_MB = 20

# ── 能力表（唯一口径）────────────────────────────────────────────────────────
# (服务商, 模型前缀们, 槽位, 视频上限 MB, 说明)
#   槽位 'media'  ：万相那支——`input.media` 里加一条 reference_video；
#   槽位 'content'：火山那支——`content` 里加一条 video_url／role=reference_video。
# 本地 ComfyUI 的 H3（Ref2VA）只吃参考图，不进这张表：勾了它带不了，拦下时给替代方案。
SUPPORT = (
    ('wan', ('wan2.7-r2v',), 'media', DEFAULT_MAX_MB,
     '万相 2.7-r2v：参考视频与首帧、资产图同在 input.media 列表里'),
    ('volcengine', ('doubao-seedance-2-0-', 'doubao-seedance-2-5-'), 'content', DEFAULT_MAX_MB,
     'Seedance 2.0／2.5：参考视频与参考图同在 content 列表里'),
)
SUPPORT_LABELS = ('万相 2.7-r2v', 'Seedance 2.0／2.5')


def target(cfg):
    """这一次要用哪个接口：返回 (服务商, 模型)。

    线上那两支的配置里有 `cloud_provider`（wan／volcengine）；本地那一支没有这一项，
    一律算成 ('local', 模型)——本地 H3 带不了参考视频，拦下时按「本地」说法给替代方案。
    """
    cfg = cfg or {}
    provider = str(cfg.get('cloud_provider', '')).strip().lower()
    if provider in ('wan', 'volcengine'):
        return provider, str(cfg.get('model', '')).strip()
    return 'local', str(cfg.get('model', '')).strip()


def support(provider, model):
    """这个接口认不认参考视频：认就回那一行口径（槽位与上限），不认回 None。"""
    for name, prefixes, slot, max_mb, usage in SUPPORT:
        if provider == name and any(str(model).startswith(prefix) for prefix in prefixes):
            return {'provider': name, 'slot': slot, 'max_mb': max_mb, 'usage': usage}
    return None


def supported_text():
    """「能带白模视频的接口」那一句（拦下时要写进错误里）。"""
    return '、'.join(SUPPORT_LABELS)


def unsupported_reason(provider, model):
    """接不上时那句话：为什么，以及改用哪个。"""
    if provider == 'local':
        return ('本地 ComfyUI 的 H3 工作流只吃参考图（最多 9 张），没有参考视频的入口；'
                '要带白模视频请改用线上 ' + supported_text() + '，或取消「白模 · 上传」再生成。')
    return ('模型 ' + (model or '当前模型') + ' 的接口不吃白模参考视频（能吃的：'
            + supported_text() + '）；请换模型，或取消「白模 · 上传」再生成。')


# ── 认产物 ────────────────────────────────────────────────────────────────────
def shot_folder(project, sid):
    """这一镜的白模目录：与白模预演阶段同一套口径（这一份不自己发明路径）。"""
    # 白模页面会把当前 Blender 工作区传给服务；这里必须经同一层，
    # 否则在自定义工作区（以及测试替换工作区）中会读到另一套目录。
    from ui.white_model import shot_directory
    return shot_directory(project, sid)


def record_of(folder, record=None):
    """读那一份 `预演记录.json`（已经拿到就传进来，别再读一遍盘）。"""
    if record is not None:
        return record
    from domain.white_model_service import read_record
    return read_record(folder)


def descriptor(project, sid, cfg, record=None):
    """验过再给一份描述；不合规当场抛（调用方不用再判一次）。

    没勾「白模 · 上传」的镜头不该走到这儿——那一条由调用方先判（`validate_video_submission`
    和 `prepare` 都先看 `upload_white_model`）。
    """
    folder = shot_folder(project, sid)
    data = record_of(folder, record)
    value = str(data.get('preview') or '').strip()
    path = Path(value) if value else None
    if not path or not path.is_file():
        raise ValueError('勾选的白模视频不存在，请先到'+pet_bus.stage_step('previs')+'制作并刷新白模')
    suffix = path.suffix.lower()
    if suffix not in SUFFIXES:
        raise ValueError('白模视频只认 mp4／webm／mov：' + path.name)
    size = path.stat().st_size
    if not size:
        raise ValueError('白模视频是空文件，请重新制作：' + path.name)
    provider, model = target(cfg)
    rule = support(provider, model)
    if rule is None:
        raise ValueError(unsupported_reason(provider, model))
    limit = int(rule['max_mb']) * 1024 * 1024
    if limit and size > limit:
        raise ValueError('白模视频 ' + path.name + ' 有 ' + str(round(size / 1024.0 / 1024.0, 1))
                         + ' MB，超过这个接口的上限（' + str(rule['max_mb']) + ' MB 以内）：'
                         + '请压小或缩短预演视频，不会自动截断')
    return {'sid': str(sid), 'path': str(path), 'name': path.name, 'suffix': suffix,
            'bytes': size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'provider': rule['provider'], 'model': model, 'slot': rule['slot'],
            'usage': rule['usage']}


# ── 拼槽位 ────────────────────────────────────────────────────────────────────
def data_url(path, suffix=None):
    """读成 data URL（与资产图那条 `image_url` 同一个做法：直接内嵌进请求）。"""
    path = Path(path)
    mime = MIME.get(str(suffix or path.suffix).lower())
    if not mime:
        raise ValueError('白模视频只认 mp4／webm／mov：' + path.name)
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()


def entries(reference):
    """按目标接口的形状把参考视频拼成请求里的那一条（没有就回空表）。"""
    if not reference:
        return []
    url = data_url(reference['path'], reference.get('suffix'))
    slot = reference.get('slot')
    if slot == 'media':
        return [{'type': 'reference_video', 'url': url}]
    if slot == 'content':
        return [{'type': 'video_url', 'video_url': {'url': url}, 'role': 'reference_video'}]
    raise ValueError('不认识的参考视频槽位：' + repr(slot))


def prompt_line(reference=None):
    """提示词里那一句：这份视频是干什么用的（只借动作与机位，不抄白模外观）。"""
    return ('白模预演视频＝本镜的动作与机位参考：人物站位、动作起止、镜头运动照它走；'
            '只借动作与机位，不复制白模的外观与材质。')


def brief(reference):
    """记录里那一行（台账／验收看得懂的一句话）。"""
    if not reference:
        return ''
    return (reference['name'] + '（' + str(round(reference['bytes'] / 1024.0 / 1024.0, 1))
            + ' MB，' + reference['provider'] + '／' + reference['model']
            + '，sha256 ' + reference['sha256'][:12] + '）')
