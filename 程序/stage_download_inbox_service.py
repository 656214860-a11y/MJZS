"""桌面 Agent 任务的下载收件箱：登记目标文件并从「下载」文件夹收回（L3）。

从 `stage_execution_service` 拆出（R1619／Q9）：本机下载回收只经 L3 编排，
与阶段执行编排的其余部分无关。

`stage_execution_service` 仍按原名转发本模块的公开名。
"""
from __future__ import annotations

import time
from pathlib import Path

import file_cache


DOWNLOAD_INBOX_LEDGER = ('工作流任务', '下载收件箱.json')


def _download_inbox_path(project):
    return Path(project).resolve().joinpath(*DOWNLOAD_INBOX_LEDGER)


def register_download_inbox(project, prompt, now=None):
    """L3 编排：登记一次桌面 Agent 任务书里的目标文件，供之后从下载文件夹收回。"""
    import time
    from agent.core import save
    from download_inbox import expected_targets, remaining
    now = time.time() if now is None else now
    targets = expected_targets(project, prompt)
    if not targets:
        return ()
    ledger = _download_inbox_path(project)
    try:
        current = file_cache.read_json(ledger) if ledger.is_file() else {}
    except (OSError, ValueError):
        current = {}
    pending = current.get('pending', []) if isinstance(current, dict) else []
    names = {str(target) for target in targets}
    pending = [entry for entry in remaining(pending, (), now)
               if str(entry.get('target')) not in names]
    pending.extend({'target': str(target), 'since': now} for target in targets)
    save(ledger, {'version': 1, 'pending': pending})
    return targets


def collect_download_inbox(project, now=None, downloads=None):
    """L3 编排：把已下载到「下载」文件夹的目标文件收回项目；返回已写入的目标路径。"""
    import time
    from agent.core import save, save_file
    from download_inbox import match_registered, remaining
    ledger = _download_inbox_path(project)
    if not ledger.is_file():
        return []
    now = time.time() if now is None else now
    try:
        current = file_cache.read_json(ledger)
    except (OSError, ValueError):
        return []
    pending = current.get('pending', []) if isinstance(current, dict) else []
    if downloads is None:
        from platform_tools import downloads_directory
        downloads = downloads_directory()
    done, finished = [], []
    from agent.publication import transaction
    from platform_tools import execution_checkpoint
    # 下载件日期比登记目标新时写到新日期路径；登记表按原目标销账。
    for source, target, registered in match_registered(downloads, pending, now):
        try:
            if not source.stat().st_size:
                continue
        except OSError:
            continue
        try:
            with transaction():
                execution_checkpoint()
                save_file(target, source)
                execution_checkpoint()
        except (OSError, ValueError):
            continue
        done.append(target)
        finished.append(registered)
    kept = remaining(pending, finished, now)
    if kept != pending:
        save(ledger, {'version': 1, 'pending': kept})
    return done
