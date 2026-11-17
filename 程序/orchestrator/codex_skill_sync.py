"""Codex 单目标兼容入口；泛化实现已迁至 ``agent_skill_sync``（R3084）。

保留 ``sync_codex_skills``／``start_codex_skill_sync`` 旧签名与 patch 面
（``threading.Thread``、模块级 ``sync_codex_skills``），供存量测试与外部引用；
生产侧一律用 ``orchestrator.agent_skill_sync`` 的多目标入口。
"""
from __future__ import annotations

import threading

from orchestrator.agent_skill_sync import sync_agent_skills


def sync_codex_skills(program=None, skill_home=None):
    """同步到 Codex 目标目录；返回 written/unchanged/recycled/conflicts/errors。"""
    return sync_agent_skills(program=program, target='codex', skill_home=skill_home)


def start_codex_skill_sync(program=None, before=None):
    """首帧后启动 Codex 单目标后台维护；语义同旧版，仅同步 codex 目标。"""
    def run(program=None):
        try:
            before()
        except Exception:  # noqa: BLE001 - 维护前置步骤失败不能拖垮同步
            import infra.app_logging as app_logging
            app_logging.swallowed('Codex 同步前置维护失败')
        sync_codex_skills(program=program)

    worker = threading.Thread(target=run if callable(before) else sync_codex_skills,
                              kwargs={'program': program}, name='codex-skill-sync', daemon=True)
    worker.start()
    return worker
