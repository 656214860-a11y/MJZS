"""遗留临时文件的受控清扫（L1 任务书轮 2 R2-g）。

只匹配 ``agent.core.temporary_path`` 产出的 ``<原名>.<32位hex>.<后缀>``
形态；用户自起的 ``剧本.tmp`` 之类没有 32 位十六进制段，永远不会命中。
物理删除经 ``file_cache.remove_temporary_file``（删除白名单内的唯一入口），
不跟随符号链接展开到项目根之外。
"""
import logging
import os
import re
import threading
import time
from pathlib import Path

import infra.app_logging as app_logging
import infra.file_cache as file_cache

TEMP_SWEEP_MAX_AGE_SECONDS = 24 * 3600
# 清扫线程的最早启动时刻（毫秒）：必须晚于「窗口出现到可交互」的启动窗口
# （规则 33，实测约 1.5 秒），否则后台线程里的 os.walk 会被启动零扫描门禁
# 计入违规。与 ui.desktop_account_page.RENEW_DELAY_MS 同档的保守延迟。
TEMP_SWEEP_START_DELAY_MS = 3000
_TEMP_NAME_RE = re.compile(r'\.[0-9a-fA-F]{32}\.(?:tmp|download|recover|partial\.mp4)$')


def is_stale_temporary_name(name):
    return bool(_TEMP_NAME_RE.search(name))


def sweep_stale_temporary_files(root, *, now=None, max_age_seconds=TEMP_SWEEP_MAX_AGE_SECONDS,
                                stats=None):
    """删除项目内超过时限的遗留临时文件，返回删除数；单个失败跳过不挡其余。

    ``stats`` 传入 dict 时回填 ``remaining``＝超期但未删净的文件数（供启动自检
    读取，不在检查项里现场扫目录）。
    """
    root = Path(root)
    cutoff = (time.time() if now is None else float(now)) - float(max_age_seconds)
    removed = 0
    remaining = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            if not is_stale_temporary_name(name):
                continue
            target = Path(dirpath) / name
            try:
                if target.stat().st_mtime >= cutoff:
                    continue
                if file_cache.remove_temporary_file(target):
                    removed += 1
                elif target.exists():
                    remaining += 1
            except OSError:
                continue
    if stats is not None:
        stats['remaining'] = remaining
    return removed


def sweep_opened_projects(projects):
    """退出维护进程清扫显式项目；仅汇总成功项，诊断失败不挡其它维护。"""
    removed = remaining = 0
    for project in dict.fromkeys(projects):
        target = Path(project)
        if target.is_dir() and not target.is_symlink() and not target.is_junction():
            stats = {}
            try:
                count = sweep_stale_temporary_files(target, stats=stats)
            except (OSError, ValueError):
                continue
            removed += count
            remaining += stats.get('remaining', 0)
    try:
        from infra import diagnostic_capture
        diagnostic_capture.record_temporary_sweep(removed, remaining)
    except Exception:
        app_logging.swallowed()


def schedule_stale_temporary_sweep(root):
    """后台清扫兼容入口；调用方须在启动可交互边界之后调度，线程本身不豁免规则33。"""
    target = Path(root)

    def work():
        try:
            stats = {}
            removed = sweep_stale_temporary_files(target, stats=stats)
            try:
                from infra import diagnostic_capture
                diagnostic_capture.record_temporary_sweep(removed, stats.get('remaining', 0))
            except Exception:
                app_logging.swallowed()
            if removed:
                logging.getLogger(__name__).info('遗留临时文件清扫完成：%s 删除 %d 个', target, removed)
        except Exception:
            app_logging.swallowed()

    threading.Thread(target=work, daemon=True, name='stale-temporary-sweep').start()
