# -*- coding: utf-8 -*-
"""剧本启发式判断：一段回复够不够长、有没有至少两个剧本要素。

第 65 期任务 9：这段回复像不像「一份能开拍的剧本」——够长 ＋ 至少两个剧本要素，
给界面决定要不要弹「保存剧本」。只做纯文本判断：不读文件、不发网络、不碰 Tk。
"""
import re

SCRIPT_MARKS = ('场景', '镜头', '分镜', '台词', '角色', '第一集', '第 1 集', '第1集')
SCRIPT_MIN = 300

# 「重新生成/重新创作/重新输出<阶段>」的口令识别，供剧本准备 API 与桌面 Agent
# 两条发送路径共用同一口径；纯文本判断，不读阶段配置、不依赖编排层。
_RESTART_REQUESTED = re.compile(
    r'(?:请)?重新(?:创作|生成|输出)(?:\s*(?:项目设定|剧本大纲|项目大纲|大纲|角色卡|自然剧本|剧本))?')


def looks_like_script(text):
    """第 65 期任务 9：这段回复像不像一份能开拍的剧本（给界面决定要不要弹「保存剧本」）。"""
    value = str(text or '').strip()
    if len(value) < SCRIPT_MIN:
        return False
    return sum(1 for mark in SCRIPT_MARKS if mark in value) >= 2


def writing_restart_requested(text):
    """仅认开头口令的显式重启指令；附件或正文里的字样不算。"""
    first = str(text or '').strip().split('\n', 1)[0].strip().rstrip('。！!')
    return bool(_RESTART_REQUESTED.fullmatch(first))

