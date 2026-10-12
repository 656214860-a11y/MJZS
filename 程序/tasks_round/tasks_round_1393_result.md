# R1393：覆盖率审计棘轮口径递归化（产品运行时子包）＋新暴露真候选登记

类型：修复轮（§3.2，2026-10-12）。中央轮次：1393（本轮先落结果文件再领号，`round_claim` 据此跳到 1393；无 R1392 提交、1392 无结果文件）。范围＝R1390 登记的待办「其余仍走 `production_files()`（根目录）的门禁（coverage ratchet 20/21/22/24/25/26、json_io/table 等）是否同批递归化」的逐段评估与执行。**不改生产代码**。

## 三个必答
- 本轮类型：修复轮（§3.2）——只改架构扫描辅助／覆盖率审计棘轮与台账／判据文档，不改生产代码。
- 测试：定向 `test_coverage_audit_ratchet`＋`test_unification_ratchet` **7/7**；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **341/341**（数量不变，改既有门禁）。
- 欠账：`1393−1390=3<5` 且未命中 §5 升级条件 → **不跑全量**（最近绿全量 R1391 `tree=a8cfd2f0…`）。新暴露 4 条真候选登记为 pending（见下）。

## 评估（只读实测）
- 现状：`test_coverage_audit_ratchet.scan()` 默认走 `_scan.production_files()`（**仅根目录**），故对 `程序/agent/`（被 30+ 产品模块 `from agent.core import ...` 实际导入的运行时子包）与 `batch_frames_tool/` 完全失明。
- 全递归实测新增命中：kind 21（进程）9 条、kind 22（删除）2 条、kind 26（网络）2 条；其中 `skills/**`／`scripts/**`／`reference/**`／`outputs/**` 为独立脚本／开发脚本／参考资料／构建产物，不属于「正式资源目标」。
- 剔除非产品目录后（新增 `_scan.production_runtime_files()`：递归再排除 `skills`／`scripts`／`reference`／`outputs`／`附加工具`，共 239 个运行时模块）：kind 20＝0、kind 21＝2、kind 22＝0、kind 24＝0、kind 25＝0、kind 26＝2。

## 实现（不改生产代码）
- `tests/architecture/_scan.py`：新增 `NON_PRODUCT_PARTS` 与 `production_runtime_files()`（递归再排除非产品目录）。
- `tests/architecture/test_coverage_audit_ratchet.py`：`scan()` 默认范围改 `production_runtime_files()`；台账键由 `p.name` 改为相对 `程序/` 的 posix 路径（`_key()`，根目录文件与此前同名不变）；补扫描范围 docstring。
- `维护记录/架构统一基数.json`：`覆盖率审计21` 增 2 条 pending、`覆盖率审计26` 增 2 条 pending，`count` 同步（21→2、26→2；26 的 `baseline_pending` 1→2）。
- `维护记录/覆盖率审计判据_20261001.md`：第 21／26 行真候选 0→2、全部命中 0→2，并补两条真候选说明。

## 新暴露真候选（已登记 pending，待语义裁定）
- 21 · `agent/core.py:173`：agent 包进程原语 `command()` 直接 `subprocess.run`（ffmpeg/ffprobe），未经 `platform_tools.run_process`。
- 21 · `agent/prompt_optimizer.py:172`：Prompt Optimizer MCP 桥接子进程直接 `subprocess.run`。
- 26 · `agent/core.py:189`／`208`：agent 包 HTTP 传输 `request()`／HTTPS 下载 `download()` 直接 `urllib.request.urlopen`。
- 处置：本轮只做审计入账（棘轮双向相等），**不擅自判定收口或白名单**；是否经 `platform_tools`／模型池收口或认定权威适配器，留待后续裁定轮。

## 测试契约同步（§2.4）
- 无既有断言被改；台账键格式对根目录文件不变，无行号平移。

## 验证
- 定向：`tests.architecture.test_coverage_audit_ratchet`＋`test_unification_ratchet` **7/7、OK**（31.7 秒）。
- 默认冒烟：**8/8、0 失败**。
- 架构：`smoke_test.py --architecture` **341/341、0 红**（133.9 秒；数量不变）。
- 全量：**不跑**（见「三个必答」）。

## 提交
- 内容：`8f1a1fc`（`tests/architecture/_scan.py`＋`test_coverage_audit_ratchet.py`＋`维护记录/架构统一基数.json`＋`维护记录/覆盖率审计判据_20261001.md`）。
- 报告／状态／接力：`5275919`（本报告＋`project_status.md`＋`.agent-handoff/` 5 文件）。

## 复盘
- 已收口：R1390 登记的「其余根目录口径门禁递归化」在覆盖率审计段完成。
- 新增待办：上述 4 条 agent 真候选的裁定／收口。
- 未做（说明理由）：其余 root-only 门禁（`test_json_io_boundary` 等按模块名精确扫描，非目录口径）不受本次影响，未在本轮扩大；secret sink（第 27 项）仍为根目录口径，是否同批递归化需另段评估。
