# R3018 结果（性能/资源轮：首帧布局收敛减负——C3 实施③）
<!-- round-evidence: {"commit_base": "a565d4ee", "credential_hits": 0, "evidence_sha256": "c12e5b8d7103fcb3", "exit": 0, "failed": 0, "passed": 104, "round": 3018, "tests": "run_selftests.py -k page_paint layout resize script_composer writing_page column_fit root_layout compact_layout"} -->

## 三问
1. 轮次类型：性能/资源轮（runbook §15.3.7）——只减重复布局工作，不改页面契约。
2. 测试：`run_selftests.py -k page_paint layout resize script_composer writing_page column_fit root_layout compact_layout` 13 文件 104 条全绿；`smoke_test.py` 8/8。
3. 债务：C3 从「定性」进入「实施」——首帧窗内整页布局轮次实测 16→11（-31%）。

## 诊断证据（工作树版诊断_首帧fit调用源_wt.py，真实项目副本）
- 改前：18 次 _apply_layout = 12 内部重排（fit_again×6 + stability×6）+ 外部触发；fit_talk_container 无条件 fit_content 5 次。
- 改后：13 次 _apply_layout = 4 稳定性重排 + 外部触发；fit_talk_container 触发降至 2 次（req 尺寸未变时跳过）。
- 注意：诊断脚本硬编码主检出路径，测工作树须用 _wt 副本（已留在 工作流任务/）。

## 改动
- `desktop_layout.py`：
  - `_fit_again` 不再无条件补排——pending 期间到达的重复 fit_content 在本轮 `_fit_content_now` 已按最新几何算完，签名未变时重排结果必然相同；改记 `layout.fit_again.suppressed` 计数，真实变化仍由签名稳定性检查兜底（8 轮上限不变）。
  - 稳定性收敛判据由全量控件请求签名（measured_requests）改为画布结果三元组 `(width, req, target)`：控件级分布变化但总高不变时画布配置一致，补排属纯浪费。
  - 新增 `layout.repass.stability`/`layout.repass.fit_again`→`layout.fit_again.suppressed` 计数器（telemetry）。
- `desktop_writing_page.py`：`fit_talk_container` 尾部无条件 `page.fit_content()` 改为仅当 `content` 请求尺寸（reqwidth/reqheight）真实变化时触发——talk 的 Configure 在建页/DeferredFill 期密集触发，是首帧窗内外部 fit_content 的主要来源之一。

## 验证
- 诊断实测：布局轮次 16→11；fit_content 外部调用仍由 scroll-restore、show()、resize 等必要路径触发。
- 104 条布局/页面相关测试全绿（含 test_window_resize_coalescing、test_script_composer、test_page_paint_*）。
- `_fit_again` 语义变化：不再产生「无条件第二眼」，但签名变化路径完整保留；scroll-restore 有独立 pending 机制不受影响。

## 遗留（C3 后续）
- 剩余 ~7 次外部触发周期（scroll-restore refit、show() 收尾 fit_content、Configure 驱动）属必要收敛，继续压需更精细证据。
- 启动窗口其余争用源（pet 动画 step×75、TrayIcon._drain×79、DeferredFill tick）尚未延迟——下轮候选：首绘收敛后再放行 pet/tray 周期回调。
- C2/C6/C7 维持冻结/待证状态。
