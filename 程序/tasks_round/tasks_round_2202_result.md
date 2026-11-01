# R2202 Tk 弹窗拆出四个数据模块并按真实依赖重登记（结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 02 的 J5、J6、J7（三项合为一轮，改动互不重叠）。

## 基线
分支 `codex/wip-R2202`，自 R2193。

## 轮次类型／三套基线／债务
结构治理轮；不改行为；`层级` 台账 21→8（清 13 项：J5 5、J6 3、J7 5）；`scope_audit_pending` +1（`asset_reference_prompts` 升为 L2，尚未审计写服务范围，如实记入待审计，不记为已迁移）。

## 改动
- J5：`project_settings.confirm_unattended` → 新 `project_settings_dialog.py`（L4）；该函数生产中无调用方，仅测试夹具替换它。
- J6：`cloud_assets.settings`（Comfy 账户窗口）→ 新 `cloud_assets_dialog.py`；`asset_batch`、`native_assets` 改从对话模块导入。
- J7：`asset_prompt_rules.check` → `asset_prompt_check_dialog.py`（`ui_plugin_registry` 登记名同步替换）；`asset_reference_prompts.show_prompt` → `asset_reference_prompts_dialog.py`；`desktop_asset_pages` 改调。
- 代码为逐字搬移，仅换导入位置。

## 登记
- `project_settings`、`cloud_assets`、`asset_prompt_rules` → L1；`asset_reference_prompts`（懒加载 L2 `storyboard_catalog_service`）→ L2；四个对话模块 → L4。
- 台账、`覆盖率基线.json`（337 模块，50 已覆盖）、runbook §11、architecture.md 同步。
- 边界测试（button／card／dialog）里 `cloud_assets.py` 跟随到 `cloud_assets_dialog.py`；`test_agents_md` 的「第 N 步」白名单加两个新文件；`test_ui_edges` 的导入路径与源码文件名跟随搬移。**断言未动。**

## 新增测试
无新增；既有边界与 `test_ui_edges` 用例覆盖搬移后的入口。

## 测试
- `smoke_test.py --architecture`：仅 2 项环境红（`test_round_number_continuous`、基准历史缺失），非回归。
- `run_selftests.py -k ui_edges`：全部通过（`--affected` 那次的 `BriefTintTests` 一项红为并发令牌争用，单跑通过）。
- 未做：真机目视各弹窗、全量 `--all --safe`（合入 master 前统一跑）。

## 回滚
`git revert` 本轮提交。

## 下一步
J8–J9（候选 05）。
