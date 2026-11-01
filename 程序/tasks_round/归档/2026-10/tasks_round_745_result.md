# R745 结果｜修复轮：UI 异常反馈首批

## 结论

已修复已复现的关窗后 Tcl 回调残留：`pet_cloud._place_window()` 的重试和 `Pet.show_main()` 的空闲置顶回调曾在窗口销毁后仍由 Tcl 调度，表现为 `invalid command name ...retry`／`...<lambda>`，并污染启动与交互日志。回调现由对象持有，并在关闭路径取消。

本轮同时将已命中的 UI 容错改为可观察语义：SKILL 面板生产模型读取失败会显示在按钮文案；资产续跑记录清理失败会写入页面状态；非生命周期错误不再被当作 Tk 销毁竞争静默吞掉。

## 回归

- 新增云朵关闭时取消定位重试的回归。
- 新增 SKILL 面板生产模型读取失败必须可见的回归。
- 新增桌面资产续跑清理失败必须写明状态的回归。
- `tests/test_pet_ui.py` 的坏 sink 回归保留页面存活，同时记录失败原因。

## 验证

- `smoke_test.py`：8/8 通过。
- `smoke_test.py --affected desktop pet_ui skill_panel`：通过。
- `run_selftests.py -k desktop pet_ui skill_panel gui_edges --safe`：93 工作单元，0 红。
- `smoke_test.py --architecture`：通过；同时补齐 AGENTS 架构门禁清单中的既存 `test_coverage_audit_ratchet.py` 漏登。
- `run_selftests.py --all --safe`：602 工作单元，0 红，854.715 秒。R745−R741=4，且触及 Tk 生命周期，故执行完整安全全量并将 `last_full_safe_all_round` 写为 745。

## 后续

本轮只处理 UI 反馈链首批已定位项；`pet_cloud.py` 的其余网络／解析容错、`cell_hover.py` 与异常台账其余历史条目仍按缺陷台账逐项分类整改，不将它们误记为已关闭。
