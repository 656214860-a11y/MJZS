# R697 修复轮结果：剧本准备页首帧分片与交互门禁

## 结论

完成。01「剧本准备」将非核心工作移出 `show_loaded_project`：聊天模型键后台解析、聊天气泡空闲分片、下载状态与文件表低优先级补建；阶段设置按钮保持在发送按钮右侧并使用轻量入口。创意历史的只读发现改走独立结果队列，**不再占用全局 `worker` 门禁**，修复“当前操作尚未结束，请稍后”的首帧误拦截。

页面代次与销毁边界均有守卫/撤销：延后下载状态、文件表和聊天批次不会在旧页或已销毁控件上提交。

## 真实项目验收

探针对象：`D:\漫剧下载\项目\摄像头_20260930`；原始输出见 `维护记录/r697_startup_probe.log`，临时 `logs/r697_startup_probe.py` 已删除。

| 指标 | R687 | R697 |
|---|---:|---:|
| `show_loaded_project` 单次回调 | 2.89 s（现场诊断） | 0.322 s |
| 首次事件循环（含 Tk paint） | 3.614 s | 1.220 s |
| 首帧全局 `worker` | — | `False` |

回调小于 1.0 s，首帧全窗小于 2.6 s；轻量阶段入口保持“设置—中断”既有顺序。专用自动化探针同样固化了真实项目回调 `<= 1.0 s`。

## 验证

- `python smoke_test.py`：8/8 通过（`维护记录/r697_smoke_final.log`）。
- `python -m unittest tests.test_idea_chat tests.test_desktop_startup_perf`：72 条通过（`维护记录/r697_idea_startup_rerun.log`）；其中包含首帧历史发现不占用 `worker` 的回归断言。
- `python run_selftests.py --layer gui-short --safe --all`：1,072 条，418.7 s；本轮相关 `test_idea_chat` 已绿。仍有 4 个既存红模块：`test_asset_gating`、`test_manual_plan`、`test_skills`、`test_stage_wiring`，详见 `维护记录/r697_gui_short_safe_final.log`；均不属于本轮可改边界。
- `python smoke_test.py --affected desktop pet_ui responsive_ui`：desktop 专项通过；`pet_ui` 的气泡尺寸/取景框既存断言红使门禁以 1 失败结束（108 s），见 `维护记录/r697_smoke_affected_final.log`。本轮未改 pet 模块，且日志中的 `place_window` 销毁提示来自该模块。

## 三个基线数

- gui：1,625 条 / 244 单元
- gui-short：1,072 条 / 155 单元
- service：1,483 条 / 241 单元
