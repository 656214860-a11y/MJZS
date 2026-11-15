"""桌面 Agent 任务的下载收件箱：登记目标文件并从「下载」文件夹收回（L3）。

从 `stage_execution_service` 拆出（R1619／Q9）：本机下载回收只经 L3 编排，
与阶段执行编排的其余部分无关。

`stage_execution_service` 仍按原名转发本模块的公开名。
"""
from __future__ import annotations

import time
from pathlib import Path

import file_cache
import contract.stage_layout as stage_layout


DOWNLOAD_INBOX_LEDGER = (stage_layout.WORKFLOW_DIR, '下载收件箱.json')


def _download_inbox_path(project):
    return Path(project).resolve().joinpath(*DOWNLOAD_INBOX_LEDGER)


def overwrite_backup_notice(backups):
    """给状态栏的一句话：覆盖前备份放在哪；没有备份返回空串。"""
    if not backups:
        return ''
    from storage_maintenance import OVERWRITE_BACKUP_DIR
    backup = Path(backups[-1][1])
    # 备份路径＝<项目>/工作流任务/覆盖前备份/<批次>/<原文件相对项目的路径>，提示到批次目录为止。
    folder = next((parent for parent in backup.parents if parent.parent.name == OVERWRITE_BACKUP_DIR),
                  backup.parent)
    return '覆盖前的原文件已备份到「' + str(folder) + '」；'


def _same_bytes(source, target):
    target = Path(target)
    if not target.is_file() or target.stat().st_size != Path(source).stat().st_size:
        return False
    return target.read_bytes() == Path(source).read_bytes()


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


def collect_download_inbox(project, now=None, downloads=None, backups=None):
    """L3 编排：把已下载到「下载」文件夹的目标文件收回项目；返回已写入的目标路径。

    目标已存在且内容不同时，先把原文件复制到项目「覆盖前备份」再覆盖，备份失败就不覆盖；
    传入 ``backups`` 列表时追加 ``(原文件, 备份副本)``。
    """
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
    from storage_maintenance import backup_before_overwrite
    # 下载件日期比登记目标新时写到新日期路径；登记表按原目标销账，对上同一份下载的旧登记一并销账。
    for source, target, registered in match_registered(downloads, pending, now):
        try:
            if not source.stat().st_size:
                continue
        except OSError:
            continue
        try:
            backup = None if _same_bytes(source, target) else backup_before_overwrite(project, target)
            with transaction():
                execution_checkpoint()
                save_file(target, source)
                execution_checkpoint()
        except (OSError, ValueError):
            continue
        if backup is not None and backups is not None:
            backups.append((target, backup))
        done.append(target)
        finished.extend(registered)
    kept = remaining(pending, finished, now)
    if kept != pending:
        save(ledger, {'version': 1, 'pending': kept})
    return done
