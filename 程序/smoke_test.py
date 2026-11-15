#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冒烟测试 —— 每轮任务完成后跑这一份（模板里那份 `smoke_test.sh` 的 Python 版）。

跑法（在哪个目录下跑都行：脚本按自己的位置找门禁，不看工作目录）：
    python smoke_test.py            只跑本轮快速检查项（默认，不启动门禁）
    python smoke_test.py --all      本轮检查项 ＋ 门禁（全量 `run_selftests.py --all`）
    python smoke_test.py --affected idea_chat workflow  本轮检查项 ＋ 指定模块门禁
    python smoke_test.py --gate     本轮检查项 ＋ 增量门禁（按台账）
    python smoke_test.py --checks   `python smoke_test.py` 的兼容别名
    python smoke_test.py --round 1  按第 1 轮登记的检查项跑（默认取下面的 ROUND）
    python smoke_test.py --list     只打出各轮登记了哪些检查项

模板里 `.sh` 那几类检查项都在这一份里：文件存在 / 目录存在 / 关键字 / JSON 字段 / 路由 /
模块可导入 / 组件可实例化。**每轮只跑本轮相关的那几条** —— 按轮次登记在 `ROUND_CHECKS`，
每轮只改一处：把上面那个 `ROUND` 加一，再照着样子往表里补几条。

真实门禁是 `run_selftests.py`：命令按本文件的位置拼、工作目录也切到那一层，超时给 900 秒
（实测全量约 318 秒，原来写 300 秒会误报超时）；输出落临时文件、不走管道，超时也不会卡住
（走上管道时，进程池里那些子进程会攥着管道不放，`communicate()` 一直等 EOF，实测挂 15 分钟不返回）。
"""
import app_logging
import ast
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


def _configure_console_utf8():
    """让 Windows 的 GBK 终端也能显示冒烟测试使用的状态符号。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            # 门禁会运行数分钟；即使调用端把 stdout 重定向到日志或 IDE 管道，也必须逐行可见。
            stream.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        except (AttributeError, OSError):
            pass


_configure_console_utf8()

HERE = Path(__file__).resolve().parent      # 程序（代码）根：本文件与 run_selftests.py 同一层
ROOT = HERE.parent                          # 安装根；表里的路径都相对它写（也可写绝对路径）
ROUND = 10                                  # 当前轮次：每轮只改这一个数字
GATE_TIMEOUT = 900                          # 门禁超时（秒）

PASS = 0
FAIL = 0
FAILED_ITEMS = []


# ── 检查器（模板 `.sh` 那几项的 Python 版）─────────────────────────────
def check(condition, msg):
    """记一条结果。"""
    global PASS, FAIL
    if condition:
        print('✅ ' + msg)
        PASS += 1
    else:
        print('❌ ' + msg)
        FAIL += 1
        FAILED_ITEMS.append(msg)


def _at(path):
    """表里的路径都相对安装根；写绝对路径也认。"""
    spot = Path(path)
    return spot if spot.is_absolute() else ROOT / spot


def check_file(path, msg=None):
    """文件存在。"""
    full = _at(path)
    check(full.is_file(), msg or ('文件存在：%s' % full))


def check_dir(path, msg=None):
    """目录存在。"""
    full = _at(path)
    check(full.is_dir(), msg or ('目录存在：%s' % full))


def check_keyword(path, keyword, msg=None):
    """文件里含这个关键字（`.sh` 里那句 grep）。"""
    full = _at(path)
    label = msg or ('%s 含：%s' % (full, keyword))
    try:
        text = full.read_text(encoding='utf-8')
    except Exception as exc:
        check(False, '%s（读取失败：%s）' % (label, type(exc).__name__))
        return
    check(keyword in text, label)


def check_absent(path, keyword, msg=None):
    """文件里不该再出现这个关键字（删掉的东西就靠它盯着；`.sh` 里那句 `! grep`）。"""
    full = _at(path)
    label = msg or ('%s 不含：%s' % (full, keyword))
    try:
        text = full.read_text(encoding='utf-8')
    except Exception as exc:
        check(False, '%s（读取失败：%s）' % (label, type(exc).__name__))
        return
    check(keyword not in text, label)

def check_json_field(path, field_path, msg=None):
    """JSON 里那个字段还在（`a.b.0.c` 这种点号路径，数字当下标）。"""
    full = _at(path)
    label = msg or ('%s 含字段：%s' % (full, field_path))
    try:
        current = json.loads(full.read_text(encoding='utf-8'))
        for key in str(field_path).split('.'):
            current = current[int(key)] if key.isdigit() else current[key]
    except Exception as exc:
        check(False, '%s（%s）' % (label, type(exc).__name__))
        return
    check(True, label)


def check_import(module, msg=None):
    """模块可导入（语法错、导入期的坑都在这一步暴露）。"""
    label = msg or ('模块可导入：%s' % module)
    try:
        __import__(module)
    except Exception as exc:
        check(False, '%s（%s: %s）' % (label, type(exc).__name__, exc))
        return
    check(True, label)


def check_route(module, name, expect=None, msg=None):
    """路由检查：那条「页面 / 阶段」入口还挂着，值还对不对。

    expect 给 None 只看在不在；给数字按长度比（阶段表 12 条）；其余按相等比。
    """
    label = msg or ('%s.%s（路由）' % (module, name))
    try:
        holder = importlib.import_module(module)
    except Exception as exc:
        check(False, '%s 读不到（%s: %s）' % (label, type(exc).__name__, exc))
        return
    value = getattr(holder, name, None)
    if value is None:
        check(False, '%s 不在' % label)
        return
    if expect is None:
        check(True, '%s 在：%r' % (label, value))
        return
    if isinstance(expect, int):
        try:
            ok = len(value) == expect
        except TypeError:
            ok = value == expect
    else:
        ok = value == expect
    check(ok, ('%s 是 %r（期望 %r）' % (label, value, expect)) if not ok
          else ('%s 是 %r' % (label, value)))


def check_tkinter_widget(module, cls, msg=None):
    """组件类能实例化（建个隐藏的 Tk 根，用完必拆）。"""
    label = msg or ('组件可实例化：%s.%s' % (module, cls))
    root = None
    try:
        import tkinter as tk
        widget_class = getattr(importlib.import_module(module), cls)
        root = tk.Tk()
        root.withdraw()
        try:
            widget_class(root)
        except TypeError:
            widget_class()
    except Exception as exc:
        check(False, '%s（%s: %s）' % (label, type(exc).__name__, exc))
        return
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                app_logging.swallowed('销毁 Tk 根')
    check(True, label)


# ── 每轮的检查项：只跑本轮那几条 ──────────────────────────────────────
# kind 八选一：file / dir / keyword / absent / json / import / route / widget
# 路径相对安装根写（`程序\...`）；msg 不写就自动生成一句。
ROUND_CHECKS = {
    1: [
        {'kind': 'file', 'path': r'程序\asset_thumbs.py', 'msg': '缩略图模块在'},
        {'kind': 'keyword', 'path': r'程序\asset_thumbs.py', 'keyword': 'def worker_main(',
         'msg': '后台解码进程入口在'},
        {'kind': 'keyword', 'path': r'程序\asset_thumbs.py', 'keyword': 'def placeholder_size(',
         'msg': '空盒子尺寸（ceil 算法）在'},
        {'kind': 'dir', 'path': r'程序\升级备份\Round1_20260923', 'msg': 'Round 1 的原版备份在'},
    ],
    2: [
        # 专项：本轮把冒烟测试对齐到 run_selftests.py
        {'kind': 'file', 'path': r'程序\smoke_test.py', 'msg': '冒烟脚本在程序根目录'},
        {'kind': 'file', 'path': r'程序\run_selftests.py', 'msg': '真实门禁在程序根目录'},
        {'kind': 'keyword', 'path': r'程序\smoke_test.py', 'keyword': 'Path(__file__)',
         'msg': '按脚本自己的位置找套件（不再看工作目录）'},
        {'kind': 'keyword', 'path': r'程序\smoke_test.py', 'keyword': 'GATE_TIMEOUT = 900',
         'msg': '门禁超时 900 秒'},
        {'kind': 'keyword', 'path': r'程序\smoke_test.py', 'keyword': 'ROUND_CHECKS',
         'msg': '分轮检查表在'},
        {'kind': 'keyword', 'path': r'程序\smoke_test.py', 'keyword': 'ROUND = 8',
         'msg': '当前轮次＝8'},
        {'kind': 'keyword', 'path': r'程序\smoke_test.py', 'keyword': '--all',
         'msg': '全量门禁留了开关'},
        {'kind': 'import', 'module': 'smoke_test',
         'msg': '冒烟脚本能当模块导入（没有语法错、没有导入期副作用）'},
        # 回归：贴在这一轮改动旁边的几条锚点
        {'kind': 'route', 'module': 'pet_bus', 'name': 'STAGE_NAMES', 'expect': 13,
         'msg': '13 个制作阶段的阶段表还挂着'},
        {'kind': 'json', 'path': r'程序\config.json', 'field': 'video_backend',
         'msg': '视频后端那条配置还在'},
        {'kind': 'widget', 'module': 'responsive_ui', 'klass': 'FlowBar',
         'msg': '按钮行组件还能实例化'},
        {'kind': 'dir', 'path': r'程序\维护记录', 'msg': '维护记录目录在（每轮落一份交付记录）'},
    ],
    5: [
        # 专项：本轮把「分镜定稿未同步分镜的可见重试」落到 04 页
        {'kind': 'keyword', 'path': r'程序\desktop.py', 'keyword': 'def auto_final_scan(',
         'msg': '定稿缺口那次扫描是只读的一份判据（desktop.auto_final_scan）'},
        {'kind': 'keyword', 'path': r'程序\desktop.py', 'keyword': 'def auto_final_state(',
         'msg': '04 页提示条的状态来源在（desktop.auto_final_state）'},
        {'kind': 'keyword', 'path': r'程序\desktop.py', 'keyword': 'def retry_auto_final(',
         'msg': '可见重试入口在（desktop.retry_auto_final）'},
        {'kind': 'keyword', 'path': r'程序\storyboard_files.py', 'keyword': '立即重试',
         'msg': '04 页那颗「立即重试」按钮在'},
        {'kind': 'keyword', 'path': r'程序\storyboard_files.py', 'keyword': 'auto_final_banner',
         'msg': '提示条的文字变量挂在 desktop 上（页面与自检都读它）'},
        {'kind': 'keyword', 'path': r'程序\storyboard_files.py', 'keyword': 'def refresh_state(',
         'msg': '提示条的刷新函数在（建页、列表变化、定时三处都调它）'},
        {'kind': 'file', 'path': r'程序\tests\test_ui_edges_autopilot.py', 'msg': 'UI 边界自检文件在'},
        {'kind': 'keyword', 'path': r'程序\tests\test_ui_edges_autopilot.py',
         'keyword': 'test_final_page_offers_visible_retry_for_unsynced_storyboard',
         'msg': '本轮那条可见重试的自检挂在 UI 边界用例里'},
        {'kind': 'import', 'module': 'storyboard_files',
         'msg': '分镜页模块能当模块导入（没有语法错、没有导入期副作用）'},
        # 回归：贴在本轮改动旁边的几条锚点
        {'kind': 'route', 'module': 'pet_state', 'name': 'PAGE_OF', 'expect': 13,
         'msg': '页面路由表是 12 个阶段'},
        {'kind': 'json', 'path': r'程序\config.json', 'field': 'video_backend',
         'msg': '视频后端那条配置还在'},
        {'kind': 'widget', 'module': 'responsive_ui', 'klass': 'FlowBar',
         'msg': '按钮行组件还能实例化（04 页那一行就是它）'},
    ],
    6: [
        # 专项：本轮把「资产中断的跨重启续跑台账」落到项目目录里
        {'kind': 'file', 'path': r'程序\asset_resume.py', 'msg': '续跑台账模块在'},
        {'kind': 'keyword', 'path': r'程序\asset_resume.py', 'keyword': 'def note_round(',
         'msg': '记账入口在（每个编号次数＋1、写下下次该重试的挂钟时刻）'},
        {'kind': 'keyword', 'path': r'程序\asset_resume.py', 'keyword': 'def delay(',
         'msg': '「离该重试还差几秒」在（跨重启按挂钟算，不用 monotonic）'},
        {'kind': 'keyword', 'path': r'程序\asset_resume.py', 'keyword': 'def clear(',
         'msg': '缺图补齐后清台账的入口在'},
        {'kind': 'keyword', 'path': r'程序\asset_resume.py', 'keyword': '资产续跑台账.json',
         'msg': '台账落在项目自己的 workflows 目录'},
        {'kind': 'keyword', 'path': r'程序\asset_resume.py', 'keyword': 'time.time()',
         'msg': '记的是挂钟时刻（monotonic 的起点每趟进程都不一样）'},
        {'kind': 'keyword', 'path': r'程序\desktop.py', 'keyword': 'def restore_asset_resume(',
         'msg': '打开项目时把台账读回来（换项目要重读）'},
        {'kind': 'keyword', 'path': r'程序\desktop.py', 'keyword': 'def note_asset_resume(',
         'msg': '一轮没做出图时记账的入口在'},
        {'kind': 'keyword', 'path': r'程序\desktop.py', 'keyword': 'def asset_pending_ids(',
         'msg': '还缺哪几个编号（收尾与台账都按编号记账）'},
        {'kind': 'keyword', 'path': r'程序\desktop.py', 'keyword': 'import asset_resume',
         'msg': '桌面程序挂上了续跑台账'},
        {'kind': 'file', 'path': r'程序\tests\test_asset_resume.py', 'msg': '台账自检文件在'},
        {'kind': 'keyword', 'path': r'程序\tests\test_ui_edges_autopilot.py',
         'keyword': 'test_asset_resume_ledger_carries_the_backoff_across_restart',
         'msg': '本轮「重启后接着跑」的自检挂在 UI 边界用例里'},
        {'kind': 'import', 'module': 'asset_resume',
         'msg': '台账模块能当模块导入（没有语法错、没有导入期副作用）'},
        # 回归：贴在本轮改动旁边的几条锚点
        {'kind': 'route', 'module': 'pet_state', 'name': 'PAGE_OF', 'expect': 13,
         'msg': '页面路由表是 12 个阶段'},
        {'kind': 'json', 'path': r'程序\config.json', 'field': 'video_backend',
         'msg': '视频后端那条配置还在'},
        {'kind': 'widget', 'module': 'responsive_ui', 'klass': 'FlowBar',
         'msg': '按钮行组件还能实例化'},
    ],
    7: [
        # 专项：本轮把「写入即校验行尾」的防护与门禁落地
        {'kind': 'file', 'path': r'程序\line_endings.py', 'msg': '行尾防护模块在'},
        {'kind': 'keyword', 'path': r'程序\line_endings.py', 'keyword': 'def write_text(',
         'msg': '唯一那条写入路在（写入即校验行尾）'},
        {'kind': 'keyword', 'path': r'程序\line_endings.py', 'keyword': 'def compose(',
         'msg': '「正文先归一、再按目标换行符铺开」在'},
        {'kind': 'keyword', 'path': r'程序\line_endings.py', 'keyword': 'def detect_eol(',
         'msg': '认目标文件自己的换行符在'},
        {'kind': 'keyword', 'path': r'程序\line_endings.py', 'keyword': 'def problems(',
         'msg': '查落单／重复 CR 的判据在'},
        {'kind': 'keyword', 'path': r'程序\line_endings.py', 'keyword': 'def audit(',
         'msg': '扫整棵目录的入口在（门禁用它体检）'},
        {'kind': 'keyword', 'path': r'程序\line_endings.py', 'keyword': "newline=''",
         'msg': '原样写：newline 空串，一个字节都不翻译'},
        {'kind': 'keyword', 'path': r'程序\run_selftests.py', 'keyword': 'line_endings.write_text',
         'msg': '自检台账那处写入已走上这条路'},
        {'kind': 'keyword', 'path': r'程序\skill_tools.py', 'keyword': 'line_endings.write_text',
         'msg': '字幕文件那处写入已走上这条路'},
        {'kind': 'file', 'path': r'程序\tests\test_line_endings.py', 'msg': '行尾门禁自检文件在'},
        {'kind': 'keyword', 'path': r'程序\tests\test_line_endings.py',
         'keyword': 'test_the_program_tree_has_no_cr_cr_lf',
         'msg': '整棵程序目录的行尾体检在'},
        {'kind': 'keyword', 'path': r'程序\tests\test_line_endings.py',
         'keyword': 'test_the_victims_keep_their_own_line_endings',
         'msg': '第 62 期那批受害文件的行尾被钉住在'},
        {'kind': 'keyword', 'path': r'程序\tests\test_line_endings.py',
         'keyword': 'test_the_writers_go_through_the_helper',
         'msg': '「写入路径都走它」那条静态检查在'},
        {'kind': 'import', 'module': 'line_endings',
         'msg': '行尾模块能当模块导入（没有语法错、没有导入期副作用）'},
        # 回归：贴在本轮改动旁边的几条锚点
        {'kind': 'keyword', 'path': r'程序\smoke_test.py', 'keyword': 'ROUND = 8',
         'msg': '当前轮次＝8'},
        {'kind': 'route', 'module': 'pet_state', 'name': 'PAGE_OF', 'expect': 13,
         'msg': '页面路由表是 12 个阶段'},
        {'kind': 'json', 'path': r'程序\config.json', 'field': 'video_backend',
         'msg': '视频后端那条配置还在'},
        {'kind': 'widget', 'module': 'responsive_ui', 'klass': 'FlowBar',
         'msg': '按钮行组件还能实例化'},
    ],
    8: [
        # 专项①：Claude Code 真机验证（入口 ＋ 台账）
        {'kind': 'file', 'path': r'程序\engine_probe.py', 'msg': '引擎真机验证入口在'},
        {'kind': 'keyword', 'path': r'程序\engine_probe.py', 'keyword': 'def verdict_of(',
         'msg': '四种结论的判据在（verified／开关缺／一次性不通／没装）'},
        {'kind': 'keyword', 'path': r'程序\engine_probe.py', 'keyword': 'def record(',
         'msg': '验证台账的落盘口在'},
        {'kind': 'file', 'path': r'程序\tests\test_engine_probe.py', 'msg': '引擎验证的自检文件在'},
        {'kind': 'json', 'path': r'程序\维护记录\引擎真机验证.json', 'field': 'engines.codex.verdict',
         'msg': '台账里 codex 那一行的结论在（本机实测 verified）'},
        # 专项②：白模视频上传接口
        {'kind': 'file', 'path': r'程序\white_model_ref.py', 'msg': '白模参考视频的接口口径在'},
        {'kind': 'keyword', 'path': r'程序\white_model_ref.py', 'keyword': 'def descriptor(',
         'msg': '「验过再给描述」在（存在／后缀／空文件／上限四道）'},
        {'kind': 'keyword', 'path': r'程序\white_model_ref.py', 'keyword': 'def prompt_line(',
         'msg': '「这份视频是干什么用的」那句话在'},
        {'kind': 'keyword', 'path': r'程序\agent\shot_assets.py', 'keyword': '_white_model_reference',
         'msg': '分镜那一份副本上挂着白模参考那一条'},
        {'kind': 'keyword', 'path': r'程序\agent\wan.py', 'keyword': 'white_entries(',
         'msg': '万相那一支把参考视频拼进 media'},
        {'kind': 'keyword', 'path': r'程序\agent\volcengine.py', 'keyword': 'white_entries(',
         'msg': 'Seedance 那一支把参考视频拼进 content'},
        {'kind': 'keyword', 'path': r'程序\engine.py', 'keyword': 'validate_video_submission',
         'msg': '提交口先验白模那一份'},
        {'kind': 'file', 'path': r'程序\tests\test_white_model_ref.py', 'msg': '白模接口的自检文件在'},
        {'kind': 'import', 'module': 'white_model_ref',
         'msg': '白模接口模块能当模块导入（没有语法错、没有导入期副作用）'},
        # 专项③：剧本 SKILL 的合并与降级收口
        {'kind': 'keyword', 'path': r'程序\script_contract.py', 'keyword': 'def support_rows(',
         'msg': '收口表在（合并／降级的那两个并回哪一段、产物落哪）'},
        {'kind': 'keyword', 'path': r'程序\script_contract.py', 'keyword': 'def merge_problems(',
         'msg': '收口体检在（归属者声明过子步骤＋落点是真的）'},
        {'kind': 'keyword', 'path': r'程序\script_contract.py', 'keyword': 'MERGE_OWNER',
         'msg': '唯一归属者只有这一处口径'},
        {'kind': 'keyword', 'path': r'程序\tests\test_script_contract.py', 'keyword': 'class MergeTests',
         'msg': '本轮那组收口自检挂在剧本契约用例里'},
        {'kind': 'keyword', 'path': r'程序\skills\02 剧本整理SKILL\script-structured-generation.skill.md',
         'keyword': 'script-dialogue-polish', 'msg': '归属者的说明里写清了台词那一段的子步骤'},
        {'kind': 'keyword', 'path': r'程序\skills\02 剧本整理SKILL\script-structured-generation.skill.md',
         'keyword': 'script-worldbuilding', 'msg': '归属者的说明里写清了设定那一段的子步骤'},
        # 专项④：弹窗的最小化／最大化键位已删（删除用例：absent）
        {'kind': 'absent', 'path': r'程序\ui_theme.py', 'keyword': 'window_buttons',
         'msg': '画那两颗键的函数已不在 ui_theme 里'},
        {'kind': 'absent', 'path': r'程序\ui_theme.py', 'keyword': 'bare_window',
         'msg': '第 67 期那条摘键位的路也一并删了'},
        {'kind': 'keyword', 'path': r'程序\tests\test_ui_theme.py', 'keyword': 'NoPopupKeyTests',
         'msg': '「弹窗不长键位」那条回归自检在'},
        # 回归：贴在本轮改动旁边的几条锚点
        {'kind': 'keyword', 'path': r'程序\smoke_test.py', 'keyword': 'ROUND = 8',
         'msg': '当前轮次＝8'},
        {'kind': 'route', 'module': 'pet_state', 'name': 'PAGE_OF', 'expect': 13,
         'msg': '页面路由表是 12 个阶段'},
        {'kind': 'json', 'path': r'程序\config.json', 'field': 'video_backend',
         'msg': '视频后端那条配置还在'},
        {'kind': 'widget', 'module': 'responsive_ui', 'klass': 'FlowBar',
         'msg': '按钮行组件还能实例化'},
    ],
    9: [
        {'kind': 'keyword', 'path': r'程序\desktop.py', 'keyword': 'def start_script_workflow(',
         'msg': '剧本发送统一进入 Agent 工作流'},
        {'kind': 'keyword', 'path': r'程序\workflow_tasks.py', 'keyword': '禁止擅自直接返回剧本、大纲或分镜方案',
         'msg': '剧本任务带 SKILL 开工门禁'},
        {'kind': 'absent', 'path': r'程序\desktop.py', 'keyword': "client.ask('chat'",
         'msg': '剧本页没有绕过工作流的聊天 API 调用'},
        {'kind': 'keyword', 'path': r'程序\pet_ui.py', 'keyword': 'def open_claude_desktop(',
         'msg': 'Claude 桌面启动入口在'},
        {'kind': 'keyword', 'path': r'程序\pet_models_ui.py', 'keyword': '打开 Claude 桌面',
         'msg': 'API 统一配置展示 Claude 桌面入口'},
        {'kind': 'file', 'path': r'程序\tests\test_idea_chat.py',
         'msg': '剧本工作流回归测试在'},
        {'kind': 'file', 'path': r'程序\tests\test_workflow.py',
         'msg': '鲸剧 SKILL 路由回归测试在'},
        {'kind': 'route', 'module': 'pet_bus', 'name': 'STAGE_NAMES', 'expect': 13,
         'msg': '13 个制作阶段路由仍完整'},
    ],
    10: [
        {'kind': 'keyword', 'path': r'程序\model_pool.py', 'keyword': "'chatgpt-desktop': 'codex'",
         'msg': 'ChatGPT Desktop 是模型池中的 Codex 调用目标'},
        {'kind': 'keyword', 'path': r'程序\model_pool.py', 'keyword': "'claude-desktop': 'claude'",
         'msg': 'Claude Desktop 是模型池中的 Claude 调用目标'},
        {'kind': 'absent', 'path': r'程序\pet_models_ui.py', 'keyword': '打开 Claude 桌面',
         'msg': 'API 统一配置不再放 Claude 桌面启动按钮'},
        {'kind': 'keyword', 'path': r'程序\skill_panel_support.py', 'keyword': 'def grouped_model_choices(',
         'msg': '阶段配置具备供应商到模型的两级下拉数据'},
        {'kind': 'keyword', 'path': r'程序\workflow_settings.py', 'keyword': 'STAGE_CONFIG_STAGES',
         'msg': '工作流阶段正确映射到阶段配置'},
        {'kind': 'keyword', 'path': r'程序\idea_transcript.py', 'keyword': 'def load(root, model=None, *, gateway=None):',
         'msg': '切换模型保留各自独立聊天记录且经 L3 网关读取'},
        {'kind': 'file', 'path': r'程序\tests\test_workflow.py', 'msg': '桌面模型工作流回归测试在'},
        {'kind': 'route', 'module': 'pet_bus', 'name': 'STAGE_NAMES', 'expect': 13,
         'msg': '13 个制作阶段路由仍完整'},
    ],
}

KINDS = {
    'file': lambda e: check_file(e['path'], e.get('msg')),
    'dir': lambda e: check_dir(e['path'], e.get('msg')),
    'keyword': lambda e: check_keyword(e['path'], e['keyword'], e.get('msg')),
    'absent': lambda e: check_absent(e['path'], e['keyword'], e.get('msg')),
    'json': lambda e: check_json_field(e['path'], e['field'], e.get('msg')),
    'import': lambda e: check_import(e['module'], e.get('msg')),
    'route': lambda e: check_route(e['module'], e['name'], e.get('expect'), e.get('msg')),
    'widget': lambda e: check_tkinter_widget(e['module'], e['klass'], e.get('msg')),
}


def entry_label(entry):
    """一条检查项的一句话说法（--list 与兜底报错都用它）。"""
    bits = [str(entry[key]) for key in ('path', 'keyword', 'field', 'module', 'name', 'klass')
            if entry.get(key)]
    return '%s(%s)' % (entry.get('kind'), ' '.join(bits)) if bits else str(entry.get('kind'))


def run_check(entry):
    """按登记的那一条跑一个检查器；检查器自己出事也算这条没过。"""
    runner = KINDS.get(entry.get('kind'))
    if runner is None:
        check(False, '不认识的检查项：%r' % entry.get('kind'))
        return
    try:
        runner(entry)
    except Exception as exc:
        check(False, '%s 跑不动（%s: %s）' % (entry_label(entry), type(exc).__name__, exc))


# ── 真实门禁：run_selftests.py ────────────────────────────────────────
_AFFECTED_TEST_ALIASES = {
    # 运行器和冒烟脚本共用 tests/test_selftests.py；源模块名本身不能匹配 test_ 文件名。
    'run_selftests': 'selftests',
    'smoke_test': 'selftests',
    # 注册表对应的回归文件沿用历史复数命名，不能由模块名直接推导。
    'skill_registry': 'skills',
    'skill_panel': 'skills',
    # 分镜定稿 UI 的行为由无 Tk 控制器与 Tk 视图两份用例共同覆盖。
    'storyboard_files': 'storyboard_final_controller final_viewer file_cache',
      'asset_detail': 'asset_detail asset_thumbs',
    # 设置窗口的构造分在主设置与模型子窗；两者复用同一专项回归文件。
    'pet_settings_ui': 'pet_settings',
    'pet_models_ui': 'pet_settings',
      # 基础设施文件名与历史测试文件名不同，定向门禁必须覆盖其生命周期回归。
      'storage_maintenance': 'storage',
}


def _test_module_name(path, tests_dir):
    """将 tests/ 下的文件路径还原为 run_selftests 使用的模块名。"""
    return '.'.join(path.relative_to(tests_dir).with_suffix('').parts)


def _direct_imports(path):
    """读取一个测试文件的顶层导入名；坏文件交给真正的门禁报告，不在这里中断。"""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError, UnicodeError):
        return frozenset()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.', 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names.add(node.module.split('.', 1)[0])
    return frozenset(names)


def _affected_test_plan(affected):
    """在 --affected 实际被调用时，找出筛选词及将被运行的测试模块。"""
    names = tuple(str(name) for name in affected if str(name))
    aliases = affected_test_filters(names)
    targets = {name.split('.', 1)[0] for name in names}
    tests_dir = HERE / 'tests'
    test_imports = tuple(
        (_test_module_name(path, tests_dir), _direct_imports(path))
        for path in sorted(tests_dir.glob('**/test_*.py'))
    ) if targets else ()
    consumers = tuple(name for name, imports in test_imports if targets & imports)
    filters = tuple(dict.fromkeys((*aliases, *consumers)))
    keys = tuple(key for item in filters for key in item.split())
    selected = tuple(name for name, _imports in test_imports
                     if any(key in name for key in keys))
    return filters, selected


def affected_test_filters(affected):
    """保留既有的源码模块名到 run_selftests 筛选词映射。"""
    return tuple(dict.fromkeys(_AFFECTED_TEST_ALIASES.get(str(name), str(name))
                               for name in affected if str(name)))


def affected_test_modules(affected):
    """返回 run_selftests 会因 --affected 选中的测试模块，供显示与回归测试使用。"""
    return _affected_test_plan(affected)[1]


def gate_args(full, safe=False, affected=(), filters=None):
    """门禁一律串行，避免冒烟时并行 Tk／缩略图 worker 抢占用户电脑。"""
    if safe:
        return ['--safe']
    if full:
        return ['--all', '--serial']
    if affected:
        filters = affected_test_filters(affected) if filters is None else filters
        return ['--serial', '-k', ' '.join(filters)]
    return ['--serial']


def check_the_gate(full, safe=False, affected=()):
    """跑显式请求的门禁：定向、增量或全量均使用串行模式。

    命令按本文件的位置拼、工作目录也切到这一层：套件是按自己的位置找用例与基础文件的。
    """
    suite = HERE / 'run_selftests.py'
    if not suite.is_file():
        check(False, '门禁脚本在：%s' % suite)
        return
    mode = ('安全全量' if safe else ('全量串行' if full else
            ('定向：' + '、'.join(affected) if affected else '增量串行')))
    # 子进程输出直接落文件，避免 Tk 子进程继承 PIPE 后让 communicate() 等不到 EOF；
    # 同时用 -u 和下面的增量读取把进度实时还给用户，不能再出现数分钟「像卡死」的空白。
    filters, selected = _affected_test_plan(affected) if affected else ((), ())
    cmd = [sys.executable, '-u', str(suite)] + gate_args(full, safe, affected, filters)
    print('\n--- 门禁：run_selftests.py（%s）---' % mode)
    print('    ' + ' '.join(cmd))
    print('    工作目录：%s' % HERE)
    if affected:
        print('    （只执行与本轮改动相关的测试模块）')
        preview = '、'.join(selected[:8])
        suffix = ' …' if len(selected) > 8 else ''
        print('    已选测试：%d 个%s%s' % (len(selected), '；' + preview if preview else '', suffix))
    elif not full:
        print('    （按台账只跑动过的测试文件；全量改用 python smoke_test.py --all）')
    log = Path(tempfile.gettempdir()) / ('smoke_gate_%s.log' % os.getpid())
    started = time.perf_counter()
    code, note = -1, ''
    offset = 0
    try:
        with open(log, 'w', encoding='utf-8', errors='replace') as sink:
            process = subprocess.Popen(cmd, cwd=str(HERE), stdout=sink,
                                       stderr=subprocess.STDOUT)
        while process.poll() is None:
            if time.perf_counter() - started > GATE_TIMEOUT:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                note = '超时（>%d 秒）' % GATE_TIMEOUT
                break
            try:
                with open(log, 'r', encoding='utf-8', errors='replace') as source:
                    source.seek(offset)
                    fresh = source.read()
                    offset = source.tell()
                for line in fresh.splitlines():
                    print('    ' + line.rstrip())
            except OSError:
                pass
            time.sleep(0.25)
        if not note:
            code = process.wait()
    except Exception as exc:
        note = '%s: %s' % (type(exc).__name__, exc)
    spent = time.perf_counter() - started
    try:
        tail = log.read_text(encoding='utf-8', errors='replace').splitlines()[-12:]
    except OSError:
        tail = []
    for line in tail:
        print('    ' + line.rstrip())
    try:
        log.unlink()
    except OSError:
        pass
    head = '门禁 run_selftests.py（%s）：%.0f 秒' % (mode, spent)
    no_selected_tests = bool(affected) and '跑 0 个测试文件' in '\n'.join(tail)
    check(code == 0 and not no_selected_tests,
          head + (' → 定向筛选未命中任何测试' if no_selected_tests
                  else (' → 0 个文件有红' if code == 0
                        else ' → ' + (note or '退出码 %s' % code))))


# ── 入口 ─────────────────────────────────────────────────────────────
USAGE = """用法：python smoke_test.py [--all | --safe | --affected 模块... | --gate | --checks | --round N | --list | --architecture]

  （不跟参数）   只跑本轮快速检查项（通常 10～30 秒）
  --all          门禁改成全量 run_selftests.py --all（约 5～7 分钟）
  --safe         门禁改成安全全量：run_selftests.py --safe（全量但一次只建一套 Tk 界面）
  --affected ... 只跑指定测试模块，例如：--affected idea_chat workflow
  --gate         跑增量门禁（按台账只跑动过的测试文件）
  --checks       只跑本轮检查项（兼容旧命令）
  --round N      按第 N 轮登记的检查项跑（默认取脚本里的 ROUND）
  --list         只打出各轮登记了哪些检查项
  --architecture  仅运行 tests/architecture 架构治理测试
"""


def main(argv=None):
    # 自检子进程继承：通知分发器不弹系统模态框，避免无人值守时卡住（见 ui_widgets.SUPPRESS_MODAL_ENV）。
    os.environ.setdefault("DRAMA_SUPPRESS_MODAL", "1")
    os.environ.setdefault("DRAMA_SUPPRESS_TRAY", "1")
    os.environ.setdefault("DRAMA_SUPPRESS_NETWORK", "1")
    os.environ.setdefault("DRAMA_SUPPRESS_DIAGNOSTICS", "1")  # 测试报错不写程序自己的诊断记录
    os.environ.setdefault("DRAMA_REDUCE_MOTION", "0")  # 自检固定保留动效，不随本机系统设置漂移
    args = list(sys.argv[1:] if argv is None else argv)
    round_no, full, safe, skip_gate, listing, architecture, affected = ROUND, False, False, True, False, False, []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == '--all':
            full, skip_gate = True, False
        elif arg == '--safe':
            full, safe, skip_gate = True, True, False
        elif arg == '--gate':
            skip_gate = False
        elif arg == '--architecture':
            architecture = True
        elif arg == '--affected':
            index += 1
            while index < len(args) and not args[index].startswith('--'):
                affected.append(args[index])
                index += 1
            if not affected:
                print('--affected 后面要跟至少一个测试模块名')
                return 2
            skip_gate = False
            index -= 1
        elif arg in ('--checks', '--no-gate'):
            skip_gate = True
        elif arg == '--list':
            listing = True
        elif arg == '--round':
            index += 1
            if index >= len(args):
                print('--round 后面要跟轮次号')
                return 2
            try:
                round_no = int(args[index])
            except ValueError:
                print('轮次号得是数字：%r' % args[index])
                return 2
        elif arg in ('-h', '--help'):
            print(USAGE)
            return 0
        else:
            print('不认识的参数：%s\n\n%s' % (arg, USAGE))
            return 2
        index += 1

    if listing:
        for no in sorted(ROUND_CHECKS):
            print('第 %d 轮（%d 条）：' % (no, len(ROUND_CHECKS[no])))
            for entry in ROUND_CHECKS[no]:
                print('    ' + entry_label(entry))
        return 0

    sys.path.insert(0, str(HERE))      # 检查器要按模块名导入程序根下的东西
    if ROOT.is_dir():
        sys.path.insert(0, str(ROOT))

    if architecture:
        architecture_dir = HERE / 'tests' / 'architecture'
        if not architecture_dir.is_dir():
            check(False, '结构测试目录存在：缺少 tests/architecture')
            return 1
        # 只在显式架构扫描时加入目录；默认冒烟流程不加载该测试集。
        sys.path.insert(0, str(architecture_dir))
        suite = unittest.defaultTestLoader.discover(
            str(architecture_dir), pattern='test_*.py', top_level_dir=str(HERE)
        )
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        check(result.wasSuccessful(), '架构治理测试：tests/architecture')
        return 0 if result.wasSuccessful() else 1

    print('=' * 50)
    print('冒烟测试 · 第 %d 轮' % round_no)
    print('程序根：%s' % HERE)
    print('=' * 50)

    print('\n--- 本轮检查项 ---')
    entries = ROUND_CHECKS.get(round_no)
    if not entries:
        check(False, '第 %d 轮还没登记检查项（照 ROUND_CHECKS 里第 2 轮的样子补几条）' % round_no)
    else:
        for entry in entries:
            run_check(entry)

    if skip_gate:
        print('\n--- 门禁：默认快速检查，未启动 ---')
    else:
        check_the_gate(full, safe, affected)

    print('\n' + '=' * 50)
    print('通过：%d 项' % PASS)
    print('失败：%d 项' % FAIL)
    print('=' * 50)
    if FAIL:
        print('\n❌ 未通过的检查项：')
        for item in FAILED_ITEMS:
            print('  - ' + item)
        print('\n冒烟测试未通过，请修复后再进入下一轮')
        return 1
    print('\n✅ 冒烟测试通过，可以进入下一轮')
    return 0


if __name__ == '__main__':
    sys.exit(main())
