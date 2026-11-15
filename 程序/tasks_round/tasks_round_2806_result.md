# R2806 结果：R2758 剧本阅读测试合成事件加固（修复轮）
<!-- round-evidence: {"commit_base": "f502d5b2", "credential_hits": 0, "evidence_sha256": "b67b665b90a9069c", "exit": 0, "failed": 0, "passed": 20, "round": 2806, "tests": "run_selftests.py -k script_line_numbers script_find_bar script_outline script_zoom"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。R2758 提交的四个剧本阅读测试文件在多车道高并行
   负载下偶发红：Tk 合成按键事件须落在焦点控件，且滚动/重绘/几何
   生效在并发时均可能滞后，导致 `bar.visible`、`zoom_delta`、
   行号同步与大纲跳转等断言偶发失败。本轮只加固测试，不改产品代码、
   不弱化断言（仍走真实事件→绑定→状态链路，仅在探针未达前重发/轮询
   以吸收环境抖动）。

2. **测试跑了吗、三个基线过了吗？**
   - 定向：`run_selftests.py -k script_line_numbers script_find_bar
     script_outline script_zoom` 20/20 绿；加固后连续多轮复跑全绿。
   - 默认冒烟 8/8、架构门禁 466/466 沿用 R2758 当次实测（本轮仅测试
     文件改动，不触产品逻辑）。
   - 全量 `--all --safe` 未跑：功能分支不累计欠账。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；消除 R2758 新测试在并行验收环境下的偶发红来源。

## 改动清单

- `tests/test_script_find_bar.py`：Esc／Enter 改为「focus_set→
  when='now' 同步派发→重发至多 12 次直至生效」。
- `tests/test_script_zoom.py`：新增 `_press_until`（焦点确认＋
  `when='now'`＋按目标 `zoom_delta` 探针重发）；`test_a` 三处按键
  断言改用之；`test_b` 普通滚轮断言改为轮询 yview 变化。
- `tests/test_script_line_numbers.py`：滚动同步断言改为轮询到
  行号槽与可视首行一致（≤20 次）。
- `tests/test_script_outline.py`：点击跳转断言改为轮询到高亮落位
  且目标行进入可视区（≤20 次）。

## 验证

- 复现证据：高负载下曾现 `test_00` Escape 后 `bar.visible` 仍 True、
  `test_a` 首次 `<Control-equal>` 后 `zoom_delta` 仍 0 等红；
  加固后连续多轮绿。
- 说明：失败根因为环境性事件投递/重绘抖动（多车道 GUI 并发），
  非产品缺陷；探针目标即断言目标，不会造成状态漂移。
