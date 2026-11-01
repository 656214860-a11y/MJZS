# R1387：UI 统一入口覆盖轮 — 按钮门禁递归零容忍（全生产 269 模块 0 裸 tk/ttk.Button）

类型：修复轮（§3.2，2026-10-12）。中央轮次：1387（`.git/round-counter.json` 的 `last_claimed=1387`）。范围＝路线图 v1 §一 第 1 项「按钮」（权威入口 `ui_widgets.setup_styles()`／`PrimaryButton`／`SecondaryButton`；审计点原文「全页面覆盖率待审计」）——把 `test_button_boundary` 由「固定页清单」收紧为「递归零容忍」，与 R1381 弹窗门禁同法。

## 三个必答
- 本轮类型：修复轮（§3.2）——只改架构门禁测试文件，不改任何生产代码、阶段、路径与分层。
- 测试：定向 `python -m unittest tests.architecture.test_button_boundary` **25/25**（原 23，+2）；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **331/331**（原 329，+2）。
- 欠账：本轮**命中 §5 五轮规则（1387−1382=5≥5）**，收口全量：干净 master 工作树 `o07-fullsafe-master`（`git reset --hard master`→`d5f597f`）跑 `run_selftests.py --all --safe`：**4973 条、572.5 秒、0 文件有红**（凭据 `round=1386`、`tree=000477da…`＝`d5f597f:程序`；`last_full_safe_all_round` 刷新为 1386）。

## 实现（不改生产代码）
`tests/architecture/test_button_boundary.py`：
- 新增常量 `BUTTON_OWNERS={'ui_widgets.py'}`（统一控件基类自身允许构造 `tk/ttk.Button`）与 `EXCLUDED_PARTS`（与 `test_dialog_boundary` 一致：tests／tasks_round／维护记录／.git／__pycache__）。
- 新增 `test_production_modules_use_semantic_buttons`：`ROOT.rglob('*.py')` 递归扫描全部生产模块（含 `batch_frames_tool/`、`agent/` 等子目录），出现裸 `tk/ttk.Button`（含静态导入与赋值别名链）即失败；豁免 `ui_widgets.py`。
- 新增 `test_recursive_scan_covers_subdirectories`：镜像 canary，确认扫描集合确实覆盖子目录文件，门禁不是「只扫根目录」的假阴性空集。
- 保留既有逐页用例（除「无裸 Button」外还断言页面必须导入 `PrimaryButton`／`SecondaryButton` 等语义组件），未删减。
- 站点实测：递归扫描 269 个生产 `.py`，除 `ui_widgets.py`（7 处，统一基类自身实现）外 **0 命中**——与 R1381 backlog 判断一致（站点早已清零，缺的只是门禁口径）。

## 测试契约同步（§2.4）
- 无（只新增门禁断言，无既有断言被改）。`维护记录/架构统一基数.json` 无行号平移。

## 验证
- 定向：`tests.architecture.test_button_boundary` **25/25、OK**（2.9 秒）。
- 架构：`smoke_test.py --architecture` **331/331、0 红**（131.7 秒；326→329 为 R1386，329→331 为本轮）。
- 默认冒烟：`smoke_test.py` **8/8、0 失败**。
- 全量（§5 五轮规则触发，干净 master 工作树 `o07-fullsafe-master`）：**4973 条、572.5 秒、0 个文件有红**；`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均通过，无阈值抖动。凭据 `round=1386`、`tree=000477da24212c15bc3a144ff61ad35865b21588`＝`d5f597f:程序`。
  说明：全量执行器用「最新已完成结果文件号」给凭据编号，跑时本轮（1387）结果尚未落盘，故 `round=1386`；`tree` 与实际验证的代码树一致。
- 新增 `skipTest`：无。

## 提交
- 内容提交：**`d5f597f`**（1 file：`tests/architecture/test_button_boundary.py`）。
- 报告与状态／接力：**`ec2320b`**（7 files：本结果文件＋`project_status.md`＋`.agent-handoff/` snapshot／backlog／risks／work-log／validation）。

## 复盘：路线图 v1 §一 第 1 项「按钮」
- 完成判据原文「全页面覆盖率待审计」。本轮做到：**门禁口径由「固定页清单」升为「递归全生产零容忍」**，覆盖子目录，任何新增／迁移页面出现裸 `tk/ttk.Button` 都会被捕获；站点实测 0 命中，即全页面覆盖率经门禁固化。
- 未做（说明理由）：`ui_widgets.py` 自身保留裸 `Button` 是统一基类的实现本体（与 `test_dialog_boundary` 豁免 `ui_widgets.py` 同理），非业务页，不计作违规。
