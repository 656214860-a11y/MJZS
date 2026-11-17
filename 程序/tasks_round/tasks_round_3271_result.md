# R3271 结果 · 修复轮：发送键圆环移出共享圆角平铺缓存（全量预审发现）

- 轮次类型：修复轮（§3.2；根因在 `ui/ui_composer_style.py` 对 `ui/ui_rounded.rounded_photo` 共享缓存的误用）。
- 三问：测试跑了——定向 67/67 绿（含 `test_complexity_ratchet` 参数棘轮）、默认冒烟 9/9；适用基线：架构门禁合并轮出口 CI 复测（532 条，本轮修正后参数棘轮通过）；全量 `--all --safe` 已在合入前触发并如实记录（见下）；欠账：无新增，环境类欠账登记入待办队列。

## 根因与修复

- **根因**：U4（R3241）给 `Tokens.Composer.Send.TButton` 四态各建了一张 32px 圆环图，经 `rounded_photo()` 写入 `root._drama_rounded_cache`。该缓存被 `test_ui_modern_system.RoundedTileSizeTests.test_cached_rounded_images_have_large_tile_centres` 断言为「可九宫格平铺的底图」（≥64×32 硬下限），发送键圆环是定长图元、宽仅 34px（`max(2*16+2, 32*factor)`），全量 `--all --safe` 实测 `AssertionError: 34 not greater than or equal to 64`。
- **修复**：`ui/ui_rounded.py` 抽出 `_rounded_image(root, cache_attr, spec)` 共用体；`rounded_photo` 签名不变（7 参，参数棘轮上限内）继续走 `_drama_rounded_cache`；新增 `element_photo`（同 7 参）供定长图元走独立 `_drama_element_cache`。`ui/ui_composer_style.py` 发送键四态改调 `element_photo`。
- **过程订正**：首版曾给 `rounded_photo` 加 `cache=` 第 8 参——合并轮出口 CI 的 `test_complexity_ratchet.test_parameter_count_does_not_grow` 判 `8 > 上限 7` 拒绝合并（未领号、已还原）；本版改为独立入口函数消掉参数超限，已随本提交修正（amend 同轮）。

## 验证

- 改前失败证据：`logs/hidden_selftest.log`（全量预审）`test_ui_modern_system` 1 红 `34 not greater than or equal to 64`；合并轮出口 CI `test_complexity_ratchet` 1 红 `rounded_photo 8 个参数 > 上限 7`。
- 改后定向：`run_selftests.py -k complexity_ratchet ui_modern_system shared_input_ui script_composer` → **67/67 绿**（平铺下限断言、参数棘轮、U4 发送键几何/四态断言全过）；前次同范围含 `hover_card_states ui_widgets_inputs` 共 82/82 绿。
- `smoke_test.py` → **9/9**。
- 未跑：`--architecture` 全量（由合并轮出口 CI 覆盖）。

## 全量预审结论（`--all --safe`，合入前按任务书 §5 触发）

- 运行约 17 分钟后因输出 GBK 编码崩溃中断，且结尾判「验收无效：测量期间 HEAD 或工作树变化，不写入绿凭据」（期间本工作树新增未跟踪驱动脚本所致）。
- 实测红项分类：
  - **真实回归 1 项**：上述圆环缓存越界——本轮已修复并定向复绿；
  - **结构性已知 1 项**：`test_round_number_continuous`（分支状态页 3214 落后，合并轮 bump 后自愈）；
  - **环境性约 50 项**：本工作树缺 `运行环境/`（ffmpeg 等随包工具 → `platform_tools` 解码器 None）；`round_claim.git_common_dir()` 在「非 ASCII 绝对路径的链接工作树」下 subprocess GBK 解码崩溃；技能 gitlink/注册表计数差异（`test_round_gate` 72!=73 等）。主树 `.wt/ci` 干净检出不具备这些环境缺陷，合并后后台全量为权威凭据。
- 环境类根因已登记 `维护记录/优化待办队列.md`（UI-U7-4），不在本任务书范围内改 infra。

## 提交

见 git log（`codex/wip-R3241`）。
