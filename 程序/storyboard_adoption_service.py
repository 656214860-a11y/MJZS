"""无人值守分镜采用的无界面轮询决策。"""


def automatic_poll_decision(signature, previous_signature, has_waiting, final_busy):
    """决定自动采用分镜应等待、跳过，还是扫描待采用文件。"""
    if final_busy:
        return {'action': 'wait', 'signature': signature}
    if signature == previous_signature and not has_waiting:
        return {'action': 'skip', 'signature': signature}
    return {'action': 'scan', 'signature': signature}
