"""OpenAI 兼容文本转语音（TTS）：支持 tts-1 及任何 OpenAI 兼容 /audio/speech 端点。"""
import base64
import hashlib
import json
import math
import os
import re
from pathlib import Path
from agent.core import read_json
from contract.error_codes import code_of
from contract.project_context import ProjectContext
from urllib.parse import urlparse
from infra.app_logging import swallowed as _swallowed
from infra.seedream_api import protect

DEFAULT_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "tts-1"
KEY_ENV = "TTS_API_KEY"                     # 第 65 期任务 1：统一那份 .env 里的变量名
# 单句配音音频上限：文本 ≤4000 字，64 MiB 足够覆盖高码率短音频；
# 同时给 http_client 的有界读取一个明确边界（旧实现 response.read() 无上限）。
TTS_AUDIO_MAX_BYTES = 64 * 1024 * 1024
# 结果未知：不自动重发，须人工核对后放开（sending／uncertain／unsaved）。
UNKNOWN_LINE_STATES = ('sending', 'uncertain', 'unsaved')


class TTSRejected(ValueError):
    """服务商明确拒绝（HTTP 4xx）：确定没成，可记 failed 并允许下次重发。"""


class TTSAcceptanceUnknown(ValueError):
    """服务商可能已受理这次 HTTP 请求；重复发送前需要核对。"""


def settings_path():
    return Path(os.environ["LOCALAPPDATA"]) / "漫剧制作助手" / "tts_settings.json"


def read_settings():
    defaults = {"base_url": DEFAULT_URL, "model": DEFAULT_MODEL, "voice": "alloy", "encrypted_key": "",
                "voices": {}, "speeds": {}, "voice_version": 0}
    data = read_json(settings_path())
    return {**defaults, **data} if isinstance(data, dict) else defaults


def _require_gateway(gateway, *operations):
    """L2 不自行落盘：发布器必须由 L3 明确注入。"""
    if not isinstance(gateway, dict):
        raise TypeError("TTS 发布必须由 L3 注入 gateway")
    missing = [name for name in operations if not callable(gateway.get(name))]
    if missing:
        raise TypeError("TTS gateway 缺少：" + "、".join(missing))
    return gateway


def _context(value):
    """TTS 的项目阶段路径只能由 L3 注入的上下文解析。"""
    if not isinstance(value, ProjectContext):
        raise TypeError("TTS 项目路径需要由 L3 注入 ProjectContext")
    return value


def write_settings(data, *, gateway=None):
    _require_gateway(gateway, "publish_json")["publish_json"](settings_path(), data)


def validate(base_url, model, voice, key):
    base_url = base_url.strip().rstrip("/")
    if base_url.endswith("/audio/speech"):
        base_url = base_url[:-len("/audio/speech")].rstrip("/")
    parsed = urlparse(base_url)
    try:
        parsed.port
    except ValueError:
        raise ValueError("接口端口无效") from None
    is_local = parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")
    if parsed.scheme != "https" and not is_local:
        raise ValueError("请使用 HTTPS 地址；本机服务可使用 HTTP")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() for c in base_url):
        raise ValueError("请填写不含密钥或查询参数的 API 根地址")
    model = model.strip()
    if not model or any(c.isspace() for c in model):
        raise ValueError("请填写 TTS 模型 ID")
    voice = voice.strip()
    if not voice or any(c.isspace() for c in voice):
        raise ValueError("请填写音色名称")
    if not key or not key.isascii() or any(c.isspace() for c in key):
        raise ValueError("请填写有效的 API Key")
    return {"base_url": base_url, "model": model, "voice": voice, "api_key": key}


def payload(text, model, voice, speed=1.0):
    return {"model": model, "input": text, "voice": voice, "speed": speed}


def save_key(base_url, model, voice, key, voices=None, speeds=None, *, gateway=None):
    """第 65 期任务 1：密钥写进统一那份 .env；这个设置文件里不再留密钥。"""
    value = validate(base_url, model, voice, key)
    data = read_settings()
    secret = value.pop("api_key")
    data.update(value)
    data.pop("encrypted_key", None)         # 老安装留下的那份密文一并清掉，免得盖住新钥匙
    if voices is not None:
        if not isinstance(voices, dict):
            raise ValueError("角色音色映射必须为 JSON 对象，例如 {'CHAR_001': 'voice_a'}")
        if data.get("voices") != voices:
            data["voice_version"] = int(data.get("voice_version") or 0) + 1
        data["voices"] = voices
    if speeds is not None:
        if not isinstance(speeds, dict):
            raise ValueError("角色语速映射必须为 JSON 对象，例如 {'CHAR_001': 1.2}")
        data["speeds"] = {k: coerce_speed(v) for k, v in speeds.items()}
    import infra.model_pool as model_pool
    model_pool.save_named_key(KEY_ENV, secret)
    write_settings(data, gateway=gateway)


def unified_key():
    """统一那份 .env（程序目录/private/.env）里的密钥；没有就是空串（第 65 期任务 1）。"""
    try:
        import infra.model_pool as model_pool
        return model_pool.named_key(KEY_ENV)
    except Exception:
        return ""


def load_key():
    """密钥的次序：统一那份 .env → 老安装留在本机加密那份（只读兼容）。"""
    unified = unified_key()
    if unified:
        return unified
    enc = read_settings().get("encrypted_key")
    if not enc:
        return ""
    try:
        return protect(base64.b64decode(enc), True).decode("utf-8")
    except Exception:
        # 密钥可能来自其他 Windows 用户或已损坏，按未配置处理。
        return ""


def coerce_speed(value):
    """把用户配置的音色语速收敛到 OpenAI 兼容范围 0.25–4.0，非法/非有限值默认 1.0。"""
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(speed):
        return 1.0
    return max(0.25, min(4.0, speed))


AUDIO_KINDS = ("dialogue", "narration", "bgm", "sfx", "full")
AUDIO_KIND_LABELS = {"dialogue": "对白", "narration": "旁白", "bgm": "BGM", "sfx": "音效", "full": "整轨"}
AUDIO_KIND_PREFIXES = {"narration": "旁白_", "bgm": "BGM_", "sfx": "音效_", "full": "整轨_"}


def audio_kind(name):
    """从文件名推断音轨用途；认不出按对白算（旧文件与直接落盘成果的默认口径）。"""
    text = str(name or "")
    for kind, prefix in AUDIO_KIND_PREFIXES.items():
        if prefix and text.startswith(prefix):
            return kind
    return "dialogue"


def marked_audio_name(stem, kind):
    """给非对白音轨一个可识别的用途前缀；对白保持原名（不破坏既有文件口径）。"""
    kind = kind if kind in AUDIO_KINDS else "dialogue"
    return AUDIO_KIND_PREFIXES.get(kind, "") + str(stem)



def voice_for(voices, speaker, name=""):
    """角色到音色的解析：按稳定角色 ID 优先，再退回显示名；都不命中给空串（用默认音色）。"""
    voices = voices if isinstance(voices, dict) else {}
    return voices.get(speaker) or voices.get(name) or ""


def missing_voices(entries, assets=None, voices=None):
    """列出「有台词但没配到音色」的角色（按稳定 ID 去重），供配音前检查。"""
    assets = assets if isinstance(assets, dict) else {}
    voices = voices if isinstance(voices, dict) else {}
    missing = {}
    for entry in entries or ():
        try:
            _sid, speaker, _text, _start, _end = entry
        except (TypeError, ValueError):
            continue
        speaker = str(speaker or "")
        if not speaker:
            continue
        item = assets.get(speaker) if isinstance(assets.get(speaker), dict) else {}
        name = str(item.get("name") or "")
        if not voice_for(voices, speaker, name):
            missing.setdefault(speaker, name or speaker)
    return [{"speaker": key, "name": value} for key, value in missing.items()]


def silent_lines(entries):
    """台词文本为空或只有空白的行：静音台词不该混进配音清单（按 ID／镜头列出）。"""
    silent = []
    for entry in entries or ():
        try:
            sid, speaker, text, _start, _end = entry
        except (TypeError, ValueError):
            continue
        if not str(text or "").strip():
            silent.append({"shot": str(sid or ""), "speaker": str(speaker or "")})
    return silent


def voice_snapshot(settings=None):
    """当前角色音色映射的快照：逐角色的音色、语速与映射版本号。"""
    settings = settings if isinstance(settings, dict) else read_settings()
    voices = settings.get("voices") if isinstance(settings.get("voices"), dict) else {}
    speeds = settings.get("speeds") if isinstance(settings.get("speeds"), dict) else {}
    return {"version": int(settings.get("voice_version") or 0),
            "voices": {key: {"voice": value, "speed": coerce_speed(speeds.get(key))}
                       for key, value in voices.items()}}



LINE_IDENTITY_FIELDS = ("shot_id", "text", "voice", "speed", "model", "endpoint")


def request_identity(settings, voice="", speed=1.0):
    """一次合成请求的身份（不含密钥）：服务商端点、模型唯一 ID、音色与采样参数。

    O12：缓存身份不能再只看台词／音色／语速——换了模型或换了服务商就是另一份缓存。
    """
    settings = settings if isinstance(settings, dict) else {}
    return {"endpoint": str(settings.get("base_url") or "").strip().rstrip("/"),
            "model": str(settings.get("model") or "").strip(),
            "voice": str(voice or "").strip(),
            "speed": coerce_speed(speed)}


def batch_identity(lines):
    """这一批清单用哪套配置（不含密钥）：端点、模型，以及逐句用到的音色与语速。"""
    def collect(key, coerce):
        return sorted({coerce(line.get(key)) for line in lines or ()})
    return {"endpoints": collect("endpoint", str),
            "models": collect("model", str),
            "voices": collect("voice", str),
            "speeds": collect("speed", coerce_speed)}


def freeze_settings(lines, settings=None):
    """批次开始时冻结的有效配置（不含密钥）：清单里写死的端点／模型优先。

    清单是空的话才退回读当前设置。这样长批次中途改设置，这一批仍按开批时那一套跑，
    不会一半旧模型一半新模型（O12）。
    """
    frozen = dict(settings) if isinstance(settings, dict) and settings else read_settings()
    for field, key in (("endpoint", "base_url"), ("model", "model")):
        values = {str(line.get(field) or "") for line in lines or ()}
        if len(values) == 1:
            value = values.pop()
            if value:
                frozen[key] = value
    return frozen


def build_lines(entries, assets=None, voices=None, speeds=None, *, settings=None):
    """把 timed_entries 的 (shot_id, speaker, text, start, end) 整理为逐句配音清单。

    每句同时记下这次请求的身份（端点／模型／音色／语速，不含密钥，O12）：换了模型或换了
    服务商就是另一份缓存，续跑时不会把旧配置生成的语音当成新配置的成品。
    """
    assets = assets if isinstance(assets, dict) else {}
    voices = voices if isinstance(voices, dict) else {}
    speeds = speeds if isinstance(speeds, dict) else {}
    settings = settings if isinstance(settings, dict) else {}
    lines = []
    for sid, speaker, text, start, end in entries:
        item = assets.get(speaker) if isinstance(assets.get(speaker), dict) else {}
        name = str(item.get("name") or speaker or "未注明角色")
        voice = voice_for(voices, speaker, name)
        speed = coerce_speed(speeds.get(speaker) or speeds.get(name))
        lines.append({"shot_id": sid, "speaker": speaker, "name": name, "text": text,
                      "start": start, "end": end,
                      **request_identity(settings, voice, speed)})
    return lines


def build_script(entries, assets=None):
    """把对白时间轴整理为整段配音文本：只念台词（不念角色名／编号），句间换行，空文本的句子跳过。"""
    return "\n".join(str(line["text"]) for line in build_lines(entries, assets)
                     if str(line["text"] or "").strip())


def script_signature(text, settings=None):
    """整段配音的内容指纹：台词、模型、音色或服务商端点变了才需重新付费合成。"""
    settings = settings if isinstance(settings, dict) else read_settings()
    payload_ = {"text": text, "model": settings.get("model"), "voice": settings.get("voice"),
                "endpoint": str(settings.get("base_url") or "").strip().rstrip("/")}
    return hashlib.sha256(json.dumps(payload_, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


FULL_TRACK_ATTEMPT_FILE = '整段配音尝试.json'
# 尝试账里「结果未知」的口径：预约后未见结果（sending）或发送后结果未知（unknown）。
FULL_TRACK_UNKNOWN_STATES = ('sending', 'unknown')


def _full_track_folder(context):
    from contract.project_stages import audio
    return audio(_context(context).root)


def _full_track_attempts(context):
    """整段配音尝试账：与成品标记同目录，按指纹记最近一次请求的序号与结果口径。"""
    data = read_json(_full_track_folder(context) / FULL_TRACK_ATTEMPT_FILE)
    records = data.get('attempts') if isinstance(data, dict) else None
    return dict(records) if isinstance(records, dict) else {}


def _save_full_track_attempts(context, records, gateway):
    _require_gateway(gateway, 'publish_json')['publish_json'](
        _full_track_folder(context) / FULL_TRACK_ATTEMPT_FILE, {'attempts': records})


def reserve_full_track_attempt(context, signature, *, confirmed=False, confirm=None, gateway=None):
    """预约整段配音的下一个请求号（指纹＋尝试序号）。

    上一次是确定失败直接用下一个序号；上一次结果未知（含预约后未发出）必须先确认，
    取消返回 None、不发请求。确认回调由 L3 注入，文案在这里统一。
    """
    ctx = _context(context)
    records = _full_track_attempts(ctx)
    entry = records.get(signature)
    entry = entry if isinstance(entry, dict) else {}
    if str(entry.get('state') or '') in FULL_TRACK_UNKNOWN_STATES and not confirmed:
        if confirm is None or not confirm('上一次配音请求结果未知，可能已扣费，确认重发？'):
            return None
    try:
        attempt = int(entry.get('attempt') or 0)
    except (TypeError, ValueError):
        attempt = 0
    attempt += 1
    request_id = 'tts-full:%s:%d' % (signature, attempt)
    records[signature] = {'attempt': attempt, 'request_id': request_id, 'state': 'sending'}
    _save_full_track_attempts(ctx, records, gateway)
    return request_id


def note_full_track_outcome(context, signature, request_id, outcome, *, gateway=None):
    """把整段配音尝试的结果口径写回尝试账；请求号已不是当前尝试时不覆盖。"""
    ctx = _context(context)
    records = _full_track_attempts(ctx)
    entry = records.get(signature)
    if not isinstance(entry, dict) or entry.get('request_id') != request_id:
        return False
    records[signature] = {**entry, 'state': outcome}
    _save_full_track_attempts(ctx, records, gateway)
    return True


def _complete_full_track_attempt(context, signature, gateway):
    """成品发布成功后把该指纹的尝试记为 done；没有尝试账（直接发布）时不补记。"""
    ctx = _context(context)
    records = _full_track_attempts(ctx)
    entry = records.get(signature)
    if not isinstance(entry, dict):
        return
    records[signature] = {**entry, 'state': 'done'}
    _save_full_track_attempts(ctx, records, gateway)


def reusable_full_track(context, signature):
    """Return the completed whole-track audio for an unchanged paid request, if any."""
    folder = _full_track_folder(context)
    marker = folder / '整段配音.json'
    previous = read_json(marker) if marker.is_file() else {}
    if not (isinstance(previous, dict) and previous.get('signature') == signature
            and previous.get('file')):
        return None
    path = Path(str(previous['file']))
    if path.is_absolute():
        # 旧格式绝对路径：文件还在就沿用；项目搬家后失效时退回同名文件在当前音频目录。
        if not (path.is_file() and path.stat().st_size > 0):
            path = folder / path.name
    else:
        # 新格式相对音频目录：项目目录搬家后仍能找回成品。
        path = folder / path
    if path.is_file() and path.stat().st_size > 0:
        return path
    return None


def publish_full_track(context, signature, raw, *, gateway=None):
    """Publish complete audio before its idempotence marker, preserving media on marker failure."""
    folder = _full_track_folder(context)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('配音_' + os.urandom(3).hex() + '.mp3')
    publish = _require_gateway(gateway, "publish_json", "publish_bytes")
    publish["publish_bytes"](path, raw)
    publish["publish_json"](folder / '整段配音.json', {'signature': signature, 'file': path.name})
    try:
        _complete_full_track_attempt(context, signature, publish)
    except Exception:
        _swallowed('tts_api.publish_full_track.attempt')
    return path


def synthesize_full_track(context, text, signature, request_id, *, settings=None, gateway=None):
    """整段配音发送：确定失败记 failed 可直接重发，结果未知记 unknown 须确认后才重发。"""
    ctx = _context(context)
    try:
        return synthesize(text, settings=settings, project=ctx.root, request_id=request_id)
    except Exception as exc:
        import urllib.error
        from infra.pet_llm import BudgetRejected
        duplicate = isinstance(exc, BudgetRejected) and '该请求已有记录' in str(exc)
        definite = (isinstance(exc, (TTSRejected, urllib.error.URLError))
                    or (isinstance(exc, BudgetRejected) and not duplicate))
        outcome = 'failed' if definite else 'unknown'
        try:
            note_full_track_outcome(ctx, signature, request_id, outcome, gateway=gateway)
        except Exception:
            _swallowed('tts_api.synthesize_full_track.outcome')
        if duplicate:
            raise ValueError('上一次配音请求未完成，请核对请求记录后重试') from None
        raise


def batch_signature(lines, episode=None):
    """逐句配音批次的内容指纹：文本、配音、语速或时间轴变化就算新批次。

    给了 episode 就把集标识一并纳入指纹：两集同名台词／音色不会共用同一批缓存目录
    （不给 episode 时与旧口径完全一致，老缓存仍可续用）。
    """
    payload = list(lines or ())
    if episode:
        payload = ["#episode:" + str(episode), *payload]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _save(path, data, *, gateway=None):
    _require_gateway(gateway, "publish_json")["publish_json"](path, data)


def resume_folder(root, lines, episode=None):
    """同内容（且同一集）的旧逐句配音目录：可续跑，已成功的句子不重复合成（避免重复扣费）。

    整批指纹对不上时退一步按集标识找该集最近的批次：改一句、插入一句或挪位置只重做
    变了的句子；没有 episode 的旧批次保持现状（只认整批指纹），不跨集匹配。
    """
    base = Path(root)
    if not base.is_dir():
        return None
    signature = batch_signature(lines, episode)
    latest = None
    for record in sorted(base.glob("*/批次.json"), reverse=True):
        data = read_json(record)
        if not isinstance(data, dict):
            continue
        if data.get("signature") == signature:
            return record.parent
        if latest is None and episode and str(data.get("episode") or "") == str(episode):
            latest = record.parent
    return latest


def line_name(index, line):
    unsafe = r'[<>:"/\\|?*\x00-\x1f]'
    safe = re.sub(unsafe, "_", str(line.get("name") or "")).strip(" .")[:20]
    shot = re.sub(unsafe, "_", str(line.get("shot_id")))[:40]
    return f'{index:03}_{shot}_{safe}_{float(line.get("start") or 0):.1f}s.mp3'


def _line_file_path(folder, name):
    """清单登记文件的定位：相对本批目录优先；指向旧批次的相对路径（相对「配音分句」目录）退回父目录解析。"""
    path = Path(folder) / str(name)
    if path.is_file():
        return path
    parent = Path(folder).parent / str(name)
    return parent if parent.is_file() else path


def _identity(entry, line):
    """句子身份（LINE_IDENTITY_FIELDS：镜头、文本、音色、语速、模型、端点）逐项相同——
    不含位置与起止时间：挪位置、改时长不算换句。"""
    return isinstance(entry, dict) and all(entry.get(key) == line.get(key) for key in LINE_IDENTITY_FIELDS)


def line_done(entry, folder):
    """这份旧清单条目是不是可沿用的成品：续跑与付费预览共用同一口径，避免两处判断走偏。

    O12：state 为 ok、登记了文件，并且要复核写入时记下的 sha256——只判「文件在不在」
    会把截断或损坏的成品当成已生成；旧清单没记摘要时退回「文件非空」。
    """
    if not (isinstance(entry, dict) and entry.get("state") == "ok" and entry.get("file")):
        return False
    path = _line_file_path(folder, entry["file"])
    if not path.is_file():
        return False
    digest = str(entry.get("sha256") or "")
    if not digest:
        try:
            return path.stat().st_size > 0
        except OSError:
            return False
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == digest
    except OSError:
        return False


def _line_error_text(state, detail):
    """第三方异常只保留 HTTP 状态或本地处理提示，供进度和时间轴共用。"""
    status = re.match(r'^TTS 请求失败（HTTP ([1-5][0-9]{2})）', str(detail))
    if status:
        return status.group()
    if state == 'unsaved':
        return '已付费未保存，请核对服务商记录和本机文件'
    if state == 'uncertain':
        return '配音受理情况待核实，请先核对服务商记录'
    return '配音未完成，请检查配音设置、网络和预算'


def _safe_manifest_rows(manifest):
    """续跑或人工放开旧批次时，也不将旧错误正文再写回磁盘。"""
    return [{**row, 'error': _line_error_text(row.get('state'), row['error'])}
            if isinstance(row, dict) and row.get('error') else row for row in manifest]


def _line_needs_review(entry):
    if not isinstance(entry, dict):
        return False
    if entry.get("state") in UNKNOWN_LINE_STATES:
        return True
    # 旧版把 HTTP 408 写成明确失败。按本程序生成的错误前缀识别，避免自动重发旧请求。
    return (entry.get("state") == "failed" and not entry.get("released_at")
            and str(entry.get("error") or "").startswith("TTS 请求失败（HTTP 408）"))


def _line_verdicts(lines, manifest, folder):
    """逐句在旧清单里的续跑判定：沿用 {新句序号: 旧条目} 与待核实 {新句序号: 旧条目清单序号}。

    句子按身份（不含位置与起止时间）在旧清单里查；同身份的句子按出现次序一一配对
    （第一处对第一处），避免两句指向同一个文件。沿用优先于待核实：成品在就不算结果未知。
    """
    entries = manifest if isinstance(manifest, list) else []
    usable = [entry for entry in entries if line_done(entry, folder)]
    done, taken = {}, set()
    for index, line in enumerate(lines, 1):
        for pos, entry in enumerate(usable):
            if pos in taken or not _identity(entry, line):
                continue
            taken.add(pos)
            done[index] = entry
            break
    blocked, claimed = {}, set()
    unknown = [pos for pos, entry in enumerate(entries, 1)
               if _line_needs_review(entry)]
    for index, line in enumerate(lines, 1):
        if index in done:
            continue
        for pos in unknown:
            if pos in claimed or not _identity(entries[pos - 1], line):
                continue
            claimed.add(pos)
            blocked[index] = pos
            break
    return done, blocked


def _require_object_entries(manifest, folder):
    """时间轴清单每条登记必须是对象：坏条目报出清单文件与第几项，不自动修清单（AUD-US05 E-14）。"""
    if isinstance(manifest, list):
        for index, entry in enumerate(manifest, 1):
            if not isinstance(entry, dict):
                raise ValueError('逐句配音清单 %s 第 %d 项不是对象，请核对或删除该批次目录'
                                 % (Path(folder) / '时间轴.json', index))


def publish_line(folder, manifest, index, line, raw, *, gateway=None):
    """原子发布单句音频后，再把它登记进可续跑时间轴。"""
    folder = Path(folder)
    name = line_name(index, line)
    publish = _require_gateway(gateway, "publish_json", "publish_bytes")
    publish["publish_bytes"](folder / name, raw)
    entry = {**line, "file": name, "state": "ok",
             "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if index <= len(manifest):
        manifest[index - 1] = entry
    else:
        manifest.append(entry)
    _save(folder / "时间轴.json", manifest, gateway=publish)
    return entry


def pending_lines(lines, folder):
    """这一批里还需要付费合成的句子序号（从 1 起）：点按钮前用它预估扣费规模。"""
    folder = Path(folder)
    manifest = read_json(folder / "时间轴.json")
    done, _blocked = _line_verdicts(lines, manifest, folder)
    return [index for index in range(1, len(lines) + 1) if index not in done]


def batch_cost_preview(project, lines, folder, settings=None):
    """只读报价：已完成与结果未知的句子不计入新增请求。"""
    from infra.pet_llm import RequestLedger, BudgetRejected
    folder = Path(folder)
    manifest = read_json(folder / '时间轴.json')
    _require_object_entries(manifest, folder)
    done, blocked = _line_verdicts(lines, manifest, folder)
    pending, unknown = [], 0
    for index, line in enumerate(lines, 1):
        if index in done:
            continue
        if index in blocked:
            unknown += 1
            continue
        text = line.get('text', '')
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise BudgetRejected('配音文本须为1至4000字')
        coerce_speed(line.get('speed', 1.0))
        pending.append(index)
    chars = sum(len(lines[index - 1]['text']) for index in pending)
    tip = f'新增 {len(pending)} 句，共 {chars} 字；待核实 {unknown} 句不会重复发送。'
    if pending:
        frozen = freeze_settings(lines, settings)
        tip += '\n' + RequestLedger(project).preview_text(frozen['model'], 'requests', {'characters': chars})
    return {'pending': pending, 'unknown': unknown, 'characters': chars, 'text': tip}


# 「连接根本没建立」的可证明文案：refused／DNS 解析失败一类——可记 failed 自动重发。
_PROVEN_UNREACHABLE_MARKERS = ('refused', '10061', 'econnrefused', 'getaddrinfo',
                             'name resolution', 'name or service', '11001', '11004')


def _send_outcome(exc):
    """网络层发送结果判定：'uncertain' 结果未知（可能已提交扣费，禁止自动重发）、
    'failed' 可证明连接没建立（refused／DNS 失败一类）、None 交给既有分支。

    必须在「已付费写盘失败」分支之前判定：ConnectionResetError 等网络层 OSError 也是
    OSError，落到写盘分支会误标 unsaved。URLError 按底层 reason 再分：refused／gaierror
    及对应文案才算确定失败，超时、重置、读取中断和识别不出的文案一律按未知处理。
    """
    import http.client
    import socket
    import urllib.error
    reason = getattr(exc, 'reason', exc)
    if isinstance(reason, (TTSAcceptanceUnknown, ConnectionResetError, ConnectionAbortedError, BrokenPipeError,
                           TimeoutError, http.client.IncompleteRead)):
        return 'uncertain'
    if isinstance(reason, (ConnectionRefusedError, socket.gaierror)):
        return 'failed'
    if isinstance(exc, urllib.error.URLError):
        if isinstance(reason, OSError):
            return 'uncertain'
        text = str(reason or exc).lower()
        return 'failed' if any(m in text for m in _PROVEN_UNREACHABLE_MARKERS) else 'uncertain'
    return None


def _line_outcome(exc, started, paid, project):
    """逐句异常归类，返回 (state, error, not_submitted)；判定顺序即扣费安全边界。

    结果未知最先判：连接重置／超时／响应读取中断可能已提交扣费，记 uncertain 禁止自动
    重发；其次已付费写盘失败记 unsaved；4xx 与可证明未建立的 refused 一类记 failed 允许
    自动重发；其余已启动的记 uncertain、未启动的记 failed。
    """
    import urllib.error
    outcome = _send_outcome(exc)
    if outcome == 'uncertain':
        return 'uncertain', str(exc), False
    if project is not None and paid and isinstance(exc, (OSError, ValueError)) and not isinstance(exc, TTSRejected):
        return 'unsaved', '已付费未保存：' + str(exc), False
    if outcome == 'failed' or isinstance(exc, TTSRejected) or (isinstance(exc, urllib.error.URLError) and started):
        return 'failed', str(exc), True
    if project is not None and started:
        return 'uncertain', str(exc), False
    return 'failed', str(exc), True


def run_lines(lines, folder, generate=None, report=None, stop=None, *, gateway=None, settings=None, episode=None,
              on_line=None, project=None):
    """逐句合成到 folder：每句完成后立即写清单，已成功的句子直接沿用。

    中断或报错后再次运行会接续同一批次，只补做缺的句子，不重复扣费。
    返回 (成功数, 沿用数, 失败数)。on_line(序号, 句子, 登记项) 在每句真正合成并发布后调用（沿用的句子不调用）。
    """
    from contextlib import nullcontext
    from uuid import uuid4
    from infra.pet_llm import RequestLedger, BudgetRejected
    publish = _require_gateway(gateway, "publish_json", "publish_bytes")
    folder = Path(folder)
    # 批次一开始就把配置冻结下来：长批次中途改设置，这一批仍按开批时那一套跑，不混用两套（O12）。
    frozen = freeze_settings(lines, settings)
    if project is not None:
        quote = batch_cost_preview(project, lines, folder, frozen)
        if report:report(quote['text'])
    folder.mkdir(parents=True, exist_ok=True)
    if generate is None:
        if project is not None and not load_key():
            raise ValueError("请先在配音设置保存 API Key")
        generate = lambda text, speed=1.0, voice=None: synthesize(
            text, speed=speed, voice=voice, settings=frozen)
    prior = read_json(folder / "时间轴.json")
    _require_object_entries(prior, folder)
    prior = _safe_manifest_rows(prior) if isinstance(prior, list) else []
    _save(folder / "批次.json", {"signature": batch_signature(lines, episode), "lines": len(lines),
                                 "identity": batch_identity(lines), "episode": str(episode or "")}, gateway=publish)
    # 逐句沿用按身份配对（不含位置与起止时间），整批先按新句序号落盘：
    # 中断后再跑，这份清单仍记得哪些旧成品沿用、哪些条目结果待核实。
    done, blocked = _line_verdicts(lines, prior, folder)
    manifest = [({**done[index], **line} if index in done
                 else {**prior[blocked[index] - 1], **line} if index in blocked
                 else {**line, 'state': 'failed', 'file': ''})
                for index, line in enumerate(lines, 1)]
    _save(folder / "时间轴.json", manifest, gateway=publish)
    ok = reused = failed = 0
    for index, line in enumerate(lines, 1):
        if stop is not None and stop.is_set():
            if report:
                report("已停止；再次点击会接续本批次，已生成的句子不会重复合成。")
            break
        if index in done:
            ok += 1; reused += 1
            if report:
                report(f'{index}/{len(lines)} · {line.get("shot_id")}：沿用已生成的配音')
            continue
        if index in blocked:
            failed += 1
            if report:
                report(f'{index}/{len(lines)}：上次配音结果未知，请核对请求 {manifest[index - 1].get("request_id", "")}，未重复发送')
            continue
        name = line_name(index, line)
        request_id = 'tts:' + uuid4().hex
        started = False
        paid = False
        try:
            text = line.get('text', '')
            if project is not None:
                if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                    raise BudgetRejected('配音文本须为1至4000字')
                coerce_speed(line.get('speed', 1.0))
            meter = (RequestLedger(project).metered_units(request_id, frozen['model'], 'audio', 'requests', 1,
                      quantities={'characters': len(text)}) if project is not None else nullcontext())
            with meter:
                if project is not None:
                    pending = {**line, 'state': 'sending', 'file': '', 'request_id': request_id}
                    if index <= len(manifest):manifest[index - 1] = pending
                    else:manifest.append(pending)
                    _save(folder / '时间轴.json', manifest, gateway=publish)
                started = True
                raw = generate(text, speed=line.get("speed", 1.0), voice=line.get("voice") or None)
                if not raw:raise ValueError('TTS 未返回音频')
                paid = True
            entry = publish_line(folder, manifest, index, {**line, **({'request_id': request_id} if project is not None else {})}, raw, gateway=publish)
            ok += 1
            if on_line is not None:
                on_line(index, line, entry)
        except Exception as exc:
            state, error, not_submitted = _line_outcome(exc, started, paid, project)
            entry = {**line, "file": "", "state": state, "error": _line_error_text(state, error)}
            if project is not None:
                entry.update(request_id=request_id, not_submitted=not_submitted)
            failed += 1
            if index <= len(manifest):
                manifest[index - 1] = entry
            else:
                manifest.append(entry)
            _save(folder / "时间轴.json", manifest, gateway=publish)
        if report:
            report(f'{index}/{len(lines)} · {line.get("shot_id")}：' + ("已生成 " + name if entry["state"] == "ok" else "失败：" + str(entry.get("error", ""))))
    _save(folder / "时间轴.json", manifest, gateway=publish)
    return ok, reused, failed


def synthesize(text, speed=1.0, voice=None, *, settings=None, project=None, request_id=None):
    """合成一段语音；出站请求统一走 ``infra.http_client.request_bytes``（规则 42）。

    返回原始音频 bytes；错误分类与直连时代一致：HTTP 状态 → ``ValueError``
    （文案不变）、空响应 → ``ValueError("TTS 未返回音频")``、超时 →
    ``TimeoutError``、其余网络失败 → ``urllib.error.URLError``。
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError('请填写要合成的文本')
    speed = coerce_speed(speed)
    if len(text) > 4000:
        raise ValueError('单次合成文本过长（超过4000字），请改用“逐句配音”分句生成')
    settings = settings if isinstance(settings, dict) else read_settings()
    key = load_key()
    if not key:
        raise ValueError("请先在“配音设置”保存 API Key")
    body = payload(text, settings["model"], voice or settings["voice"], speed)
    from contextlib import nullcontext
    from uuid import uuid4
    from infra.pet_llm import RequestLedger
    import infra.http_client as http_client
    meter = (RequestLedger(project).metered_units(request_id or 'tts:' + uuid4().hex,
             settings['model'], 'audio', 'requests', 1, quantities={'characters': len(text)})
             if project is not None else nullcontext())
    with meter:
        result = http_client.request_bytes(
            'POST', settings["base_url"].rstrip("/") + "/audio/speech",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            payload=body, timeout=120, max_bytes=TTS_AUDIO_MAX_BYTES)
        data = result.data if isinstance(result.data, dict) else {}
        if result.ok:
            raw = data.get('body')
            if not raw:
                raise ValueError("TTS 未返回音频")
            return raw
        status = data.get('status')
        if status:
            message = f"TTS 请求失败（HTTP {int(status)}）"
            if data.get("acceptance") == "unknown":
                raise TTSAcceptanceUnknown(message) from None
            if 400 <= int(status) <= 499:
                raise TTSRejected(message) from None
            raise ValueError(message) from None
        if code_of(result) == 'E-NET-TIMEOUT':
            raise TimeoutError('配音请求超时，请核对受理情况') from None
        import urllib.error
        # 在本地分类传输错误；异常会随时间轴持久化，不能带服务商原文或签名地址。
        reason = urllib.error.URLError(str(data.get('error_body') or ''))
        if _send_outcome(reason) == 'failed':
            raise urllib.error.URLError(ConnectionRefusedError('未能连接配音服务')) from None
        raise urllib.error.URLError('配音连接中断，请核对受理情况') from None


def unknown_line_indexes(lines, folder):
    """身份一致且状态为 sending／uncertain／unsaved 的旧条目在时间轴清单里的序号（从 1 起）。"""
    folder = Path(folder)
    manifest = read_json(folder / '时间轴.json')
    _done, blocked = _line_verdicts(lines, manifest, folder)
    return list(blocked.values())


def unknown_release_prompt(lines, folder):
    """人工放开确认文案：镜号、台词前 20 字、请求号，按句子状态分组。

    sending／uncertain 一组沿用「已核对没有扣费」句；unsaved（已付费未保存）单独成组，
    如实说明重发会再付一次；混合批次两段各自列出。indexes 为空表示没有待核实句。
    """
    folder = Path(folder)
    manifest = read_json(folder / '时间轴.json')
    manifest = manifest if isinstance(manifest, list) else []
    indexes = unknown_line_indexes(lines, folder)
    groups = {'unknown': [], 'unsaved': []}
    for index in indexes:
        previous = manifest[index - 1] if index <= len(manifest) else {}
        line = lines[index - 1] if index <= len(lines) and isinstance(lines[index - 1], dict) else {}
        text = str((previous or {}).get('text') or line.get('text') or '')
        row = '%s · %s · 请求 %s' % (
            (previous or {}).get('shot_id') or line.get('shot_id') or '',
            text[:20],
            (previous or {}).get('request_id') or '（无）')
        groups['unsaved' if (previous or {}).get('state') == 'unsaved' else 'unknown'].append(row)
    sections = []
    if groups['unknown']:
        sections.append('下列句子上次结果未知，不会自动重发：\n' + '\n'.join(groups['unknown'])
                        + '\n\n已核对服务商后台，这些请求没有扣费，重新发送')
    if groups['unsaved']:
        sections.append('下列句子上次已付费但没有保存成功，不会自动重发：\n' + '\n'.join(groups['unsaved'])
                        + '\n\n这些句子上次已付费但没有保存成功，重新发送会再付一次')
    return {'indexes': indexes, 'text': '\n\n'.join(sections)}


def release_unknown(folder, indexes, *, gateway=None):
    """把指定序号的 sending／uncertain／unsaved 改成 failed，并记下放开时间。"""
    from datetime import datetime, timezone
    folder = Path(folder)
    publish = _require_gateway(gateway, 'publish_json')
    manifest = read_json(folder / '时间轴.json')
    if not isinstance(manifest, list):
        raise ValueError('时间轴清单不可读')
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    released = []
    for index in indexes:
        if not isinstance(index, int) or index < 1 or index > len(manifest):
            continue
        entry = manifest[index - 1]
        if not _line_needs_review(entry):
            continue
        manifest[index - 1] = {**entry, 'state': 'failed', 'released_at': stamp, 'not_submitted': True}
        released.append(index)
    if released:
        _save(folder / '时间轴.json', _safe_manifest_rows(manifest), gateway=publish)
    return released
