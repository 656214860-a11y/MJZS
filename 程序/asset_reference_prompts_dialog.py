"""资产提示词窗口（L4）；提示词取数与展示文本在 ``asset_reference_prompts``。"""
from asset_reference_prompts import display_prompt


def show_prompt(app,aid,asset):
    """资产提示词窗口：与首帧图片提示词窗口共用同一套「复制成功即关窗」行为。"""
    text=display_prompt(asset)
    if not text:raise ValueError('该资产缺少提示词；固定角色请在第1步补齐，场景、道具、临时角色请在第2步补齐')
    from prompt_window import show as show_prompt_window
    return show_prompt_window(app.win,aid+' · '+asset.get('name',aid)+' · 资产提示词',text,
                              status=getattr(app,'status',None),
                              receipt=aid+' 资产提示词已复制，可直接粘贴到生图工具',
                              source='来源：'+asset.get('prompt_source','资产清单'),scrollbar=True)
