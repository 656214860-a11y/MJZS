"""OpenAI 兼容文本转语音（TTS）：支持 tts-1 及任何 OpenAI 兼容 /audio/speech 端点。"""
import base64
import hashlib
import json
import math
import os
import re
from pathlib import Path
from agent.core import read_json
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
    defaults = {"base_url": DEFAULT_URL, "model": DEFAULT_MODEL, "voice": "alloy", "encrypted_key": "", "voices": {}, "speeds": {}}
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


def build_lines(entries, assets=None, voices=None, speeds=None):
    """把 timed_entries 的 (shot_id, speaker, text, start, end) 整理为逐句配音清单。"""
    assets = assets if isinstance(assets, dict) else {}
    voices = voices if isinstance(voices, dict) else {}
    speeds = speeds if isinstance(speeds, dict) else {}
    lines = []
    for sid, speaker, text, start, end in entries:
        item = assets.get(speaker) if isinstance(assets.get(speaker), dict) else {}
        name = str(item.get("name") or speaker or "未注明角色")
        voice = voices.get(speaker) or voices.get(name) or ""
        speed = coerce_speed(speeds.get(speaker) or speeds.get(name))
        lines.append({"shot_id": sid, "speaker": speaker, "name": name, "text": text,
                      "start": start, "end": end, "voice": voice, "speed": speed})
    return lines


def build_script(entries, assets=None):
    """把对白时间轴整理为整段配音文本（逐句带说话人）。"""
    return "\n".join(f'{line["name"]}：{line["text"]}' for line in build_lines(entries, assets))


def script_signature(text, settings=None):
    """整段配音的内容指纹：台词、模型或音色变了才需要重新付费合成。"""
    settings = settings if isinstance(settings, dict) else read_settings()
    payload_ = {"text": text, "model": settings.get("model"), "voice": settings.get("voice")}
    return hashlib.sha256(json.dumps(payload_, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def reusable_full_track(project, signature):
    """Return the completed whole-track audio for an unchanged paid request, if any."""
    from project_stages import audio
    marker = audio(project) / '整段配音.json'
    previous = read_json(marker) if marker.is_file() else {}
    path = Path(previous.get('file', '')) if isinstance(previous, dict) else Path()
    if (isinstance(previous, dict) and previous.get('signature') == signature
            and previous.get('file') and path.is_file()):
        return path
    return None


def publish_full_track(project, signature, raw, *, gateway=None):
    """Publish complete audio before its idempotence marker, preserving media on marker failure."""
    from project_stages import audio
    folder = audio(project)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('配音_' + os.urandom(3).hex() + '.mp3')
    publish = _require_gateway(gateway, "publish_json", "publish_bytes")
    publish["publish_bytes"](path, raw)
    publish["publish_json"](folder / '整段配音.json', {'signature': signature, 'file': str(path)})
    return path


def batch_signature(lines):
    """逐句配音批次的内容指纹：文本、配音、语速或时间轴变化就算新批次。"""
    return hashlib.sha256(json.dumps(lines, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _save(path, data, *, gateway=None):
    _require_gateway(gateway, "publish_json")["publish_json"](path, data)


def resume_folder(root, lines):
    """同内容的旧逐句配音目录：可续跑，已成功的句子不重复合成（避免重复扣费）。"""
    base = Path(root)
    if not base.is_dir():
        return None
    signature = batch_signature(lines)
    for record in sorted(base.glob("*/批次.json"), reverse=True):
        data = read_json(record)
        if isinstance(data, dict) and data.get("signature") == signature:
            return record.parent
    return None


def line_name(index, line):
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(line.get("name") or "")).strip(" .")[:20]
    return f'{index:03}_{line.get("shot_id")}_{safe}_{float(line.get("start") or 0):.1f}s.mp3'


def line_done(manifest, index, line, folder):
    """这一句是否已有可用成品：续跑与付费预览共用同一口径，避免两处判断走偏。"""
    previous = manifest[index - 1] if index <= len(manifest) and isinstance(manifest[index - 1], dict) else {}
    same = all(previous.get(key) == line.get(key) for key in ("shot_id", "text", "voice", "speed"))
    return bool(same and previous.get("state") == "ok" and previous.get("file") and (Path(folder) / previous["file"]).is_file())


def publish_line(folder, manifest, index, line, raw, *, gateway=None):
    """原子发布单句音频后，再把它登记进可续跑时间轴。"""
    folder = Path(folder)
    name = line_name(index, line)
    publish = _require_gateway(gateway, "publish_json", "publish_bytes")
    publish["publish_bytes"](folder / name, raw)
    entry = {**line, "file": name, "state": "ok"}
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


def run_lines(lines, folder, generate=None, report=None, stop=None, *, gateway=None):
    """逐句合成到 folder：每句完成后立即写清单，已成功的句子直接沿用。

    中断或报错后再次运行会接续同一批次，只补做缺的句子，不重复扣费。
    返回 (成功数, 沿用数, 失败数)。
    """
    publish = _require_gateway(gateway, "publish_json", "publish_bytes")
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    generate = generate or synthesize
    manifest = read_json(folder / "时间轴.json")
    if not isinstance(manifest, list):
        manifest = []
    _save(folder / "批次.json", {"signature": batch_signature(lines), "lines": len(lines)}, gateway=publish)
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


def synthesize(text, speed=1.0, voice=None):
    from urllib.request import Request, build_opener        # 第 34 期第 9 条：HTTP 栈按需加载
    from urllib.error import HTTPError
    if not isinstance(text, str) or not text.strip():
        raise ValueError('请填写要合成的文本')
    speed = coerce_speed(speed)
    if len(text) > 4000:
        raise ValueError('单次合成文本过长（超过4000字），请改用“逐句配音”分句生成')
    settings = read_settings()
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
