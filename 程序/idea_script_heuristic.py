# -*- coding: utf-8 -*-
"""剧本启发式判断：一段回复够不够长、有没有至少两个剧本要素。

第 65 期任务 9：这段回复像不像「一份能开拍的剧本」——够长 ＋ 至少两个剧本要素，
给界面决定要不要弹「保存剧本」。只做纯文本判断：不读文件、不发网络、不碰 Tk。
"""
SCRIPT_MARKS = ('场景', '镜头', '分镜', '台词', '角色', '第一集', '第 1 集', '第1集')
SCRIPT_MIN = 300


def looks_like_script(text):
    """第 65 期任务 9：这段回复像不像一份能开拍的剧本（给界面决定要不要弹「保存剧本」）。"""
    value = str(text or '').strip()
    if len(value) < SCRIPT_MIN:
        return False
    return sum(1 for mark in SCRIPT_MARKS if mark in value) >= 2
