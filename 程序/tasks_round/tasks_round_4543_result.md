# tasks_round_4543_result — L5-E2-E3-REF-L5-1 解开启动器变基冲突
<!-- round-evidence: {"commit_base": "e60da9e0e", "credential_hits": 0, "evidence_sha256": "d4a354735c5f467b", "exit": 0, "failed": 0, "passed": 127, "round": 4543, "tests": "run_selftests.py -k desktop_launcher startup_selfcheck ui_status_bus app_metadata"} -->

- 本轮类型：任务卡 `L5-E2-E3-REF-L5-1`（波次 `W2`）的变基收尾轮，只做冲突解决，无功能改动。车道 `codex/l5-entry-hardening`，基准 `e60da9e0e`，索引为调度已暂存的变基合并结果。
- 测试跑了吗、三个基线过了吗：定向测试随本批提交门禁 `--tests desktop_launcher startup_selfcheck ui_status_bus app_metadata` 执行，证据文件 `tasks_round/evidence/R4543.json` 由 `dev.py commit` 生成；卡面两条验收命令在提交后各试一次，结果记录于会话完成报告。本文件写于提交前，门禁被拒或验收失败按实记录、不改写。
- 欠账少了吗：无新增欠账；本轮不动任何已暂存文件的语义内容，仅消除 `desktop_launcher.py` 的冲突标记。

## 改动清单（文件:行号）

- `程序/desktop_launcher.py`（唯一手改文件）：`launch()` 内 L223–L248 的冲突段（`<<<<<<< master` / `=======` / `>>>>>>> 6aad2bfc8`）收敛为分支侧语义——`if selfcheck:` 内只留 `degraded_items, safe_start = run_preflight(Path(__file__).resolve().parent)`；紧随其后、`from desktop import Desktop` 之前保留 L5 组合根三行（注释「L5 组合根：把 L4 的 SKILL 工具适配器注入 L3；编排器本身不反向依赖 UI。」、`import ui.skill_tools as skill_tools`、`skill_tools.install_executor()`）。主干侧的内联自检块随冲突标记一并删除（其逻辑即 `run_preflight()` 提取前的原文，语义由 `run_preflight` 承接）。
- 其余已暂存文件（`启动漫剧制作助手.pyw`、`infra/app_logging.py`、`infra/diagnostic_capture.py`、`ui/ui_status_bus.py`、三个测试文件、`tasks_round_4539_result.md`、`evidence/R4539.json`）保持调度合并结果原样，未改一字。

## 解开后的 launch() 片段

```python
    if selfcheck:
        degraded_items, safe_start = run_preflight(Path(__file__).resolve().parent)
    # L5 组合根：把 L4 的 SKILL 工具适配器注入 L3；编排器本身不反向依赖 UI。
    import ui.skill_tools as skill_tools
    skill_tools.install_executor()
    from desktop import Desktop
```

## 未验证项与卡外发现

- 未验证项：本文件提交前未单跑测试；`--tests` 定向、卡面两条验收命令与 `git status` 终态在提交步骤核查，实际结果以会话完成报告为准。
- 卡外发现：无。
