# R2218 结果：模型管理列表只留 Provider 列头排序、调用方式挪到第 2 列、表单成对并行并缩短（功能轮）

## 三问
- 轮次类型：功能轮（§3.1）。用户看着模型管理截图提出三点：删掉 Provider 以外的列头排序；调用方式左移到第 2 列；表单里调用方式／Provider、模型 ID／显示名、上下文长度／备注各并一行，下拉框和输入框缩短。模型管理不属于制作阶段，没有对应的 docs REQ／DES。
- 测试和基线：在 worktree 分支上运行，都经 `工作流任务/gui_hidden.py`。
  - `run_selftests.py -k pet_settings model_manager_actions model_delete_stays ui_batch7 button_consistency pet_ui`（最终代码）：699 条，0 个文件有红。
  - 默认冒烟：8 项通过。
  - `smoke_test.py --architecture`：411 项里 3 条红，都不是本轮引入。`test_script_stages_name_only_their_approved_00_references`、`test_performance_history_is_declared_as_historical_only` 在 worktree 上缺技能子模块和 `维护记录/基准历史.json` 时红；`test_round_number_continuous` 当时 worktree 状态页落后于 master（2199≠2206）。这 3 条没有在主检出重跑确认，由合并轮在主检出复跑。模块行数上限一条在本轮里先红后绿：`pet_models_ui.py` 一度 1006 行＞上限 1000，压到 998 行，没有抬高上限。
  - 全量 `--all --safe` 本轮未手动运行。
  - 真机未手动核对，没有截图。
- 轮次号：领号放在提交前一刻。
- `project_status.md` 欠账：没有减少，也没有新增；本分支不写状态页，由合并轮登记。

## 改动
- `pet_models_ui.py`：
  - 列顺序改为 Provider／调用方式／模型 ID／显示名／能力标签／状态。
  - `DataTable` 默认给每个列头挂「按显示文本排序」；这里把除 Provider 外的列头命令清空。Provider 列头改为 `flip_provider_order`：翻转分组顺序并重载列表，组内仍按显示名、模型 ID 排（不用显示文本排序，因为同组后面的行 Provider 格是空的，按显示文本排会打乱分组）。
  - 表单改为四列网格：调用方式｜Provider、模型 ID｜显示名、上下文长度｜备注各占一行；API 根地址、密钥名、直接输入密钥、协议、能力标签横跨整行。下拉框和输入框按字符数定宽（`FORM_COMBO_WIDTH`、`FORM_ID_WIDTH`、`FORM_SHORT_WIDTH`），不再随窗口拉长。
  - 因行号变了，API 专属行集合改为 `{2, 3, 4, 5}`，Desktop／CLI 的「应用安装路径」行放在 API 根地址同一行（行 2），显隐切换逻辑未动。
  - `text_row` 增加 `column`、`width`、`span` 参数，默认值与原行为一致。
- 新增测试（`tests/test_pet_settings.py`）：
  - `test_only_the_provider_heading_sorts_and_it_flips_the_group_order`：只有 provider 列头有命令；点一下 Provider 分组倒序，再点翻回。
  - `test_the_form_pairs_fields_on_one_row_with_short_boxes`：三对字段同行，控件请求宽度小于表单一半。
- 随契约变更改动的旧测试，原有断言未弱化、断言未动：
  - `tests/test_pet_settings.py` 两条按列取值的测试：列下标跟着新列顺序走（显示名由第 2 列改第 3 列，调用方式由第 3 列改第 1 列），表头期望值同步。
  - `tests/test_ui_batch7_settings_models.py::test_manager_inputs_share_one_left_edge`：Provider 和显示名搬到右半边，原来「全部输入同一竖线」改为左半边（调用方式、模型 ID、根地址、密钥名）同一竖线，另加右半边（Provider、显示名）同一竖线的断言。

## 用户需做
重启应用后生效。
