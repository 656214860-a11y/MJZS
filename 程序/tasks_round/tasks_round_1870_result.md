# R1870 结果：测试瘦身第 2 批 b（整理轮）

- 本轮类型：整理轮。只改测试，产品代码一行没动。
- 依据：`维护记录/测试瘦身审计_20261022.md` 的 A2 档，做法同 R1869：先把差分测试独占的产品行补成普通行为测试，用 `Temp/audit/verify.py`（不进仓库）确认这些行被替代测试跑到，再删差分测试。下表 5 个文件都是 0 行漏掉。

| 删掉的差分测试 | 独占行 | 替代测试（新增或扩充） |
|---|---|---|
| test_frames_ready_equivalence | 1 | `tests/test_stage_parallel.py` 加 `ShotFrameProblemTests`：首帧已找到但校验时读文件出错，报“首帧路径无法读取”且保留“已找到” |
| test_content_box_equivalence | 2 | `tests/test_script_structure_edit.py` 加 1 条：只读文档点“编辑”报错；编辑态没有可恢复的删除时“恢复”报错而不是抛 TclError |
| test_pet_click_equivalence | 2 | `tests/test_pet_ui.py` 的 `SnoozeTests` 加 1 条：点“稍后再说”进入安静期，提示写明安静几分钟 |
| test_writing_page_equivalence | 2 | `tests/test_writing_page_controller.py` 加 `CancelScriptLoadTests`：窗口已销毁时撤销批次，after_cancel 抛 TclError 也清掉待办任务 |
| test_preparation_step_equivalence | 3 | `tests/test_writing_api_output_budget.py` 加 1 条：发送中途异常时释放预算台账的预占并原样抛出 |

- skip 台账：删去 `test_content_box_equivalence`、`test_writing_page_equivalence` 各 1 条登记。
- 断言未动：现有用例的断言一条没改。`test_script_structure_edit._setup` 加了 `editable` 参数（默认 True），只给新用例用。
- 验证：替代测试在隐藏桌面实测通过：test_stage_parallel 54/54、test_script_structure_edit 7/7、test_pet_ui 600/600、test_writing_page_controller 3/3、test_writing_api_output_budget 8/8。冒烟通过。架构门禁 394 条红 1 条：`test_round_baselines.test_round_number_continuous`（1860 != 1871），原因是 `project_status.md` 按约定只在 master 上改、本分支未同步轮次头，合入 master 时补齐即转绿，与本轮改动无关。全量放在 17 个都做完之后统一跑。
- 剩余：A2 档还有 12 个（含 `test_script_structure_page_equivalence`）。
