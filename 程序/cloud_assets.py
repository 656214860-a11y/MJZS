"""ComfyUI partner image models for the assistant's sequential asset batches."""
import os
import re
from pathlib import Path
from seedream_api import protect
import production_model_contract

KEY_LABEL = '本机 Comfy API Key'                      # 只用于出错提示；DPAPI 实现在 seedream_api.protect
KEY_ENV = 'COMFY_API_KEY'                             # 第 65 期任务 1：统一那份 .env 里的变量名
LOCAL = production_model_contract.ASSET_LOCAL_MODEL    # 第 1647 轮：后端名下沉 L0，这里按原名字保留
MODELS = list(production_model_contract.ASSET_CLOUD_MODELS)
NODE_TYPES = dict(zip(production_model_contract.ASSET_CLOUD_MODELS, ('ByteDanceSeedreamNode', 'GeminiImage2Node', 'OpenAIGPTImage1')))
LIMITS = dict(zip(production_model_contract.ASSET_CLOUD_MODELS, (10, 14, 16)))


def _secret_file():
    return Path(os.environ['LOCALAPPDATA']) / '漫剧制作助手' / 'comfy_cloud_key.dpapi'


def _unified_key():
    """统一那份 .env（程序目录/private/.env）里的密钥；没有就是空串（第 65 期任务 1）。"""
    try:
        import model_pool
        return model_pool.named_key(KEY_ENV)
    except Exception:
        return ''


def get_key():
    """密钥的次序：同名环境变量 → 统一那份 .env → 老安装留在本机加密那份（只读兼容）。"""
    if os.environ.get(KEY_ENV, '').strip():
        return os.environ[KEY_ENV].strip()
    unified = _unified_key()
    if unified:
        return unified
    file = _secret_file()
    return protect(file.read_bytes(), decrypt=True, label=KEY_LABEL).decode('utf-8') if file.is_file() else ''


def save_key(value):
    """第 65 期任务 1：写进统一那份 .env，本机不再另存一份明文之外的文件。"""
    value = value.strip()
    if not value or any(c.isspace() for c in value):
        raise ValueError('请填写 Comfy 账户的 API Key')
    import model_pool
    model_pool.save_named_key(KEY_ENV, value)


def validate(client, options, assets):
    model = options.get('backend', LOCAL)
    if model not in MODELS:
        raise ValueError('请选择支持的云图片模型')
    if not get_key():
        raise ValueError('请先点击“云模型设置”，保存 Comfy 账户的 API Key；阿里云或火山密钥不能填在这里')
    info = client.request('/object_info')
    for name in ('DramaCloudImage', 'DramaOptionalReferenceImage', NODE_TYPES[model]):
        if name not in info:
            raise ValueError('本地 ComfyUI 尚未加载新节点，请重启 ComfyUI：' + name)
    for aid, asset in assets:
        if len(asset.get('reference_images', [])) > LIMITS[model]:
            raise ValueError(f'{aid} 的参考图超过 {model} 支持的 {LIMITS[model]} 张')


def graph(client, aid, asset, prompt, images, options):
    from batch_frames_tool.batch_frames import Client
    model = options['backend']
    if len(images) > LIMITS[model]:
        raise ValueError('参考图数量超过模型上限')
    paths = [item['path'] for item in asset.get('_reference_signature', [])] or list(dict.fromkeys(asset.get('reference_images', [])))
    roles = asset.get('reference_roles', {})
    workflow = {}
    previous = None
    upload = Client(client.url)
    for index, path in enumerate(images):
        node = str(100 + index)
        inputs = {'image': upload.upload(Path(path)), 'role': roles.get(paths[index], '综合参考')}
        if previous is not None:
            inputs['previous'] = [previous, 0]
        workflow[node] = {'class_type': 'DramaOptionalReferenceImage', 'inputs': inputs}
        previous = node
    from asset_contract import resolve_aspect_ratio
    inputs = {'model': model, 'prompt': prompt, 'aspect_ratio': resolve_aspect_ratio(
              options.get('workflow_lock'), options.get('aspect_ratio'), '1:1'),
              'quality': options.get('quality', 'medium'), 'seed': int.from_bytes(os.urandom(4), 'little') % 2147483648}
    if previous is not None:
        inputs['references'] = [previous, 0]
    workflow['30'] = {'class_type': 'DramaCloudImage', 'inputs': inputs}
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', asset.get('name', aid)).strip(' .')[:60]
    workflow['14'] = {'class_type': 'SaveImage', 'inputs': {'images': ['30', 0], 'filename_prefix': f'DramaAssets/{aid}_{name}'}}
    return workflow


def redact(value):
    """给人看的那一眼：前 4 位 ＋ ****，整把密钥从不摆到界面上（与模型配置同一套）。"""
    text = str(value or '')
    if len(text) <= 4:
        return '****' if text else ''
    return text[:4] + '****'


def settings(parent):
    import tkinter as tk
    import webbrowser
    from tkinter import ttk
    from ui_widgets import (Card, DescriptionBlock, FormDialog, LineInput, PrimaryButton,
                            ProgressLabel, SecondaryButton, notify)
    win = FormDialog(parent, '云图片模型 · Comfy 账户', modal=False, chrome=False)
    win.withdraw();win.transient(parent)
    body = Card(win, padding=16);body.pack(fill='both', expand=True)
    DescriptionBlock(body, text='Seedream 5.0 Pro / Nano Banana Pro / GPT Image 2', wraplength=560).pack(anchor='w')
    DescriptionBlock(body, text='使用 ComfyUI 账户余额；本地 FLUX 无需此密钥。', wraplength=560).pack(anchor='w', pady=6)
    DescriptionBlock(body,text='1. 打开 Comfy 账户并登录或注册。\n2. 在 API Keys 页面创建密钥，复制到下方并保存。\n3. 确认账户有可用余额，再返回手动制作资产。',wraplength=560).pack(anchor='w',pady=6)
    ttk.Label(body, text='Comfy API Key（统一保存到 程序目录/private/.env，不写入工作流）').pack(anchor='w')
    saved = get_key()
    token = tk.StringVar(value=saved)
    LineInput(body, textvariable=token, show='•', width=64).pack(fill='x', pady=6)
    status = tk.StringVar(value='已保存密钥（%s）' % redact(saved) if saved
                           else '尚未配置，暂不能从助手批量调用云模型')
    ProgressLabel(body, textvariable=status, wraplength=560).pack(anchor='w')
    row = ttk.Frame(body);row.pack(fill='x', pady=(12, 0))
    def save():
        try:save_key(token.get());win.destroy()
        except Exception as exc:notify(win, str(exc), level='error', title='保存失败', status=status)
    PrimaryButton(row, text='保存', command=save).pack(side='left')
    SecondaryButton(row, text='打开 Comfy 账户', command=lambda:webbrowser.open('https://platform.comfy.org/')).pack(side='left', padx=5)
    SecondaryButton(row, text='获取 API Key', command=lambda:webbrowser.open('https://platform.comfy.org/profile/api-keys')).pack(side='left', padx=5)
    win.update_idletasks()
    x = max(0, parent.winfo_rootx() + (parent.winfo_width()-win.winfo_reqwidth())//2)
    y = max(0, parent.winfo_rooty() + (parent.winfo_height()-win.winfo_reqheight())//2)
    win.geometry(f'+{x}+{y}');win.deiconify()
