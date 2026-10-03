"""TTS 配音设置窗口：OpenAI 兼容 /audio/speech 端点。"""
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

import tts_api as api
import tk_timers
from ui_tokens import SPACING
from ui_widgets import (DescriptionBlock, FormDialog, LineInput, PrimaryButton,
                        ProgressLabel, SecondaryButton, notify)


def show(parent, on_saved=None):
    win = FormDialog(parent, "配音设置 · OpenAI 兼容 TTS", modal=False, chrome=False)
    win.withdraw()
    win.title("配音设置 · OpenAI 兼容 TTS")
    win.transient(parent)
    win.geometry("760x500")
    win.minsize(620, 460)

    settings = api.read_settings()
    import json as _json
    values = {
        "base_url": tk.StringVar(value=settings.get("base_url", api.DEFAULT_URL)),
        "model": tk.StringVar(value=settings.get("model", api.DEFAULT_MODEL)),
        "voice": tk.StringVar(value=settings.get("voice", "alloy")),
        "api_key": tk.StringVar(value=api.load_key()),
        "voices": tk.StringVar(value=_json.dumps(settings.get("voices", {}) or {}, ensure_ascii=False)),
        "speeds": tk.StringVar(value=_json.dumps(settings.get("speeds", {}) or {}, ensure_ascii=False)),
    }
    body = ttk.Frame(win, padding=SPACING['lg'])
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)
    DescriptionBlock(body, text="支持 OpenAI /audio/speech 或任意 OpenAI 兼容 TTS 端点；密钥统一保存到 程序目录/private/.env。", wraplength=700).grid(row=0, column=0, columnspan=3, sticky="w", pady=(SPACING['none'], SPACING['md']))
    for row, key, label in [(1, "base_url", "API 根地址"), (2, "model", "TTS 模型"), (3, "voice", "默认音色"), (4, "api_key", "API Key")]:
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(SPACING['none'], SPACING['md']))
        LineInput(body, textvariable=values[key], show="•" if key == "api_key" else "").grid(row=row, column=1, columnspan=2, sticky="ew", pady=SPACING['sm'])
    ttk.Label(body, text="角色音色映射（可选，JSON：{\"CHAR_001\": \"voice_a\"}，留空用默认音色）").grid(row=5, column=0, sticky="w", padx=(SPACING['none'], SPACING['md']))
    LineInput(body, textvariable=values["voices"]).grid(row=5, column=1, columnspan=2, sticky="ew", pady=SPACING['sm'])
    ttk.Label(body, text="角色语速映射（可选，JSON：{\"CHAR_001\": 1.2}，范围 0.25–4.0，留空默认 1.0）").grid(row=6, column=0, sticky="w", padx=(SPACING['none'], SPACING['md']))
    LineInput(body, textvariable=values["speeds"]).grid(row=6, column=1, columnspan=2, sticky="ew", pady=SPACING['sm'])
    status = tk.StringVar(value="保存配置不会发起付费合成；实际合成时按用量计费。")
    ProgressLabel(body, textvariable=status, wraplength=700).grid(row=7, column=0, columnspan=3, sticky="w", pady=SPACING['sm'])

    def check():
        try:
            api.validate(values["base_url"].get(), values["model"].get(), values["voice"].get(), values["api_key"].get())
            status.set("填写格式正确；实际模型与音色权限将在正式合成时验证。")
        except ValueError as exc:
            status.set(str(exc))

    def probe():
        from api_endpoints import normalize_url, probe_endpoint
        try:
            url = normalize_url(values["base_url"].get())
        except ValueError as exc:
            status.set(str(exc)); return
        status.set("正在测试连接…")
        def work():
            result = probe_endpoint(url)
            if result.get("reachable") and result.get("code") in (401, 403, 404):
                return "接口可达（HTTP %s，需密钥）" % result["code"]
            if result.get("reachable"):
                return "接口可达（HTTP %s）" % result["code"]
            return "连接失败：" + str(result.get("error", "未知错误"))
        import threading
        outcome = []
        def run():
            # 工作线程只写普通列表：跨线程设置 Tk 变量会抛 RuntimeError，状态栏会一直停在「正在检测」。
            try: outcome.append(work())
            except Exception as exc: outcome.append("连接失败：" + type(exc).__name__)
        def poll():
            if not win.winfo_exists(): return
            if not outcome: return
            status.set(outcome[0]);stop()
        threading.Thread(target=run, daemon=True).start()
        stop=tk_timers.repeat(win, 150, poll);poll()

    def commit():
        try:
            import json as _json
            voices_text = values["voices"].get().strip()
            voices = _json.loads(voices_text) if voices_text else {}
            if not isinstance(voices, dict):
                raise ValueError("角色音色映射必须为 JSON 对象")
            speeds_text = values["speeds"].get().strip()
            speeds = _json.loads(speeds_text) if speeds_text else {}
            if not isinstance(speeds, dict):
                raise ValueError("角色语速映射必须为 JSON 对象")
            from stage_execution_service import save_tts_key
            save_tts_key(values["base_url"].get(), values["model"].get(), values["voice"].get(), values["api_key"].get(), voices, speeds)
            if on_saved:
                on_saved()
            win.destroy()
        except (ValueError, OSError, _json.JSONDecodeError) as exc:
            notify(win, str(exc), level='error', title="保存失败", status=status)

    row = ttk.Frame(body)
    row.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(SPACING['md'], SPACING['none']))
    PrimaryButton(row, text="保存", command=commit).pack(side="left")
    SecondaryButton(row, text="检查配置", command=check).pack(side="left", padx=SPACING['sm'])
    SecondaryButton(row, text="测试连接", command=probe).pack(side="left", padx=SPACING['sm'])
    SecondaryButton(row, text="打开 OpenAI 控制台", command=lambda: webbrowser.open("https://platform.openai.com/")).pack(side="left", padx=SPACING['sm'])
    SecondaryButton(row, text="取消", command=win.destroy).pack(side="right")

    win.update_idletasks()
    x = max(0, parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2)
    y = max(0, parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2)
    win.geometry(f"+{x}+{y}")
    win.deiconify()
