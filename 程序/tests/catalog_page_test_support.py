"""旧页面行为用例显式完成目录任务，不以 Tk idle 代替后台完成证据。"""
from collections import deque
from types import SimpleNamespace
from unittest import mock


def show_catalog_page_ready(desktop, index):
    """控制目录线程接缝并应用结果；真实线程边界由 loading 用例单独验证。"""
    import storyboard_files
    import tk_timers

    tasks = deque()
    collectors = []
    real_thread = storyboard_files.threading.Thread
    real_repeat = tk_timers.repeat
    names = {'storyboard-catalog-scan', 'final-storyboard-catalog-scan'}
    callbacks = {'apply_background_catalog', 'apply_background_final_catalog'}

    def thread(*args, **kwargs):
        if kwargs.get('name') in names:
            return SimpleNamespace(start=lambda: tasks.append(kwargs['target']))
        return real_thread(*args, **kwargs)

    def repeat(widget, interval, callback):
        if callback.__name__ in callbacks:
            collectors.append(callback)
        return real_repeat(widget, interval, callback)

    with mock.patch.object(storyboard_files.threading, 'Thread', thread), \
            mock.patch.object(tk_timers, 'repeat', repeat):
        result = desktop.show(index)
        rounds = 0
        while tasks:
            rounds += 1
            if rounds > 10:
                raise AssertionError('目录任务未能稳定完成')
            while tasks:
                tasks.popleft()()
            for collect in collectors:
                collect()
        return result
