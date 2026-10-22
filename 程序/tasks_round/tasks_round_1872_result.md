# R1872 结果：测试瘦身第 2 批 c（整理轮）

- 本轮类型：整理轮。只改测试，产品代码一行没动。
- 依据与做法同 R1869／R1870：先把差分测试独占的产品行补成普通行为测试，用 `Temp/audit/verify.py`（不进仓库）确认这些行被替代测试跑到，再删差分测试。下表 5 个文件都是 0 行漏掉。

| 删掉的差分测试 | 独占行 | 替代测试（新增或扩充） |
|---|---|---|
| test_keyframe_comfy_window_equivalence | 7 | `tests/test_keyframe_comfy.py` 的 `DialogTests` 加 1 条：本地模型名没填时“保存设置”拒绝且配置文件不变；全部取消勾选后“开始逐镜生成”“检查参考资产”“预估费用”都报“请至少勾选一个” |
| test_open_manager_equivalence | 7 | `tests/test_ui_batch7_settings_models.py` 加 `ManagerHintTests`：没选行点“删除这条”、没填模型 ID 点“测试连接”只写提示；填了 ID 才去测（`probe_line` 打桩，不联网） |
| test_cloud_settings_window_equivalence | 8 | `tests/test_cloud_video.py` 加 `StaleSettingsWindowTests`：设置窗打开后项目切换或宿主正忙，“删除模型”“保存设置”都只报错，不写任何文件 |
| test_pet_save_settings_equivalence | 8 | `tests/test_pet_agent.py` 加 `SaveSettingsTests`：坏的 dnd／retry_delays／max_attempts 本次不写、盘上旧值保留；未登记的配额类型与非正数丢掉；未登记的键和 None 不碰 |
| test_script_documents_equivalence | 8 | `tests/test_script_workspace_service.py` 加 1 条：三种已发布批次布局都列出；同名目录、越界目录或文件、读不出文本的剧本都不抛错 |

- skip 台账：删去 `test_open_manager_equivalence`、`test_cloud_settings_window_equivalence`、`test_keyframe_comfy_window_equivalence` 各 1 条登记；新用例 `DialogTests.test_buttons_refuse_empty_selection_and_unnamed_models`、`StaleSettingsWindowTests.setUp` 带 `PLATFORM_TKINTER` 跳过位，各补登 1 条（skip 卫生门禁要求台账与源码双向相等）。
- 断言未动：现有用例的断言一条没改，只新增用例。
- 轮次号：本轮领到 1872，1871 已被其他会话领走。
- 验证：替代测试在隐藏桌面实测通过：test_keyframe_comfy 15/15、test_ui_batch7_settings_models 14/14、test_cloud_video 18/18、test_pet_agent 79/79、test_script_workspace_service 22/22。冒烟通过。架构门禁 394 条：补登 skip 台账后只红 `test_round_baselines.test_round_number_continuous`（1860 != 1873），原因同 R1870：`project_status.md` 按约定只在 master 上改，合入时补齐。全量放在 17 个都做完之后统一跑。
- 剩余：A2 档还有 7 个：tick_async_result、send_message、app_tick、run_background、open_flow_agent、asset_batch_window，以及 `test_script_structure_page_equivalence`。
