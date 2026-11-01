# R947 全量反馈：删除模态不再阻塞

R946 全量安全回归结束：3778 项，424.1 秒，1 项失败。资产删除确认不再阻塞；未达到 C4 的两轮零失败且不超过 420 秒门槛，C4 保持未完成。

唯一失败：tests/test_asset_gating.py 的 test_progressbar_directly_above_action_buttons 期待旧 Label 类名，实际 native_assets.py 已使用 ProgressLabel（继承 ttk.Label）。将预期更新到明确的新组件名，保留顺序和按钮内容断言；不修改生产行为。

截图阻塞修复已提交于 3ec4c7b。正常用户应用与项目数据未被关闭或修改。

验证：资产测试模块 18/18，通过实际删除与恢复路径；默认冒烟 8/8。不得将本报告作为全量绿色凭据。测试销毁时仍有 Tcl after 回调警告，未导致断言失败，需与性能问题分别追踪。
