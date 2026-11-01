# R2174 结果：模型列表加「调用方式」列并精简（功能轮）

## 三问
- 轮次类型：功能轮（§3.1）。用户反馈模型管理的模型列表「不够简洁清晰可读，缺少一列调用方式」。模型管理不属于制作阶段，没有对应的 docs REQ／DES；README「新增一个模型」那张表讲的是表单字段，不涉及列表，未改。
- 测试和基线：在 worktree 分支 `claude/model-deletion-issue-6e8e80` 上运行（经 gui_hidden）。
  - `-m unittest tests.test_pet_settings tests.test_model_manager_actions tests.test_ui_batch7_settings_models tests.test_pet_ui.ModelPoolTests tests.test_model_delete_stays_deleted tests.test_button_consistency tests.test_client_profiles tests.test_model_probe_layers`（最终代码）：159 条全过。
  - `smoke_test.py --affected pet_models_ui`（最终代码）：未通过。8 项检查通过；定向 selftest（test_pet_settings、test_pet_ui、test_model_manager_actions、test_model_probe_layers、test_client_profiles、test_ui_batch7_settings_models、test_skills）只红 test_skills 那 2 条，与 R2166 相同，属环境问题：worktree 没初始化子模块 `程序/skills/00全流程SKILL/AIGC创作全流程`（目录为空，主检出有 18 项），SKILL 注册数 71≠73。
  - 截图核对：在临时程序目录和临时项目里打开模型管理（1180×860），六列内容全部显示完整。截图脚本放在仓库外，未入库。
  - 默认冒烟、`--architecture` 未单独运行；本轮没有新增 import。全量 `--all --safe` 未手动运行，由提交后钩子在后台补跑。
  - 真机未手动核对。
- `project_status.md` 欠账：没有减少，也没有新增。本分支不写状态页，由合并轮登记。

## 改动
- `pet_models_ui.py`：
  - 列表列改为 Provider／模型 ID／显示名／调用方式／能力标签／状态。「调用方式」取 `model_pool.call_mode`（Desktop／API／CLI），与下面表单的「调用方式」同源。
  - 去掉 API 根地址、协议、密钥名三列。这三项只对 API 行有意义，Desktop／CLI 行一直空着；选中一行后在下面表单里看。
  - 新增 `list_status`：状态一格可用时只写「可用」，不再重复模型 ID（模型 ID 已有自己一列）。三虎模型配置页的状态行仍用 `status_text`，带模型 ID，未改。
  - 去掉表单切换调用方式时列表跟着藏列的 `displaycolumns` 切换，以及只为它存在的 `self.keys`。列表的列不再随表单变化。
  - 列宽按内容重分（能力标签 270、状态 220），五个能力标签和「缺 DASHSCOPE_API_KEY（.env）」都显示得下。

## 测试
- 新增 `tests/test_pet_settings.py::ManagerProviderTests::test_the_list_shows_the_call_mode_and_leaves_api_details_to_the_form`：改动前红（表头仍是 8 列：`['Provider', '模型 ID', '显示名', '能力标签', 'API 根地址', '协议', '密钥名', '状态']`），改动后通过。
- 已有测试断言未动。列顺序保留 Provider／模型 ID／显示名在前，`test_the_manager_groups_gpt_entries_and_sorts_rows_by_label` 读的第 0、2 列不受影响。

## 用户需做
重启应用后生效。
