"""无人值守自动定稿的无界面派发决策。"""


def automatic_finalize_decision(signature, previous_signature, production_busy):
    """决定自动定稿应跳过、等待正在读工作稿的批次，还是启动一次定稿。"""
    if signature == previous_signature:
        return {'action': 'skip', 'signature': signature}
    if production_busy:
        return {'action': 'wait', 'signature': signature}
    return {'action': 'dispatch', 'signature': signature}
