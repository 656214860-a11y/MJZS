# R4415 结果：REL-12 实机走通清单（发布前人工验收操作表，只读生成）
<!-- round-evidence: {"commit_base": "9f501243c", "credential_hits": 0, "evidence_sha256": "168a62972158e510", "exit": 0, "failed": 0, "passed": 34, "round": 4415, "tests": "run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage"} -->

## 三问
- 轮次类型：功能轮（§3.1，先文档后写码口径；纯文档卡，无任何 .py 改动）。
- 测试和三个基线：定向 `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 改前 34 条全绿、改后 34 条全绿（退出码 0）；`smoke_test.py --architecture` 复现红 1 条（登记门禁，改后复跑 708 条全绿，退出码 0）；默认冒烟 8/8 本轮未运行（卡面验收未列）。
- 欠账：持平。新增一份人工验收操作表，不增不减测试与代码欠账。

## 缺陷复现
- 缺陷：发布就绪调研列出的缺口——基线 §2「实机」列、§4 三条 A 级待实机复验、PRD §10 八项待验收、REL-03 首启矩阵、REL-04 升级保留、REL-14 DPI/多屏、REL-07 选择项目页复验、关于页/帮助入口，此前没有一份「人能照着点」的操作表（AUD-REAL 按用户 11-22 决定只做读码审查）。
- 卡面验收的定向命令只覆盖四个架构测试，均不检查本文档存在性：改前 `-k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 即 34 条全绿（退出码 0），符合卡面「无代码用例」的设定。
- 实际红→绿证据：先建文档不登记，跑 `smoke_test.py --architecture`，`tests/architecture/test_doc_registry_migration.py::test_all_current_documents_are_registered` 红 1 条：`AssertionError: Lists differ: ['存在但未登记：docs/process/实机走通清单.md'] != []`（708 条用例、退出码 1）——与卡面「不登记过不了 test_doc_registry_migration」一致；登记后复跑全绿。

## 改动
- `docs/process/实机走通清单.md`（新建）：发布前人工验收操作表。§0 使用口径（执行人、免费档≈60 分钟与待真实使用档分档、证据目录 `程序/验收证据/<YYYYMMDD>/`、判定口径、执行记录）；§1 免费档五组：1.1 启动与首启（A1–A4 REL-03 四情形首启矩阵、A5 每次先跳选择项目页、A6 缺陷台账 A 级①启动饿死链）、1.2 项目登记（B1 改名认领、B2 右键清失效登记，台账 A 级②③）、1.3 DPI/多屏/系统版本（C1–C4，REL-14）、1.4 升级保留数据（D1–D2，REL-04）、1.5 关于页与帮助入口（E1–E2，REL-13）；§2 待真实使用档：2.1 基线 §2 手工步骤 US01–US07、2.2 PRD §10 八项 P0-3～P2-1；§3 与 release-gate/发布检查单/基线/PRD §10 的衔接；§4 执行记录表；§5 维护检查单。每步字段齐全：怎么点／预期看到什么／证据存哪里／对应的自动测试／风险，步骤全部取自既有代码入口、测试断言与文档原文，未发明的界面行为。
- `docs/records/工程文档登记表.md:113`：登记新文档一行（`全局 | 全局 | 权威 | R4415 | 用户、执行 agent`），卡面允许只加本卡新建文档该行。

## 核对（命令输出尾部原文）
- `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`，退出码 0：
  ```
  跑 4 个测试文件 / 4 路工作单元（8 路并行）
    architecture.test_design_coverage     8 条     0.0 秒
    architecture.test_stage_doc_sections    10 条     0.1 秒
    architecture.test_agent_doc_budget    11 条     0.1 秒
    architecture.test_requirement_traceability     5 条     0.5 秒

  共 34 条用例，1.3 秒；0 个文件有红
  ……
  ALL TESTS PASSED
  ```
- `smoke_test.py --architecture`（登记前复现），退出码 1：
  ```
  FAIL: test_all_current_documents_are_registered (tests.architecture.test_doc_registry_migration.DocRegistryMigrationTests.test_all_current_documents_are_registered)
  AssertionError: Lists differ: ['存在但未登记：docs/process/实机走通清单.md'] != []
  Ran 708 tests in 254.105s
  FAILED (failures=1)
  ```
- `smoke_test.py --architecture`（登记后复跑），退出码 0：
  ```
  ----------------------------------------------------------------------
  Ran 708 tests in 246.946s

  OK
  ✅ 架构治理测试：tests/architecture
  ```

## 未验证
- 默认冒烟 8/8 与全量 `run_selftests.py --all --safe` 未运行（卡面验收未列；本卡零 .py 改动）。
- 操作表本身未在真机上执行——按卡面只读生成；「清单已执行并有证据目录」属 release-gate 人工确认项，由执行人在发布前照表走并留证。
- 免费档步骤的机器前提（双显示器、旧版系统、命令行引擎、有效 API Key）若缺，按表内口径标「不适用」。
- 「拿不准」项：范围与花费上限按卡面默认——免费档约 60 分钟、不调用付费模型；待真实使用档不预付预算，仅列步骤与证据位。
- 卡外发现（只记录不修）：`文档导航.md` 末尾有「新增文档请在此登记用途」的指引，但不在本卡允许文件内，未登记；登记表是唯一被门禁强制核对的索引。
