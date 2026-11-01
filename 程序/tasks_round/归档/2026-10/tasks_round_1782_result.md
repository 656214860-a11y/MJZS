# R1782：重复代码合并——6 组中合并 5 组，另有排序键惰性求值（整理轮）

1. 本轮类型：§3.3 整理轮（不改行为的结构整理）。来源：审计第 26、35 项。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k file_cache seedream model_secrets cloud_assets workflow_engines stage_slot process_slot parallel space_toggle project_sort_key storyboard asset_page media_pages desktop_project checkbox row_targets unification_ratchet line_endings architecture`：601 条，1 个文件有红（见「未通过项」，非本批引入）。
   - 默认冒烟通过。
   - DPAPI 实机往返：`seedream_api.protect` 加密→解密得回原文，解密垃圾数据抛出带自定义 label 的中文错误，行为与合并前一致。
   - 完整安全全量：合入 master 后由 `scripts/auto_full_safe.py --run` 补跑，未跑前不写通过。

3. project_status.md 欠账少了吗：本轮改源码 +8；全量欠账由合入后补跑清账。

## 合并的重复（审计第 35 项，共 6 组，合并 5 组）

| 组 | 做法 |
|---|---|
| `workflow_engines.reserve_/request_stage_process_slot` 同一段阶段名解析 | 抽 `_stage_slot_arguments(stage)` |
| `file_cache.read_json/read_text/read_bytes` 同一段签名缓存逻辑 | 抽 `_read_through(cache, key, path, parse)`；`json.loads` 不再在 `read_json` 里直调，`架构统一基数.json` 里对应的 `file_cache.py:read_json:json.loads` 豁免项随之删除（债务下降） |
| `desktop_asset_pages` 与 `desktop_storyboard_page` 的 `toggle_focus_check` | 抽 `responsive_ui.bind_space_toggle(tree, toggle)`，与 `bind_row_toggle` 并列；新增 `tests/test_space_toggle.py`（不起 Tk，3 条） |
| `desktop_media_pages` 后期与交付页顶栏 | 抽 `MediaPagesMixin.stage_action_bar(stage, manual_text)` |
| `model_secrets.protect` 与 `seedream_api.protect` | 实现只留 `model_secrets.protect`；`seedream_api.protect` 保留默认标签「火山 API Key」转发，`cloud_assets` 等调用方不变；删除 `seedream_api` 里不再使用的 `import ctypes` |
| `edit_service.automatic_assemble_decision` 与 `handoff_service.automatic_decision`（9 行纯函数） | **未合并**：共享必须新增顶层模块，要同步登记层级表、覆盖率基线、架构清单等 4 处台账，得不偿失；两处属于不同业务的自动流程，保留。已记入 `BLOCKED_ISSUES.md` |

## 其他

- `desktop_project_pages.fill_projects`：排序键原写法 `item.get('created_at', Path(...).stat().st_ctime ...)`，`dict.get` 的默认值会被提前求值，导致每个项目每次刷新都读一次磁盘。改为 `project_sort_key(item)`：登记了 `created_at` 就不碰磁盘。`tests/test_project_sort_key.py`（2 条）。

## 未通过项

- `architecture.test_round_baselines.test_round_number_continuous`：状态页轮次头是 1776，最新结果文件已是 R1782，要求头＝最新结果＋1。`project_status.md` 只允许 master 提交（规则 41），合入 master 后单独补一次；分支上此项预期为红，非本批引入。

## 提交

- 已在分支 `claude/project-handoff-f6eb50` 提交，commit hash 见 git log `R1782:`。
