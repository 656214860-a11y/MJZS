# R2811 结果：修复 ui_usage_detail 静默异常棘轮违例（except Exception: pass → app_logging.swallowed）
<!-- round-evidence: {"commit_base": "2ded4464", "credential_hits": 0, "evidence_sha256": "c729e56b4a9ae071", "exit": 0, "failed": 0, "passed": 47, "round": 2811, "tests": "run_selftests.py -k usage silent_exception"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。R2774 收口轮在 `_export_csv` 状态栏提示处写了
   `except Exception: pass`，触发 `architecture.test_silent_exception_ratchet`
   （后台全量在 R2779 合并树上实测 1 处违例：ui_usage_detail.py:142）。
   定向验证只跑了 `-k usage` 未覆盖架构棘轮，属本轮验证口径欠账。

2. **测试跑了吗、三个基线过了吗？**
   - 定向 `run_selftests.py -k usage silent_exception`：**47 条全绿**
     （棘轮 4/4、test_usage_indicator_ui 8/8、test_usage_snapshot 9/9）。
   - 静态复扫 `silent_exception_sites()`：违例 NONE。
   - 冒烟/全量：未跑（两行留痕修正；合入后由后台自动全量复核）。

3. **`project_status.md` 的欠账少了吗？**
   消除一笔本模块引入的架构棘轮违例；未新增欠账。

## 变更

- `ui_usage_detail.py`：`import app_logging`；`_export_csv` 状态栏
  `status.set` 的兜底 `except Exception: pass` 改为
  `app_logging.swallowed()`（棘轮唯一合规写法）。工作树中该修正已存在
  （他车道先行改好，本轮核验后单独落账，避免与其在制改动混提交）。

## 边界与说明

- 本工作树含多车道在制脏文件（剧本结构编辑等 15 个），本轮只暂存
  `ui_usage_detail.py` 与本结果文件。
- 教训记录：L4 收口改动虽不改契约，凡新增 `except` 仍须跑
  `--architecture` 或至少棘轮定向；后续同类小改默认带
  `-k silent_exception` 复核。
