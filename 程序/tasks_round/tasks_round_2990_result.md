# R2990 结果：page.paint 首帧指标分解（布局等待 polls＋窗内布局轮次）
<!-- round-evidence: {"commit_base": "60e76dfe", "credential_hits": 0, "evidence_sha256": "9be07b29ea164b2b", "exit": 0, "failed": 0, "passed": 306, "round": 2990, "tests": "run_selftests.py -k boundary coverage static_hygiene"} -->

**类型**：性能/资源轮（度量增强，不改产品行为）。
**测试**：跑了——`test_page_paint_metric` 8 条、`test_page_paint_freeze` 9 条、`test_app_logging` 13 条全绿（含新增计数器断言）；默认冒烟 8/8；四个改动文件 py_compile 通过。跨树 GUI 令牌被另一工作树全量串行回归（PID 39528，dsh-1be9aed2 车道）占用，`run_selftests -k` 排队超时后改由直接 `python tests/<file>.py` 验证同三文件。
**基线**：冒烟 8/8；未跑 `--architecture`（无分层/契约结构变更，app_logging/desktop_layout 均为既有模块内修改）；全量回归未跑（分支不累计欠账，合入前按风险触发判定——纯遥测改动，风险低）。
**欠账**：无新增；C3 剧本页首帧根因修复待本轮埋点在真实使用中取证后立项；C2 内存漂移、C6 降级约定维持原状。

## 本轮做了什么

1. **C3 定性推进（证据）**：剧本页 `page.paint.script` 真实日志超阈 148 次（均值 2307ms）。本地复现链：
   - 合成项目 fixture 仅 ~330ms → 换真实项目副本（摄影侠_20260930，592 文件）仍 ~330ms；
   - **最大化窗口**后冷启首帧 **1346ms**（超阈），暖开回切 316ms ——窗口尺寸是第一敏感因子；
   - cProfile：`tkapp.call` 占累计 93%（Tk 几何/布局 C 调用），另有 SSL 握手 ~76ms、skill_registry 解析、目录扫描；
   - `fit_content` 机制：`_fit_content_now` 每轮递归遍历全控件树取 req 尺寸作签名，签名变化最多补 8 轮＋`_fit_again` 合并，`page.paint` 度量＝show()→`_fit_pending` 连续稳定，与「用户看到画面」不是同一时刻。
   - 结论：首帧耗时＝建页＋**多轮整页布局收敛**＋收敛期间其他 idle 工作（pet 气泡 +150ms、deferred idea 回填、缩略图 tick）的墙钟叠加。需分解数据确认各占比。
2. **埋点（本轮交付）**：
   - `desktop_layout._apply_layout.run()` 每执行一轮整页布局 `_layout_pass_count+1`；
   - `app_logging.begin_page_paint` 快照基线，`finish()` 记 `page.paint.<页>.fitwaits`（等 `_fit_pending` 的 16ms 轮询数）与 `.fitpasses`（窗内实际布局轮次）入 `perf_metrics.json` counters；
   - 慢操作告警附分解：`慢操作 page.paint.script 2300ms（阈值 1000ms；布局等待≈736ms/46 polls，窗内布局轮次 12）`——paint_stats 正则不受影响（明细在括号内）。
   - `paint_stats.py` 新增「首帧分解」段：按页输出会话均值布局等待 ms 与布局轮次。
3. **测试**：`test_page_paint_metric` 新增 `test_page_switch_records_fit_breakdown_counters` 断言两计数器落账；`record_elapsed` 加可选 `detail` 形参（默认空，旧调用兼容，`test_record_elapsed_preserves_existing_shape` 通过）。

## 改动文件

`app_logging.py`、`desktop_layout.py`、`tests/test_page_paint_metric.py`、`tests/architecture/test_static_hygiene.py`、`维护记录/基准脚本/paint_stats.py`。

## 合并阻断修复（同轮附带，三轮 CI 暴露后补齐）

`data/voice_asr_venv/`（离线 ASR 运行时 pip venv，约 7700 个第三方 .py／630MB）被各源码扫描器当成本仓代码扫描。三轮 CI 逐层暴露，最终共修 **18 个文件**：

1. `test_static_hygiene._EXCLUDED_PARTS`＋`_scan.EXCLUDED_PARTS` 加 `"voice_asr_venv"`（无效转义／星号导入／eval-exec 门禁＋全部 `_scan` 消费者）；
2. 九个自带排除集的 boundary 测试（busy_state/button/copy_entry/data_table/dialog/input/shortcut_registry/token/ui_icons）集合加 `"voice_asr_venv"`；
3. 六个内联过滤的 boundary 测试（combobox×2/context_menu/file_dialog/notification/scrollbar_theme/tooltip）条件加 `or 'voice_asr_venv' in relative.parts`；
4. `scripts/coverage_report.py` 排除集合同步（修模块数 6360≠546 基线失配）。

排除语义统一：venv 与 `skills/` 同性质——第三方运行时代码，不属本仓维护、无法提交修复；门禁断言未弱化，只是扫描范围收敛到「本仓自有 .py」。已核对其余 rglob 扫描器（silent_exception/service_return/skip_hygiene/round_baselines/requirement_traceability/path_authority/startup_budget）作用域不含 data/，无需改。新增 `test_scan_scope_excludes_runtime_asr_venv` 断言排除生效；本地 99 条相关架构测试全绿。

## 下一步（证据驱动）

- 真实使用积累数日后跑 `paint_stats.py`：若 `fitwaits*16 ≈ 总耗时` 且 `fitpasses` 高 → 修布局收敛（签名粒度/轮数上限/触发源合并）；若 waits 低而总时高 → 修建页或 Tk 调用热点。
- 候选修复方向（待数据）：`_fit_content_now` 的全树 req 尺寸签名可按「直接子级+已知动态区」收窄；pet 气泡/idea 回填等 +150ms 后触发源可并入同一布局批；`resize()` 递归遍历每轮全树可缓存。
