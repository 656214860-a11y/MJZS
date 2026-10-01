# -*- coding: utf-8 -*-
"""用例沙盒：把「全局配置目录」（program）指到临时目录（第 45 期）。

三虎的全局配置（自动化等级／预算／免打扰／贴片动画）落在 program 目录下的
`配置/宠物/配置.json`。自检里那些 `Agent(persist=False)`、`pet_ui.attach(...)` 原来 program
一直指向本机真安装目录，于是「出厂默认档是半自动」这种断言会被**用户机上那份配置**左右：
用户机上早先存过 `{"level": "hint"}`，用例就红了——红的样子跟被测功能没有半点关系。

这里给每个测试进程一个临时 program 目录（退出时删掉），测试文件在导入时把自己的
program 常量指过去：读不到真配置，也就写不脏真安装目录。
"""
import atexit
import shutil
import tempfile
from pathlib import Path

_ROOT = None


def sandbox_program():
    """这个测试进程专用的临时 program 目录（同一进程里多次调用返回同一个）。"""
    global _ROOT
    if _ROOT is None:
        _ROOT = Path(tempfile.mkdtemp(prefix="drama-selftest-"))
        atexit.register(shutil.rmtree, str(_ROOT), True)
    return _ROOT


def isolate(*modules):
    """把这些模块的 PROGRAM 指到沙盒目录；返回沙盒目录（模块没有 PROGRAM 就跳过它）。"""
    root = sandbox_program()
    for module in modules:
        if getattr(module, "PROGRAM", None) is not None:
            module.PROGRAM = root
    return root
