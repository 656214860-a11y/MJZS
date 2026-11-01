# R2189 Qwen API 设置窗口迁到 qwen_setup_dialog（结构治理轮·执行）

来源：`tasks_round/tasks_round_2178_result.md` J 节 **J2**。日期：2026-11-01。
基线：`codex/wip-R2184` @ 37133965（R2184，J1）。零行为变更。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：`--affected qwen workflow api` 全过（冒烟 9 项 0 失败）；架构门禁 412 项，只剩 2 条与本轮无关的既有红（见「测试」）；覆盖率基线同步（332→333 个模块）。债务：`--all --safe` 欠账 +1，本分支未跑全量；本轮改了层级登记表，合入 master 前须跑全量。

## 改动

1. 新模块 `qwen_setup_dialog.py`（L4，82 个可执行行）：`show(parent, on_saved)` 函数体原样迁入，连同它用到的 Tk／UI 名称、`api_models` 记录函数、`agent.core.save`、`tk_timers`、`threading`、`json`；设置路径、`load`、`validate`、`save_key`、`unified_key` 经 `qwen_setup` 导入。
2. `qwen_setup.py` 174→91 行：删去 `show` 与全部 Tk／UI／线程／计时器导入，只留连接设置的读取、校验与密钥读写（`settings_path`、`load`、`validate`、`save_key`、`unified_key`、`api_credential`、`child_environment`、`environment`）。导入本模块不再加载 tkinter。
3. `workflow_settings_dialog.py` 的「自定义 API（Qwen）」按钮改调 `qwen_setup_dialog.show`（J1 里留的那一处）。`previs_automation`、`qwen_adapter`、`workflow_settings` 只用 `environment`／`load`，不用改。

## 登记

- `tests/architecture/_layers.py` 把 `qwen_setup_dialog` 登记为 L4。`qwen_setup` 本轮仍登记在 L4，按真实依赖重新登记留给 J3。
- 边界测试的登记文件名跟随迁移，断言未动：`test_button_boundary`、`test_card_boundary`、`test_dialog_boundary`（仍断言 `show` 里用 `FormDialog`、无裸 `Toplevel`）、`test_notification_boundary`（0 处）、`test_text_component_boundary`。
- `test_migrated_ui_boundaries.TK_FREE_ON_IMPORT` 加入 `qwen_setup`。
- 动态导入：`workflow_settings_dialog` 对 `qwen_setup_dialog` 的常量字符串 `__import__` 不在覆盖率审计 24 的命中范围内，台账无新增；`qwen_setup.py` 的 `load:json.loads` 与审计 24 的 `retired` 登记随文件保留。
- 覆盖率基线：重跑 `scripts/coverage_report.py`（原 8 组定向用例，全通过）刷新为 333 个模块、50 个有行覆盖；只有 `qwen_setup.py` 141→62 行、新增 `qwen_setup_dialog.py` 82 行变化。`runbook.md` §11 同步为 333／283。
- `architecture.md`：分层表 L4 行加 `qwen_setup_dialog` 及职责说明。

## 新增测试

- 无新文件。已有 `test_split_settings_modules_load_without_tk` 加入 `qwen_setup` 即覆盖导入后 `sys.modules` 不含 tkinter：改前（HEAD 的 `qwen_setup`）输出 True，改后输出 False。

## 测试

- `smoke_test.py --affected qwen workflow api`：通过（9 项 0 失败）。
- `smoke_test.py --architecture`（经 `工作流任务\gui_hidden.py`）：412 项，剩 2 条红，与 R2184 相同且与本轮无关：`test_round_baselines.test_round_number_continuous`（状态页只在 master 更新，分支上必红）；`test_agents_md.test_performance_history_is_declared_as_historical_only`（`维护记录/基准历史.json` 被 `.gitignore` 排除，工作树里没有）。
- 临时核对（脚本不入库，密钥与设置路径全部打桩）：隐藏 Tk 根上打开迁出后的窗口，缺 API Key 时保存被拒且窗口保留、不写文件；填入后保存写出 `model=qwen-adhoc` 且 json 里无 `api_key`、`save_key` 只收到一次、`on_saved` 回调一次、窗口关闭；再开窗点「删除模型」回调第二次。输出 `OK model=qwen-adhoc keys=1 calls=['saved', 'saved']`。
- 未运行：`--all --safe` 全量；真实界面目测；「测试连接」真实联网。

## 回滚

`git revert <本轮提交>`。不涉及用户数据与配置格式。

## 下一步

J3：按真实依赖重新登记 `workflow_settings`、`qwen_setup` 等层级，层级台账 35→21，`KNOWN_DYNAMIC_UPWARD` 5→3；合入 master 前跑全量。
