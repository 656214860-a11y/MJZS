# R3215 结果：代收口停摆车道 R3199——依赖白名单机制落地＋核验修复
<!-- round-evidence: {"commit_base": "d29e1e83", "credential_hits": 0, "evidence_sha256": "42f31366b46a67ed", "exit": 0, "failed": 0, "passed": 3, "round": 3215, "tests": "run_selftests.py -k dependency_whitelist"} -->

## 三问

1. **轮次类型**：结构治理轮（§3.3；承接 R3199 车道（dsh-82c63326-f006）停摆约 3 小时的已暂存交付物，用户授权「核验后代为提交」）。
2. **测试跑了吗、三个基线过了吗**：`test_dependency_whitelist` 修复后 **3/3 通过**（unittest 可发现）；`test_agent_doc_budget` 等 8 项通过；默认冒烟 9/9（master 树实测）；架构门禁全量未重跑——master 存量 1 红为历史 json.loads 债务（R3199 结果文件已声明范围外），本轮新增门禁测试本身全绿。
3. **欠账少了吗**：消除一个「声明了门禁但空转」的隐性欠账；R3199 车道停摆造成的 master 合并阻塞解除。

## 背景与授权

R3199 车道（dsh）于 18:14 写交接文档后停摆，其 9 个文件留在 master 工作区暂存区，`merge_round.py` 拒绝在脏工作区合并，阻塞所有车道。用户选定「核验后代为提交」。核验发现原交付物存在实质缺陷，按本轮修复后提交。

## 交付物（R3199 原交付＋本轮修复）

### 原交付（保留）

- `CLAUDE.md`／`程序/AGENTS.md`／`程序/architecture.md`：零依赖→谨慎白名单依赖政策表述。
- `程序/维护记录/依赖白名单.md`：白名单策略、评估标准、禁止清单、门禁说明。
- `程序/tests/architecture/test_dependency_whitelist.py`：门禁测试。
- `tasks_round` R3199 结果文件、证据 JSON、BLOCKING/HANDOFF 报告。

### 本轮核验修复（如实记录）

1. **门禁测试取径错误**：原 `get_site_packages()` 取 `sys.path` 首个含 site-packages 路径，实际命中用户目录 `AppData\Roaming\Python\Python314\site-packages`（仅开发工具），`运行环境\Python\Lib\site-packages`（requests 等真实白名单库）扫不到 → 三项检查全挂。改为 `importlib.metadata.distributions()`＋`sysconfig` purelib 作用域过滤，只统计随包环境。
2. **`urllib` 前缀误吞**：原 STDLIB_PREFIXES 的 `'urllib'` startswith 会跳过 `urllib3`；新实现按分发包元数据精确名匹配，无此问题。
3. **unittest 不可发现**：原测试为模块级 `def test_*`（pytest 风格），项目 unittest 发现机制收集 0 项——门禁空转。改为 `DependencyWhitelistTests(unittest.TestCase)`，架构套件实际执行 3 项。
4. **白名单与环境不符**：实测 `Lib\site-packages` 有 13 个第三方分发包，原白名单只列 requests 链 5 个。补全 pillow/playwright/greenlet/gallery_dl/apted/ruff/tree-sitter/tree-sitter-python 共 8 个随包维护/开发工具（版本逐一按 dist 元数据核对），`依赖白名单.md` 增「随包维护/开发工具」一节说明其不进产品运行路径。
5. **AGENTS.md 超预算**：R3199 文案使文件达 16056 字节 > 16000 预算。压缩 §1 两行（白名单依赖表述最简化、解释器行恢复原口径），现 **15984 字节**达标；白名单文档指针由 CLAUDE.md 与 architecture.md 门禁清单保留。

## 验证记录

- `python -m unittest tests.architecture.test_dependency_whitelist`：**3/3 OK**（修复前 3/3 FAIL，已留证）。
- `test_agent_doc_budget`＋`test_dependency_whitelist` 合跑：**8/8 OK**。
- `smoke_test.py`（master 工作区，R3199 现场）：**9/9 通过**。
- `smoke_test.py --architecture`（master 工作区）：483 项中 2 红——`test_agent_doc_budget`（本轮已修，复测过）与 `test_unification_ratchet` json.loads 债务（R3199 已声明历史欠账、本轮不扩大）；本轮新增 3 项白名单测试在套件内实际执行且全绿。
- 提交门禁静态检查曾拦 `\P` 无效转义（docstring），已修复为 `\\`。

## 说明

- 轮次号 R3215：R3199 认领属已停摆 dsh 工作树（实体仍在，无法合法转移）；本轮在新工作树 `wt-r3199`/`codex/wip-R3215` 完成同一交付物的核验、修复与提交，R3199 原结果文件/证据/报告随本批入库备查。
- `运行环境` 为 gitignored 本地目录，解释器 3.14.7＋白名单包已在主工作区实测存在；本轮不改环境本身。
