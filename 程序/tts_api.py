"""OpenAI 兼容文本转语音（TTS）：支持 tts-1 及任何 OpenAI 兼容 /audio/speech 端点。"""
import base64
import hashlib
import json
import math
import os
import re
from pathlib import Path
from agent.core import read_json
from project_context import ProjectContext
from urllib.parse import urlparse
# 第 34 期第 9 条：`urllib.request`／`urllib.error` 连 ssl 一起加载（约 4.4 MB 常驻），
# 本模块只在真要请求语音接口时用得到——都改成函数内 import。

from seedream_api import protect

DEFAULT_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "tts-1"
KEY_ENV = "TTS_API_KEY"                     # 第 65 期任务 1：统一那份 .env 里的变量名


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
    import model_pool
    model_pool.save_named_key(KEY_ENV, secret)
    write_settings(data, gateway=gateway)


def unified_key():
    """统一那份 .env（程序目录/private/.env）里的密钥；没有就是空串（第 65 期任务 1）。"""
    try:
        import model_pool
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
    """把对白时间轴整理为整段配音文本（逐句带说话人）。"""
    return "\n".join(f'{line["name"]}：{line["text"]}' for line in build_lines(entries, assets))


def script_signature(text, settings=None):
    """整段配音的内容指纹：台词、模型、音色或服务商端点变了才需重新付费合成。"""
    settings = settings if isinstance(settings, dict) else read_settings()
    payload_ = {"text": text, "model": settings.get("model"), "voice": settings.get("voice"),
                "endpoint": str(settings.get("base_url") or "").strip().rstrip("/")}
    return hashlib.sha256(json.dumps(payload_, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def reusable_full_track(context, signature):
    """Return the completed whole-track audio for an unchanged paid request, if any."""
    from project_stages import audio
    marker = audio(_context(context).root) / '整段配音.json'
    previous = read_json(marker) if marker.is_file() else {}
    path = Path(previous.get('file', '')) if isinstance(previous, dict) else Path()
    if (isinstance(previous, dict) and previous.get('signature') == signature
            and previous.get('file') and path.is_file() and path.stat().st_size > 0):
        return path
    return None


def publish_full_track(context, signature, raw, *, gateway=None):
    """Publish complete audio before its idempotence marker, preserving media on marker failure."""
    from project_stages import audio
    folder = audio(_context(context).root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('配音_' + os.urandom(3).hex() + '.mp3')
    publish = _require_gateway(gateway, "publish_json", "publish_bytes")
    publish["publish_bytes"](path, raw)
    publish["publish_json"](folder / '整段配音.json', {'signature': signature, 'file': str(path)})
    return path


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
    """同内容（且同一集）的旧逐句配音目录：可续跑，已成功的句子不重复合成（避免重复扣费）。"""
    base = Path(root)
    if not base.is_dir():
        return None
    signature = batch_signature(lines, episode)
    for record in sorted(base.glob("*/批次.json"), reverse=True):
        data = read_json(record)
        if isinstance(data, dict) and data.get("signature") == signature:
            return record.parent
    return None


def line_name(index, line):
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(line.get("name") or "")).strip(" .")[:20]
    return f'{index:03}_{line.get("shot_id")}_{safe}_{float(line.get("start") or 0):.1f}s.mp3'


def line_done(manifest, index, line, folder):
    """这一句是否已有可用成品：续跑与付费预览共用同一口径，避免两处判断走偏。

    O12：身份要对得上（含端点与模型），并且要复核写入时记下的 sha256——只判「文件在不在」
    会把截断或损坏的成品当成已生成；旧清单没记摘要时退回「文件非空」。
    """
    previous = manifest[index - 1] if index <= len(manifest) and isinstance(manifest[index - 1], dict) else {}
    same = all(previous.get(key) == line.get(key) for key in LINE_IDENTITY_FIELDS)
    if not (same and previous.get("state") == "ok" and previous.get("file")):
        return False
    path = Path(folder) / str(previous["file"])
    if not path.is_file():
        return False
    digest = str(previous.get("sha256") or "")
    if not digest:
        try:
            return path.stat().st_size > 0
        except OSError:
            return False
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == digest
    except OSError:
        return False


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
    if not isinstance(manifest, list):
        manifest = []
    return [index for index, line in enumerate(lines, 1) if not line_done(manifest, index, line, folder)]


def run_lines(lines, folder, generate=None, report=None, stop=None, *, gateway=None, settings=None, episode=None,
              on_line=None):
    """逐句合成到 folder：每句完成后立即写清单，已成功的句子直接沿用。

    中断或报错后再次运行会接续同一批次，只补做缺的句子，不重复扣费。
    返回 (成功数, 沿用数, 失败数)。on_line(序号, 句子, 登记项) 在每句真正合成并发布后调用（沿用的句子不调用）。
    """
    publish = _require_gateway(gateway, "publish_json", "publish_bytes")
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    # 批次一开始就把配置冻结下来：长批次中途改设置，这一批仍按开批时那一套跑，不混用两套（O12）。
    frozen = freeze_settings(lines, settings)
    if generate is None:
        generate = lambda text, speed=1.0, voice=None: synthesize(
            text, speed=speed, voice=voice, settings=frozen)
    manifest = read_json(folder / "时间轴.json")
    if not isinstance(manifest, list):
        manifest = []
    _save(folder / "批次.json", {"signature": batch_signature(lines, episode), "lines": len(lines),
                                 "identity": batch_identity(lines), "episode": str(episode or "")}, gateway=publish)
    ok = reused = failed = 0
    for index, line in enumerate(lines, 1):
        if stop is not None and stop.is_set():
            if report:
                report("已停止；再次点击会接续本批次，已生成的句子不会重复合成。")
            break
        if line_done(manifest, index, line, folder):
            ok += 1; reused += 1
            if report:
                report(f'{index}/{len(lines)} · {line.get("shot_id")}：沿用已生成的配音')
            continue
        name = line_name(index, line)
        try:
            raw = generate(line.get("text", ""), speed=line.get("speed", 1.0), voice=line.get("voice") or None)
            entry = publish_line(folder, manifest, index, line, raw, gateway=publish)
            ok += 1
            if on_line is not None:
                on_line(index, line, entry)
        except Exception as exc:
            entry = {**line, "file": "", "state": "failed", "error": str(exc)}
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


def no_redirect():
    """第 34 期第 9 条：惰性建类——只有真要发 HTTP 时才 import urllib.request；照旧返回实例。"""
    from urllib.request import HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    return NoRedirect()


def synthesize(text, speed=1.0, voice=None, *, settings=None):
    from urllib.request import Request, build_opener        # 第 34 期第 9 条：HTTP 栈按需加载
    from urllib.error import HTTPError
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
    request = Request(
        settings["base_url"].rstrip("/") + "/audio/speech",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with build_opener(no_redirect()).open(request, timeout=120) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        raise ValueError(f"TTS 请求失败（HTTP {exc.code}）：{detail}") from None
    if not raw:
        raise ValueError("TTS 未返回音频")
    return raw
