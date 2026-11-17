"""「无人值守自动XX」勾选前的确认弹窗（L4）；项目设置读写仍在 ``project_settings``。"""
from ui_widgets import ask_confirmation

def confirm_unattended(text, parent=None):
    """勾上「无人值守自动XX」之前先确认一次（第 32 期第 2 条）。

    自动排队的活会自己往下跑，勾错一次就是一批任务被派出去；先问一句，用户点「否」时
    调用方负责把勾选框还原成未勾选。关闭时不用问（这里直接放行）。
    """
    return ask_confirmation(parent, '确认开启无人值守',
        text+'\n\n开启后三虎会按这一页的规则自动排队执行，遇到要花钱或要您确认的步骤仍会停下来。\n要现在开启吗？',
        dangerous=True)
