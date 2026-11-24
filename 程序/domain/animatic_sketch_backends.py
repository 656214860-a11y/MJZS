"""L2 分镜预演草图生成器接口：可插拔后端登记、分流与导入替换图校验（REQ-S04-78/79）。

按 ``settings['animatic_sketch_backend']`` 分流，默认 ``comfy_local``（本地 ComfyUI）。
会产生费用的后端默认关闭，须在设置中显式开启 ``animatic_allow_paid_sketch``。
纯 L2 模块：零同层 domain/* 依赖；默认后端的 ComfyUI 客户端由编排层注入
（client 参数或 ``settings['comfy_client']``，外发点登记在注入方），本模块不构造
网络客户端；``ComfyGenerationFailed`` 是唯一可重试异常，提交结果不确定时绝不自动重投。
"""
import time
from pathlib import Path

DEFAULT_BACKEND = 'comfy_local'
ALLOWED_IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')
MAX_IMAGE_BYTES = 20 * 1024 * 1024
SKETCH_PROMPT_PREFIX = '只生成分镜预演草图，不是正式资产或首帧。\n'

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


register(DEFAULT_BACKEND, comfy_local_render, label='本地 ComfyUI 草图')
