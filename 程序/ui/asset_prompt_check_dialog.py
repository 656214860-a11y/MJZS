"""资产页「检查提示词」按钮：把缺项以弹窗列出（L4）；判定规则在 ``asset_prompt_rules``。"""
from infra.asset_prompt_rules import issues
from ui_widgets import notify


def check(app):
    scope=app.asset_scope();label={'all':'全部资产','adopted':'已采用分镜','current':'当前分镜'}[scope]
    rows=app.asset_requirements()
    missing=[aid+' '+str(asset.get('name',''))+'：'+'、'.join(errors)
             for aid,asset in rows.items() if (errors:=issues(aid,asset))]
    if missing:
        notify(app.win, '\n'.join(missing)+'\n\n固定角色请在第1步补齐；场景、道具、临时角色请在第2步补齐。',
               level='warning', title='资产提示词待补齐', status=app.status)
    else:notify(app.win, f'{label}的 {len(rows)} 项资产编号、名称和提示词已齐备，可以批量生成。',
                title='资产提示词检查', status=app.status)
