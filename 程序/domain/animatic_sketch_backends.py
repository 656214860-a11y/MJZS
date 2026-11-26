"""L2 分镜预演草图生成器接口：可插拔后端登记、分流、暂存烧录、运镜识别与替换图校验。

按 ``settings['animatic_sketch_backend']`` 分流，默认 ``comfy_local``（本地 ComfyUI），
同时内建免费后端 ``text_card``（纯本地 Pillow 文字分镜卡）与 ``gflow_cli``（Google Flow）。
会产生费用的后端默认关闭，须在设置中显式开启 ``animatic_allow_paid_sketch``。
纯 L2 模块：零同层 domain/* 依赖；外部执行器全部由编排层注入，本模块不构造网络客户端。
"""
import os
import threading
import time
from pathlib import Path

DEFAULT_BACKEND = 'comfy_local'
ALLOWED_IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')
MAX_IMAGE_BYTES = 20 * 1024 * 1024
SKETCH_PROMPT_PREFIX = '只生成分镜预演草图，不是正式资产或首帧。\n'
_DEFAULT_CARD_SIZE = (1280, 720)
_MOTION_FIELDS = ('camera_movement', 'camera', 'movement', 'description', 'video_prompt')
_STATIC_HINTS = ('固定', '静止', 'static')
_MOTION_RULES = (
    ('zoom_in', ('拉近', 'zoom in', 'zoom_in', '推')),
    ('zoom_out', ('拉远', 'zoom out', 'zoom_out', '拉')),
    ('pan_left', ('左摇', '左移', 'pan left', 'pan_left')),
    ('pan_right', ('右摇', '右移', 'pan right', 'pan_right')),
)

BACKENDS = {}


def register(name, factory, *, paid=False, label=''):
    """登记一个草图生成后端；factory 须满足 ``(workspace, shot, references, settings) -> Path``。"""
    if not isinstance(name, str) or not name or name != name.strip():
        raise ValueError('草图生成后端名称须为不带首尾空白的非空字符串')
    if name in BACKENDS:
        raise ValueError('草图生成后端已登记：' + name)
    if not callable(factory):
        raise TypeError('草图生成后端的 factory 必须是可调用对象')
    BACKENDS[name] = {'name': name, 'factory': factory, 'paid': bool(paid), 'label': str(label)}


def unregister(name):
    """移除已登记后端（供测试清理）；未登记时不报错。"""
    BACKENDS.pop(name, None)


def list_backends():
    """按名称排序的只读元数据副本（name/paid/label），不暴露 factory 本体。"""
    return [{'name': entry['name'], 'paid': entry['paid'], 'label': entry['label']}
            for entry in (BACKENDS[name] for name in sorted(BACKENDS))]


def comfy_local_render(workspace, shot, references, settings, *, client=None):
    """默认 comfy_local 后端：本地 ComfyUI 参考图工作流、固定种子、超时不重投。

    客户端须由编排层注入：优先 client 参数，其次 ``settings['comfy_client']``；
    两者都缺时报中文错——本模块不构造网络客户端（外发点登记在注入方）。
    """
    client = client or settings.get('comfy_client')
    if client is None:
        raise ValueError('缺少本地 ComfyUI 客户端，请注入 client 参数或 comfy_client 设置')
    cfg = settings.get('reference_config') or client.reference_config()
    graph = client.reference_graph(SKETCH_PROMPT_PREFIX + shot['prompt'], references, cfg)
    seed = int(settings.get('seed', 1))
    for node in graph.values():
        inputs = node.get('inputs', {})
        for key in ('seed', 'noise_seed'):
            if key in inputs:
                inputs[key] = seed
    record = client.submit_graph(workspace, 'scenes', shot['prompt'], graph)
    deadline = time.monotonic() + float(settings.get('timeout', 600))
    while time.monotonic() < deadline:
        files = client.collect(workspace, record)
        if isinstance(files, list) and files:
            return Path(files[0])
        time.sleep(1)
    raise ValueError('ComfyUI 仍在排队或生成，请人工核查任务；不自动重复提交')


def create(settings=None):
    """按设置分流草图后端，返回 ``(workspace, shot, references, settings) -> Path`` 可调用对象。"""
    resolved = dict(settings or {})
    name = resolved.get('animatic_sketch_backend') or DEFAULT_BACKEND
    entry = BACKENDS.get(name)
    if entry is None:
        raise ValueError('未知的草图生成后端：' + str(name))
    if entry['paid'] and resolved.get('animatic_allow_paid_sketch') is not True:
        raise ValueError('付费草图后端默认关闭，需在设置中显式开启付费草图后端')
    factory = entry['factory']

    def render(workspace, shot, references, run_settings=None):
        return factory(workspace, shot, references,
                       resolved if run_settings is None else run_settings)

    return render


def validate_imported_sketch(path):
    """校验每镜导入替换图：存在、PNG/JPEG/WebP、0 < 大小 <= 20MB；返回 (小写后缀, 原始字节)。"""
    candidate = Path(path)
    suffix = candidate.suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ValueError('替换图格式不支持，请选择 PNG、JPEG 或 WebP 图片：' + candidate.name)
    try:
        raw = candidate.read_bytes()
    except OSError:
        raise ValueError('替换图不存在或无法读取：' + candidate.name) from None
    if not raw:
        raise ValueError('替换图为空文件：' + candidate.name)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError('替换图超过 20 MB 大小上限：' + candidate.name)
    return suffix, raw


def _dialogue_text(raw):
    if raw is None:
        return ''
    if isinstance(raw, dict):
        return _dialogue_text(raw.get('text') or raw.get('line'))
    if isinstance(raw, (list, tuple)):
        return '。'.join(part for part in (_dialogue_text(item) for item in raw) if part)
    return str(raw).strip()


def _format_seconds(seconds):
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return '0s'
    if abs(value - round(value)) < 1e-6:
        return '%ds' % int(round(value))
    return '%.1fs' % value


def _format_timecode(start_seconds):
    try:
        total = max(0, int(round(float(start_seconds))))
    except (TypeError, ValueError):
        total = 0
    return '%02d:%02d' % (total // 60, total % 60)


def _load_font(size):
    from PIL import ImageFont
    windir = Path(os.environ.get('WINDIR', r'C:\Windows'))
    candidates = (
        windir / 'Fonts' / 'msyh.ttc',
        Path(r'C:\Windows\Fonts\msyh.ttc'),
        windir / 'Fonts' / 'simhei.ttf',
        Path(r'C:\Windows\Fonts\simhei.ttf'),
        Path('simhei.ttf'),
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), max(10, int(size)))
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def _text_width(draw, text, font):
    if hasattr(draw, 'textlength'):
        return float(draw.textlength(text, font=font))
    box = draw.textbbox((0, 0), text, font=font)
    return float(box[2] - box[0])


def _wrap_lines(draw, text, font, max_width, max_lines):
    lines = []
    for paragraph in str(text or '').splitlines() or ['']:
        current = ''
        for ch in paragraph:
            trial = current + ch
            if current and _text_width(draw, trial, font) > max_width:
                lines.append(current)
                current = ch
                if len(lines) >= max_lines:
                    return lines[:max_lines]
            else:
                current = trial
        if current:
            lines.append(current)
            if len(lines) >= max_lines:
                return lines[:max_lines]
    return lines[:max_lines]


def _card_dimensions(settings):
    spec = settings.get('spec') if isinstance(settings, dict) else None
    width = int((spec or {}).get('width') or _DEFAULT_CARD_SIZE[0])
    height = int((spec or {}).get('height') or _DEFAULT_CARD_SIZE[1])
    return max(64, width), max(64, height)


def text_card_render(workspace, shot, references, settings):
    """REQ-S04-100：纯本地 Pillow 文字分镜卡（零成本、无网络/ComfyUI 依赖）。"""
    from PIL import Image, ImageDraw
    width, height = _card_dimensions(settings)
    shot = shot if isinstance(shot, dict) else {}
    shot_id = str(shot.get('id') or 'SH001')
    seconds = shot.get('seconds') or shot.get('duration') or shot.get('estimated_duration') or 0
    shot_size = str(shot.get('shot_size') or shot.get('camera_size') or shot.get('framing') or '').strip()
    location = str(shot.get('location') or shot.get('scene') or '').strip()
    description = str(shot.get('description') or shot.get('prompt')
                      or shot.get('image_prompt') or shot.get('video_prompt') or '').strip()
    dialogue = _dialogue_text(shot.get('dialogue'))

    canvas = Image.new('RGB', (width, height), (24, 28, 36))
    draw = ImageDraw.Draw(canvas)
    pad = max(20, int(min(width, height) * 0.045))
    header_h = max(48, int(height * 0.11))
    footer_h = max(56, int(height * 0.16)) if dialogue else 0
    title_font = _load_font(max(16, int(min(width, height) * 0.036)))
    body_font = _load_font(max(14, int(min(width, height) * 0.032)))
    sub_font = _load_font(max(13, int(min(width, height) * 0.028)))

    draw.rectangle((0, 0, width, header_h), fill=(36, 44, 58))
    header_parts = [shot_id, _format_seconds(seconds)]
    meta = ' / '.join(part for part in (shot_size, location) if part)
    if meta:
        header_parts.append(meta)
    draw.text((pad, max(8, (header_h - int(min(width, height) * 0.04)) // 2)),
              ' · '.join(header_parts), fill=(240, 244, 248), font=title_font)

    body_top = header_h + pad
    body_bottom = height - footer_h - pad
    line_step = max(20, int(min(width, height) * 0.046))
    max_body_lines = max(1, (body_bottom - body_top) // line_step)
    for idx, line in enumerate(_wrap_lines(draw, description or shot_id, body_font,
                                           max(40, width - 2 * pad), max_body_lines)):
        draw.text((pad, body_top + idx * line_step), line, fill=(224, 230, 238), font=body_font)

    if dialogue:
        footer_top = height - footer_h
        draw.rectangle((0, footer_top, width, height), fill=(16, 20, 28))
        sub_step = max(18, int(min(width, height) * 0.04))
        sub_lines = _wrap_lines(draw, dialogue, sub_font, max(40, width - 2 * pad), 2)
        for idx, line in enumerate(sub_lines):
            draw.text((pad, footer_top + max(10, pad // 2) + idx * sub_step),
                      line, fill=(255, 236, 179), font=sub_font)

    temp_target = Path(workspace) / ('%s_card.png' % shot_id)
    temp_target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(temp_target, format='PNG')
    return temp_target


def gflow_cli_render(workspace, shot, references, settings, *, generate=None):
    """REQ-S04-101：Google Flow（gflow-cli）免费草图后端；执行器与配置由 L3 注入。"""
    resolved = settings if isinstance(settings, dict) else {}
    runner = generate or resolved.get('gflow_generate')
    config = resolved.get('gflow_config')
    if not callable(runner) or not isinstance(config, dict) or not config:
        raise ValueError('请先在模型管理配置 Google Flow 账号与 gflow.exe')
    shot_id = str((shot or {}).get('id') or 'SH001')
    prompt = SKETCH_PROMPT_PREFIX + str((shot or {}).get('prompt') or '')
    destination = Path(workspace) / ('%s_gflow.png' % shot_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stop = resolved.get('gflow_stop') or resolved.get('stop') or threading.Event()
    runner(config, prompt, list(references or ()), destination, stop)
    if not destination.is_file() or not destination.stat().st_size:
        raise ValueError('Google Flow 未生成有效草图，请检查配置')
    return destination


def render_overlay_frame(image_path, destination, *, shot_id, seconds, start_seconds, dialogue=''):
    """REQ-S04-103：在暂存副本上叠加半透明顶栏与临时对白字幕，绝不修改原图。"""
    from PIL import Image, ImageDraw
    src_path = Path(image_path).resolve()
    temp_dest = Path(destination)
    if src_path == temp_dest.resolve():
        raise ValueError('烧录目标路径不得覆盖原图')
    with Image.open(src_path) as opened:
        base = opened.convert('RGBA')
    width, height = base.size
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    pad = max(12, int(min(width, height) * 0.025))
    top_font = _load_font(max(13, int(height * 0.032)))
    header_text = '%s · %s · %s' % (shot_id, _format_seconds(seconds), _format_timecode(start_seconds))
    top_h = max(32, int(height * 0.075))
    draw.rectangle((0, 0, width, top_h), fill=(0, 0, 0, 150))
    draw.text((pad, max(6, (top_h - int(height * 0.036)) // 2)),
              header_text, fill=(255, 255, 255, 255), font=top_font)

    subtitle = _dialogue_text(dialogue)
    if subtitle:
        sub_font = _load_font(max(13, int(height * 0.034)))
        line_step = max(18, int(height * 0.044))
        lines = _wrap_lines(draw, subtitle, sub_font, max(40, width - 2 * pad), 2)
        bar_h = max(36, len(lines) * line_step + pad)
        bar_top = max(top_h, height - bar_h)
        draw.rectangle((0, bar_top, width, height), fill=(0, 0, 0, 165))
        for idx, line in enumerate(lines):
            draw.text((pad, bar_top + pad // 2 + idx * line_step),
                      line, fill=(255, 248, 214, 255), font=sub_font)

    merged = Image.alpha_composite(base, overlay).convert('RGB')
    temp_dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = temp_dest.suffix.lower()
    fmt = 'JPEG' if suffix in ('.jpg', '.jpeg') else ('WEBP' if suffix == '.webp' else 'PNG')
    merged.save(temp_dest, format=fmt)
    return temp_dest


def infer_motion(shot):
    """REQ-S04-104：按运镜/画面描述映射 2D Ken Burns 动效类型。"""
    if not isinstance(shot, dict):
        return 'static'
    for field in _MOTION_FIELDS:
        text = str(shot.get(field) or '').strip().lower()
        if not text:
            continue
        for motion, keywords in _MOTION_RULES:
            if any(keyword in text for keyword in keywords):
                return motion
        if field in ('camera_movement', 'movement') and any(hint in text for hint in _STATIC_HINTS):
            return 'static'
    return 'static'


register(DEFAULT_BACKEND, comfy_local_render, label='本地 ComfyUI 草图')
register('text_card', text_card_render, paid=False, label='文字分镜卡（零成本）')
register('gflow_cli', gflow_cli_render, paid=False, label='Google Flow（gflow-cli 免费）')
