# R2166 结果：模型管理里删掉的模型又回来了（缺陷轮）

## 三问
- 轮次类型：缺陷轮（§3）。用户报模型管理里 `claude-desktop-app`（状态「缺 API 根地址」）删不掉。
- 测试和三个基线：在 worktree 分支 `claude/model-deletion-issue-6e8e80` 上运行（经 gui_hidden）。
  - `run_selftests.py -k pet_ui model_pool model_delete skills model_manager ui_batch7 stage_config`：867 条，865 条过，2 条红，均为环境问题，与本轮无关：`test_skills.RegistryTests` 里的 SKILL 注册数 71≠73。worktree 没初始化子模块 `程序/skills/00全流程SKILL/AIGC创作全流程`，少了两条 SKILL。
  - `smoke_test.py --affected model_pool skill_panel_support stage_config pet_ui_settings pet_models_ui`：未通过。它的定向 selftest 带上了 test_skills，红的是上面同 2 条。
  - 默认冒烟：通过。
  - `--architecture` 未单独运行。本轮没有新增 import 方向：stage_config 已被 pet_ui_settings 引用，skill_panel_support 已引用 model_pool。
  - 全量 `--all --safe` 未手动运行，由提交后钩子在后台补跑。
  - 真机未手动核对。
- `project_status.md` 欠账：没有减少，也没有新增。本分支不写状态页，由合并轮登记。

## 根因
用户日志（`logs/sanhu_progress.log`）里删除每次都成功了，模型是从两条路被补回来的：
1. 删除后右侧表单仍停在被删的那条。紧接着点「保存并关闭」时，`save_and_close` 发现模型 ID 栏还有字，就调 `save_one` 把它原样存了回去（11-01 10:35:52 删、10:35:54「已保存模型」）。
2. 项目「摄影侠_20260930」的剧本结构阶段还选着 `claude-desktop-app`。删除只把全局预设改回「自动」，项目阶段配置没动。每次打开或切换项目，`skill_panel_support.sync_models` 会把「阶段里选过、池里没有」的模型补成最小记录：显示名等于 ID，没有根地址，所以显示「缺 API 根地址」。补的时候 `upsert` 还清掉了删除记录。10-30 那几次删了又回来、却没有保存记录，就是这条路造成的。

## 改动
- `model_pool.py`：新增 `deleted_ids(data)`。`remove` 对所有模型都记删除记录，以前只记出厂桌面入口；键名沿用 `deleted_desktop_models`，旧配置不用迁移。`upsert`，也就是用户重新保存同一 ID 时，解除任何模型的删除记录。`pool()` 改读 `deleted_ids`，行为不变。
- `skill_panel_support.sync_models`：跳过 `deleted_ids` 里的模型。从没见过的模型照旧补进池（第 59 期第 12 条不变）。
- `stage_config.py`：新增 `project_model_references`／`release_project_model`，比对规则与预设相同（ID／显示名／模型名，不分大小写，池里其他条目还在用的名字不动）。
- `pet_ui_settings.py`：`delete_pool_model` 把当前项目里选了它的阶段改回「自动」，提示语加上「当前项目 N 个阶段的模型已改为「自动」」。项目目录写不进去时不拦删除。新增 `pool_model_stages` 给确认框用，`_current_project` 读桌面当前项目。
- `pet_models_ui.py`：删除确认框列出会改回「自动」的阶段。删除成功后表单清成「新建」，「保存并关闭」就只关窗。

## 测试
- 新增 `tests/test_model_delete_stays_deleted.py`（5 条）。修复前 4 条红：同步把 `claude-desktop-app` 和 API 模型都补回 `['claude-desktop-app'] != []`，以及 `pool_model_stages` 不存在。另 1 条「重新保存解除删除记录」修复前后都通过，作为防回退用例。
- 新增 `tests/test_pet_ui.py::ModelPoolTests::test_save_and_close_right_after_delete_does_not_save_it_back`：修复前红（`'delete-then-close' != ''`），修复后通过。
- 已有测试断言未动。

## 已知边界
- 其他没打开的项目若也选着被删的模型，阶段配置里仍留着这个 ID。删除记录让它不会被补回池里；运行到那个阶段时，选型会报「指定的模型 … 现在用不了（缺 API Key 或没登记）」，需要用户在该阶段改选模型。

## 用户需做
重启应用后生效。现有用户配置里的 `claude-desktop-app` 仍是那条 API 记录：在模型管理里再删一次，就不会再回来，剧本结构阶段也会改回「自动」。
