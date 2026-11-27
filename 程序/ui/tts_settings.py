"""TTS 配音设置窗口：OpenAI 兼容 /audio/speech 端点。"""
import tkinter as tk
import webbrowser
from tkinter import ttk

import domain.tts_api as api
import infra.tk_timers as tk_timers
from ui_tokens import WRAPLENGTH, SPACING
from account_inputs import PasswordInput
from ui_widgets import (BaseDialog, Card, DescriptionBlock, FormDialog, LineInput, PrimaryButton,
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
    body = Card(win)
    body.pack(fill="both", expand=True, padx=SPACING['lg'], pady=SPACING['lg'])
    body.columnconfigure(1, weight=1)
    DescriptionBlock(body, text="支持 OpenAI /audio/speech 或任意 OpenAI 兼容 TTS 端点；密钥统一保存到 程序目录/private/.env。", wraplength=WRAPLENGTH['lg']).grid(row=0, column=0, columnspan=3, sticky="w", pady=(SPACING['none'], SPACING['md']))
    for row, key, label in [(1, "base_url", "API 根地址"), (2, "model", "TTS 模型"), (3, "voice", "默认音色"), (4, "api_key", "API Key")]:
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(SPACING['none'], SPACING['md']))
        (PasswordInput if key == "api_key" else LineInput)(body, textvariable=values[key]).grid(row=row, column=1, columnspan=2, sticky="ew", pady=SPACING['sm'])
    ttk.Label(body, text="角色音色映射（可选，JSON：{\"CHAR_001\": \"voice_a\"}，留空用默认音色）").grid(row=5, column=0, sticky="w", padx=(SPACING['none'], SPACING['md']))
    LineInput(body, textvariable=values["voices"]).grid(row=5, column=1, columnspan=2, sticky="ew", pady=SPACING['sm'])
    ttk.Label(body, text="角色语速映射（可选，JSON：{\"CHAR_001\": 1.2}，范围 0.25–4.0，留空默认 1.0）").grid(row=6, column=0, sticky="w", padx=(SPACING['none'], SPACING['md']))
    LineInput(body, textvariable=values["speeds"]).grid(row=6, column=1, columnspan=2, sticky="ew", pady=SPACING['sm'])
    status = tk.StringVar(value="保存配置不会发起付费合成；实际合成时按用量计费。")
    ProgressLabel(body, textvariable=status, wraplength=WRAPLENGTH['lg']).grid(row=7, column=0, columnspan=3, sticky="w", pady=SPACING['sm'])

    def check():
        try:
            api.validate(values["base_url"].get(), values["model"].get(), values["voice"].get(), values["api_key"].get())
            status.set("填写格式正确；实际模型与音色权限将在正式合成时验证。")
        except ValueError as exc:
            status.set(str(exc))

    def probe():
        from infra.api_endpoints import normalize_url, probe_message
        try:
            url = normalize_url(values["base_url"].get())
        except ValueError as exc:
            status.set(str(exc)); return
        status.set("正在测试连接…")
        tk_timers.run_in_background(win, lambda: probe_message(url), status.set,
                                    lambda exc: status.set("连接失败：" + type(exc).__name__))

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
            import contract.error_codes as error_codes
            notify(win, error_codes.user_text(exc), level='error', title="保存失败", status=status)

    row = ttk.Frame(body);row.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(SPACING['md'], SPACING['none']))
    SecondaryButton(row, text="检查配置", command=check).pack(side="left")
    SecondaryButton(row, text="测试连接", command=probe).pack(side="left", padx=(SPACING['sm'], SPACING['none']))
    SecondaryButton(row, text="打开 OpenAI 控制台", command=lambda: webbrowser.open("https://platform.openai.com/")).pack(side="left", padx=(SPACING['sm'], SPACING['none']))
    PrimaryButton(row, text="保存", command=commit).pack(side="right")
    SecondaryButton(row, text="取消", command=win.destroy).pack(side="right", padx=(SPACING['none'], SPACING['sm']))

    win.update_idletasks()
    x = max(0, parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2)
    y = max(0, parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2)
    win.geometry(f"+{x}+{y}")
    win.deiconify()


_AUDIO_KIND_CHOICES = tuple((kind, api.AUDIO_KIND_LABELS[kind]) for kind in api.AUDIO_KINDS)


class AudioKindDialog(BaseDialog):
    """导入音频的用途询问：默认对白；取消、Esc 与关闭都保持 ``choice`` 为 None。"""

    def __init__(self, parent):
        self.choice = None
        super().__init__(parent, "导入音频 · 选择用途")
        DescriptionBlock(self.content, text="这段音频在成片里是什么用途？非对白音轨会加前缀标记，不计入对白成果。").pack(fill="x", pady=(SPACING["none"], SPACING["md"]))
        self._selected = tk.StringVar(value="dialogue")
        for kind, label in _AUDIO_KIND_CHOICES:
            ttk.Radiobutton(self.content, text=label, variable=self._selected, value=kind).pack(anchor="w", pady=SPACING["xs"])
        self.add_action("取消", self.close)
        self.add_action("导入", self._confirm, primary=True)

    def _confirm(self):
        self.choice = self._selected.get()
        self.close()


def ask_audio_kind(parent):
    """同步询问音轨用途；确定返回 kind，取消、Esc、关闭或父窗已销毁返回 None。"""
    dialog = AudioKindDialog(parent)
    try:
        dialog.wait_window()
    except tk.TclError:
        return None
    return dialog.choice


def import_audio_with_kind(app, source):
    """「导入配音 / 音乐」胶水：先问清用途再经 L3 编排导入；取消询问不导入。"""
    kind = ask_audio_kind(app.win)
    if kind is None:
        return
    from stage_execution_service import import_stage_audio
    project = app.root
    def work():
        result = import_stage_audio(project, source, kind=kind)
        if not result.ok:
            raise ValueError(result.reason)
        return result.data
    app.async_(work, lambda dest: app.status.set('音频已导入：' + str(dest)))
