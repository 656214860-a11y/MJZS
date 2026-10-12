# R1394：agent 进程原语收口到 platform_tools（覆盖率审计21 清零）

类型：修复轮（§3.2，2026-10-13）。中央轮次：1394。范围＝R1393 递归口径新暴露的 4 条 agent 真候选中「进程原语」2 条（覆盖率审计21）；按项目惯例把页面／业务层 OS 进程调用收口到 `platform_tools`。2 条 HTTPS 传输（覆盖率审计26）保留待裁定，不在本轮擅动。

## 三个必答
- 本轮类型：修复轮（§3.2）——改 `agent/core.py`／`agent/prompt_optimizer.py` 两处生产模块的进程调用经 `platform_tools.run_process`；同步台账与判据文档。
- 测试：定向 `test_coverage_audit_ratchet`＋`test_unification_ratchet` **7/7**；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **341/341**；`agent.core.command` 运行期复验通过。
- 欠账：`1394−1390=4<5` 且未命中 §5 升级条件（非启动器文件／非 Tk 控件生命周期／非删除语义／非层级登记表）→ **不跑全量**（最近绿全量 R1391 `tree=a8cfd2f0…`）。

## 实现（生产代码，最小改动，行为不变）
- `agent/core.py` `command()`：`subprocess.run(...)` → `platform_tools.run_process(...)`（**惰性 import**，维持启动路径轻量；`run_process` 会 `str(cwd)` 并 setdefault `creationflags=hidden_console_flags()`）；删去不再使用的模块级 `import subprocess`。保留 capture_output／text／utf-8／errors=replace；缺程序仍抛 `RuntimeError`，非零返回仍抛 `RuntimeError`。
- `agent/prompt_optimizer.py`：MCP 桥子进程 `subprocess.run(...)` → `platform_tools.run_process(...)`（**模块级 import**；该模块是 UI 页、非启动路径）；保留 `import subprocess` 供 `except subprocess.TimeoutExpired`／`SubprocessError`（异常类型不变），保留 `input`／`timeout=125`。
- 未改：`agent/core.py:189/208`（覆盖率审计26，HTTPS 传输，待裁定）。

## 台账与判据同步
- `维护记录/架构统一基数.json`：`覆盖率审计21` 两条 disposition `pending`→`migrated`（reason 以 `R1394：` 开头），`count` 2→0（`baseline_pending` 6 不动）；**行号平移修正**：`第四项` 的 `agent/core.py` 13→12、`agent/prompt_optimizer.py` 174→175（`json.loads` 位点）。
- `维护记录/覆盖率审计判据_20261001.md`：第 21 项真候选 2→0，并改写第 21 项说明。
- `覆盖率审计26` 两条（`agent/core.py:189/208`）仍 pending。

## 验证
- 定向：`tests.architecture.test_coverage_audit_ratchet`＋`test_unification_ratchet` **7/7、OK**（33.3 秒）。
- 默认冒烟：**8/8、0 失败**。
- 架构：`smoke_test.py --architecture` **341/341、0 红**（144.2 秒；数量不变）。
- 运行期：`agent.core.command([python,'-c','print(12345)'])` → `'12345\n'`；缺程序 → `RuntimeError`（文案不变）。
- 全量：**不跑**（见「三个必答」）。

## 提交
- 内容：`a966c41`（`agent/core.py`＋`agent/prompt_optimizer.py`＋`维护记录/架构统一基数.json`＋`维护记录/覆盖率审计判据_20261001.md`）。
- 报告／状态／接力：`0c1e471`（本文件＋`project_status.md`＋`.agent-handoff/` 5 文件）。

## 复盘
- 已收口：覆盖率审计21（平台适配）真候选归 0——棘轮双向相等，agent 包再出现直接 `subprocess.run` 会被 `test_coverage_audit_ratchet` 立即拦下。
- 新增待办：覆盖率审计26 的 2 条 HTTPS 传输（`agent/core.py:189/208`）待裁定「agent 包是否具权威传输适配器地位，或须收口」。
- 未做（理由）：HTTPS 传输涉及 agent 包对外部服务的调用语义与凭据流，需先裁定权威归属，不在本收口轮擅改。
