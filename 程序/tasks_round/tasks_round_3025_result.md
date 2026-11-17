# R3025 结果（性能/资源轮：首帧收敛信号 `_first_paint_settled`＋周期工作避让——C3 实施④）
<!-- round-evidence: {"commit_base": "222326c3", "credential_hits": 0, "evidence_sha256": "11c04acaffae03f0", "exit": 0, "failed": 0, "passed": 677, "round": 3025, "tests": "run_selftests.py -k pet_ui page_paint layout sidebar"} -->

## 三问
1. 轮次类型：性能/资源轮（runbook §15.3.7）——周期工作在首帧收敛前空转/跳帧，不改可见契约。
2. 测试：`run_selftests.py -k pet_ui page_paint layout resize sidebar desktop_compact` 11 文件 680 条全绿（rebase 前口径）；rebase 后净改动复验见下。
3. 债务：C3 争用削减第二步落地——首帧窗内 pet 全帧重绘与侧栏补排不再做功。

## 改动（rebase 到 R3042 后的净额）
- `desktop_layout.py`：`LayoutMixin` 类属性 `_first_paint_settled=False` 作缺省（唯一写者是 `thaw_page_paint`，shared-state 棘轮合规）；`thaw_page_paint()` 首次调用置实例属性 True（每次布局收敛都经过，只置一次）；`schedule_sidebar_fit` 的 after_idle 回调在未收敛时空转重排（布局轮内 `align_header` 已在做同一件事），收敛后自然恢复 `fit_sidebar()`。
- `pet_ui_view.py`：`PetViewMixin.step` 在未收敛时跳过 `draw()` 全帧重绘但照常 `_schedule` 续排——动画节拍不丢，收敛后自动恢复画面；`desktop` 缺属性按已收敛处理。

## 过程说明（重要）
- 本分支原含 cell_row_menu 拆分与四项 master 存量棘轮修复；期间另一车道 R3033/R3042 已在 master 完成等价修复（cell_menu.py／CellImagesZoomMixin／PetClickCancelMixin／ui_tooltip 参数），故 rebase 时放弃重复改动、只保留本轮独有的 `_first_paint_settled`。
- `程序/skills/00全流程SKILL/AIGC创作全流程` 是无 .gitmodules 的 gitlink，工作树未检出导致技能依赖用例不可跑；已从主检出复制内容补齐（不入 git），合并 CI 在 master 检出不受影响。

## 验证（工作树版诊断_启动回调普查_wt.py，真实项目副本）
- 布局轮次累计：R3018 后 11 → 本轮 8–10（含机器负载差异）。
- 首帧窗内 `PetViewMixin.step` 不再执行 `draw()`（snapshot+schedule 空转，微秒级）；`schedule_sidebar_fit` 回调同理由「fit_sidebar+align_header」降为「空转重排」。
- `TrayIcon._drain`（120ms 轮询）与 `asset_thumbs` 泵（~100ms，仅 `_PENDING` 非空时干活）评估后不改：前者本就近零成本，后者承载真实缩略图投递、延迟收益不确定。

## 遗留（C3 收尾候选）
- `.lambda`×~420/10s 主体为 asset_thumbs 结果泵（有真实 pending 时工作，非空转）——暂不动。
- `.check`×~10 为 DeferredFill 稳定 tick，机制本身即为等布局稳定设计。
- 剩余外部 fit_content 触发（scroll-restore、show() 收尾）属必要收敛。
- C2 内存漂移、C6 忙时降级决策、C7 页缓存扩围：维持冻结/待证。
