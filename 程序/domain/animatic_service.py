"""L2 分镜预演：本地草图与临时声音编排，正式成果仅经注入的 L3 发布器。"""
import hashlib
import json
import math
import re
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path

import infra.file_cache as file_cache
import contract.artifact_schema as artifact_schema
import infra.broadcaster as broadcaster
from contract.project_context import ProjectContext
from contract.service_contract import success
from contract.stage_path_service import write_dir
from contract.file_naming import generate_existing

MANIFEST = 'animatic_manifest.json'
CONFIRMATIONS = ('rhythm', 'duration', 'dialogue_sync')


def _manifest_path(root):
    return write_dir(Path(root), 'animatic') / MANIFEST


def _future_blocked(root):
    """写入口守卫（G8/D4-d）：盘上清单为 ``future`` 时发一次【警告】并返回 True（拒写）。"""
    try:
        existing = file_cache.read_json(_manifest_path(root))
    except (OSError, ValueError):
        existing = None
    if artifact_schema.classify('animatic_manifest', existing) != 'future':
        return False
    broadcaster.warn_once('artifact_future:animatic_manifest',
                          'Animatic 清单是更新版本写的产物，本版程序拒绝覆盖；请升级程序或移走该文件')
    return True


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_bundle(artifacts):
    """发布前验证清单与所有媒体字节一一对应，人工确认不得由生成器代签。"""
    try:
        manifest = json.loads(artifacts[MANIFEST])
        files = manifest['files']
        if manifest.get('kind') != 'animatic' or set(files) != set(artifacts) - {MANIFEST}:
            return False
        if manifest.get('confirmed') != dict.fromkeys(CONFIRMATIONS, False):
            return False
        if manifest['video'] not in files or manifest['audio'] not in files:
            return False
        if not manifest['shots'] or any(row['image'] not in files for row in manifest['shots']):
            return False
        return all(artifacts[name] and digest(artifacts[name]) == expected for name, expected in files.items())
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def shots_of(storyboard):
    """显式镜头 ID、提示词与时长；不从缺失字段猜测创作要求。"""
    result = []
    for row in storyboard.get('shots', []):
        sid = str(row.get('id', ''))
        prompt = str(row.get('image_prompt') or row.get('prompt') or row.get('video_prompt') or row.get('description') or '').strip()
        seconds = float(row.get('estimated_duration') or row.get('duration') or 0)
        if not re.fullmatch(r'[A-Za-z0-9_-]+', sid) or not prompt:
            raise ValueError('分镜需要安全且唯一的镜头 ID 与图片提示词')
        if not math.isfinite(seconds) or not 0 < seconds <= 600:
            raise ValueError('分镜缺少有效镜头时长')
        result.append({'id': sid, 'prompt': prompt, 'seconds': seconds,
                       'batch': str(row.get('batch_id') or 'default')})
    if not result or len({row['id'] for row in result}) != len(result):
        raise ValueError('分镜为空或镜头 ID 重复')
    return result


def local_sketch(workspace, shot, references, settings, *, client=None):
    """复用 Comfy 参考图图谱与提交回执；结果不确定时绝不盲目重投。"""
    from infra.comfy_service import Comfy
    client = client or Comfy(settings.get('url', 'http://127.0.0.1:8188'))
    cfg = settings.get('reference_config') or client.reference_config()
    graph = client.reference_graph('只生成分镜预演草图，不是正式资产或首帧。\n' + shot['prompt'], references, cfg)
    seed = int(settings.get('seed', 1))
    for node in graph.values():
        inputs = node.get('inputs', {})
        for key in ('seed', 'noise_seed'):
            if key in inputs:
                inputs[key] = seed
    record = client.submit_graph(workspace, 'scenes', shot['prompt'], graph)
    return _collect_sketch(client, workspace, record, settings)


def _collect_sketch(client, workspace, record, settings):
    deadline = time.monotonic() + float(settings.get('timeout', 600))
    while time.monotonic() < deadline:
        files = client.collect(workspace, record)
        if isinstance(files, list) and files:
            return Path(files[0])
        time.sleep(1)
    raise ValueError('ComfyUI 仍在排队或生成，请人工核查任务；不自动重复提交')


def prepare_reference(workspace, prompt, model, settings, *, publish, client=None):
    """本地文字草图复用既有 Comfy 提交器；只由 L3 发布到共享参考图目录。"""
    from infra.comfy_service import Comfy
    if not str(prompt).strip() or not str(model).strip():
        raise ValueError('请填写参考图描述与本地已安装模型名称')
    client = client or Comfy(settings.get('url', 'http://127.0.0.1:8188'))
    record = client.submit(workspace, 'scenes', prompt, model)
    image = _collect_sketch(client, workspace, record, settings)
    return success(publish((image,)))


def build_bundle(context, source, references, audio, settings, *, publish, write_temporary, render=local_sketch,
                 assemble=None, run_batches=None, workspace=None, spec=None):
    """所有生成发生在暂存区；整包验证后才交给发布器。"""
    if not isinstance(context, ProjectContext) or not callable(publish):
        raise TypeError('分镜预演需要 L3 注入上下文与发布器')
    root = context.root.resolve()
    source = Path(source).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError('请选择本项目内的分镜初稿')
    storyboard, raw_source, _signature = file_cache.read_stable_json_snapshot(source)
    shots = shots_of(storyboard)
    refs = tuple(Path(path).resolve() for path in references)
    if not refs or any(not path.is_file() or not path.stat().st_size for path in refs):
        raise ValueError('请先准备共享参考图')
    if assemble is None:
        from domain.edit_service import assemble_image_timeline
        assemble = assemble_image_timeline
    # L3 的持久工作区保留 ComfyUI 回执，未知提交结果不能随临时目录清理而丢失。
    workspace_context = nullcontext(workspace) if workspace is not None else tempfile.TemporaryDirectory(prefix='animatic-')
    with workspace_context as temporary:
        scratch = Path(temporary)
        if audio is None:
            from domain.tts_api import synthesize, read_settings, script_signature
            text = str(settings.get('tts_text') or '').strip()
            if not text:
                raise ValueError('请选择临时音频或填写临时 TTS 文本')
            tts_settings = read_settings()
            signature = script_signature(text, tts_settings)
            audio = scratch / ('temporary-' + signature + '.mp3')
            if not audio.is_file() or not audio.stat().st_size:
                request_id = 'tts-previs:' + signature if workspace is not None else None
                write_temporary(audio, synthesize(text, settings=tts_settings, project=root, request_id=request_id))
        audio = Path(audio)
        if not audio.is_file() or not audio.stat().st_size:
            raise ValueError('临时音频为空或不存在')
        batches = {}
        for shot in shots:
            batches.setdefault(shot['batch'], []).append(shot)

        def one_batch(rows):
            from infra.comfy_service import ComfyGenerationFailed
            outputs = []
            for shot in rows:
                workspace = scratch / shot['id']
                workspace.mkdir(exist_ok=True)
                for attempt in range(int(settings.get('retry_attempts', 0)) + 1):
                    attempt_dir = workspace / ('attempt-' + str(attempt))
                    attempt_dir.mkdir(exist_ok=True)
                    try:
                        image = render(attempt_dir, shot, refs, settings)
                        outputs.append((shot['id'], image))
                        break
                    except ComfyGenerationFailed:
                        if attempt == int(settings.get('retry_attempts', 0)):
                            raise ValueError('镜头 ' + shot['id'] + ' 生成失败且重试耗尽，请人工核查') from None
            return outputs

        groups = list(batches.values())
        generated = run_batches(groups, one_batch) if run_batches else map(one_batch, groups)
        images = dict(pair for group in generated for pair in group)
        from contract.platform_tools import tool_path
        video = assemble([images[row['id']] for row in shots], [row['seconds'] for row in shots],
                         audio, scratch / 'animatic.mp4',
                         ffmpeg=tool_path('ffmpeg', configured=settings.get('ffmpeg')),
                         ffprobe=tool_path('ffprobe', configured=settings.get('ffprobe')),
                         write_temporary=write_temporary, spec=spec)
        audio_name = 'assets/' + generate_existing('animatic_audio', suffix=audio.suffix.lower())
        artifacts = {'assets/animatic.mp4': Path(video).read_bytes(), audio_name: audio.read_bytes()}
        for shot in shots:
            image = Path(images[shot['id']])
            name = 'assets/shots/' + generate_existing('animatic_shot', shot_id=shot['id'], suffix=image.suffix.lower())
            artifacts[name] = image.read_bytes()
            shot['image'] = name
        if source.read_bytes() != raw_source:
            raise ValueError('生成期间分镜已变化，请重新生成；本次不发布')
        # D4-e/G8：正常写入双写 schema_version 与旧键 version，旧版程序仍能读。
        manifest = artifact_schema.stamp('animatic_manifest', {
            'version': 1, 'kind': 'animatic', 'source': source.relative_to(root).as_posix(),
            'source_sha256': digest(raw_source), 'shots': shots, 'video': 'assets/animatic.mp4',
            'audio': audio_name,
            'files': {name: digest(data) for name, data in artifacts.items()},
            'confirmed': {key: False for key in CONFIRMATIONS}})
        artifacts[MANIFEST] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
        if _future_blocked(root):
            raise ValueError('Animatic 清单是更新版本写的产物，本版程序拒绝覆盖；请升级程序或移走该文件')
        return success(publish(artifacts))


def evidence(project, *, require_confirmation=True):
    """文件完整性、源版本与三项人工确认共同决定 SG-B；不相信任务文本。"""
    root = Path(project).resolve()
    folder = write_dir(root, 'animatic').resolve()
    try:
        manifest = file_cache.read_json(folder / MANIFEST)
        # D4-c/D4-d：属主读取点分类计数；future 清单照常参与核验（可读），不写盘不提示。
        state = artifact_schema.classify('animatic_manifest', manifest)
        artifact_schema.note_read_state('animatic_manifest', state)
        if not isinstance(manifest, dict) or manifest.get('kind') != 'animatic':
            raise ValueError('尚无 Animatic 成果')
        source = (root / manifest['source']).resolve()
        if not source.is_relative_to(root) or file_cache.file_digest(source) != manifest['source_sha256']:
            raise ValueError('分镜已变化，需要重新预演')
        files = manifest['files']
        if not files or manifest['video'] not in files or manifest['audio'] not in files:
            raise ValueError('预演缺少视频或临时音频')
        for name, expected in files.items():
            path = (folder / name).resolve()
            if not path.is_relative_to(folder) or not path.is_file() or not path.stat().st_size:
                raise ValueError('预演成果缺失或路径越界')
            if file_cache.file_digest(path) != expected:
                raise ValueError('预演成果已变化，需要重新生成并确认')
        if not manifest.get('shots') or any(row.get('image') not in files for row in manifest['shots']):
            raise ValueError('预演镜头图不完整')
        if require_confirmation and not all(manifest.get('confirmed', {}).get(key) is True for key in CONFIRMATIONS):
            raise ValueError('请确认节奏、时长和对白同步')
        return True, ''
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False, '分镜预演未就绪、源文件已变化，或节奏／时长／对白同步尚未确认'
