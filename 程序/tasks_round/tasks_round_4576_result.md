# R4576 主分支全量回归与启动耗时排查
<!-- round-evidence: {"commit_base": "a8d6be6db", "credential_hits": 0, "evidence_sha256": "6cf62d5f41d08a13", "exit": 0, "failed": 0, "passed": 347, "round": 4576, "tests": "run_selftests.py -k test_agent_skill_sync test_asset_gating test_project_rename_reconcile test_video_ui test_files_panel_stages test_model_routes"} -->

- 修复轮。对照主分支 a8d6be6db 的全量自检及上一轮 bfda0f976 的失败清单。
- 修正后的首批 117 条和菜单、操作目标与授权相关的 57 条定向用例通过，另有 38 条技能同步、分发和音轨范围用例通过。最后九条针对失败路径的验证均通过。
- 修复资产右键菜单的操作对象判断。恢复对真实发送、刷新、删除、复制、保存与入账入口的覆盖，包括取消重做及只删目标图片。

## 启动耗时

合并时的趋势告警读取共享历史。11 月 27 日 01:03–01:04 的三个样本均来自合并前的 bfda0f976。空项目、首日和同日恢复分别为 1.092、0.924 和 1.356 秒，超过各自之前五次中位数的 1.25 倍。

启动采样观察到后台技能同步反复读取元数据。清理失效技能时现在先排除刚处理过的目录，并跳过没有标记文件的目录。模型选择器一次刷新复用同一份模型池供选项、分组与能力检查使用。性能阈值保持原值。带分析器的运行用于定位调用，不能作为启动时间的对照样本。

## 主分支修复前的完整结果

817 个测试文件，11,124 条用例，3 条跳过，22 个失败工作单元，涉及 20 个不同文件。上一轮 18 个失败工作单元来自 17 个文件。

- 仍失败（14）为 test_asset_gating、test_audio_subtitle_scope、test_distribution_selfcheck、test_final_page_loading、test_final_viewer、test_manual_gate、test_project_open、test_project_rename_reconcile、test_row_targets、test_stage_command_contract、test_stage_wiring、test_ui_edges_autopilot、test_ui_edges_controls、test_video_ui。
- 本轮通过（3）为 test_client_profiles、test_perf_baseline、test_stdlib_closure。
- 本轮新增失败（6）为 test_account_entry、test_desktop_compact_layout、test_files_panel_stages、test_model_routes、test_pet_ui、test_popup_no_interrupt。

修复后切换项目会清掉收起面板里的旧行；同项目刷新保留原显示直到新结果就绪。验证覆盖缺索引时后台发现文件、手动拖宽后的筛选条布局和迟到结果丢弃。三虎切档现在检查一次模式播报，视频工作台通过真实右键菜单清空日志。

在相同解释器与主机上交错启用三个独立进程分别测量两版。空项目首帧中位数由 1.352 秒降至 0.919 秒，首日由 0.697 秒降至 0.618 秒。同日恢复在原版三轮中两次超过期限；候选版三次均通过，中位 1.585 秒。主机同时运行其他架构检查，不能把计时差全部归因于一个改动。原版全量的三项样本分别是 1.112、1.073、1.287 秒；前两项超过趋势阈值，全部通过绝对启动门禁。
