# R3990 结果：DOC-G1 阶段文件「接口」「交互」两节的结构守卫 —— 失败报告（停止）

## 开头三问

- 本轮属于哪种类型：测试轮（任务书 §4.3 DOC-G1，「测试轮（只新增一个架构测试）」）。实际按 §4.13 停止。
- 测试跑了吗、三个基线：跑了。默认冒烟 9 项通过 0 失败（绿）；架构门禁改动前基线 `smoke_test.py --architecture` 实测 685/685 全绿，加入本卡允许的新测试文件后 `test_agents_md.test_architecture_guard_list_matches_actual_test_files` 与 `test_structure.test_real_repository_has_no_new_structure_violations` 两项必红（实证输出见下），验收「失败集合必须为空」无法达成；全量回归未运行（任务书禁止）。
- 欠账少了吗：本轮未新增欠账。卡本身欠两处登记放行，列入「需要主控决定」。

## 失败报告（§4.13）

```yaml
失败报告:
  任务卡: DOC-G1
  轮次: R3990
  停在哪一步: 步骤 3「再改代码，直到任务卡的全部测试和全部验收命令通过」
  现象: |
    测试文件本体（先红后绿）已实现并自测全过：
      PY -B -m unittest tests.architecture.test_stage_doc_sections -v → Ran 10 tests, OK
    但新增的 tests/architecture/test_stage_doc_sections.py 触发两条既有门禁：
      PY -B -m unittest ...test_architecture_guard_list_matches_actual_test_files -v
      FAIL: Items in the second set but not the first:
      'test_stage_doc_sections.py' : architecture.md 架构门禁清单必须与实际测试文件集合完全相等
      PY -B -m unittest ...test_real_repository_has_no_new_structure_violations
      FAIL: New directory debt: [('STR006', '程序/tests/architecture/test_stage_doc_sections.py', 'ownership')]
  已经试过:
    - 领号 R3990；前置核验通过：DOC-F0 提交 13ed7f81 在本车道 git log 中，docs/process/阶段文档写法.md 存在。
    - 按任务卡接口契约写 tests/architecture/test_stage_doc_sections.py：problems() 空桩先红（10 用例中 7 个断言失败，输出见下节），补齐实现后 10/10 绿。
    - 改动前跑 PY -B smoke_test.py --architecture：685/685 全绿。
    - 定位冲突一：tests/architecture/test_agents_md.py:157-165 要求 architecture.md「## 当前架构门禁清单」节内反引号列出的 test_*.py 集合与磁盘实际集合完全相等；AGENTS §5 也写明「增删架构测试时同轮更新清单」。放行须在 architecture.md 补一行登记。
    - 定位冲突二：governance/check_structure.py 的 STR006（tests/architecture/test_structure.py 驱动）要求每个 test_*.py 在 governance/structure.json 的 test_ownership 登记 kind/contract/targets，或有同名生产模块。stage_doc_sections 无同名生产模块，须在 structure.json 补一条登记。
    - architecture.md 与 governance/structure.json 均不在本卡「允许修改文件」（只允许新增测试文件与结果文件），且禁止事项写明「不改任何文档和任何已有测试」，按 §4.13 停下。
  我的判断: |
    任务卡的允许修改文件清单与仓库现行门禁冲突：本仓任何新增 tests/architecture/test_*.py
    都必须同轮登记 architecture.md 门禁清单和 structure.json test_ownership，两处都不在允许范围。
    守卫实现本身已按契约完成并自测全绿（红→绿实证如下），只差两处登记。
  需要主控决定: |
    请把 程序/architecture.md 与 程序/governance/structure.json 加入 DOC-G1 允许修改文件，
    或明确放行口径。建议改动：architecture.md「当前架构门禁清单」补 `test_stage_doc_sections.py`
    （阶段文件接口/交互两节结构守卫）；structure.json test_ownership 补
    "程序/tests/architecture/test_stage_doc_sections.py":
    {"kind": "architecture", "owner": "项目维护者", "contract": "阶段文件接口/交互两节结构守卫",
     "targets": ["程序/docs/process/阶段文档写法.md"]}。
    测试文件已 git stash 留在车道，放行后恢复即可按原提交行提交。
  工作树状态: |
    git stash 存下 tests/architecture/test_stage_doc_sections.py（见下）；本结果文件为唯一提交内容。
```

## T1 改前失败输出（先红）

`problems()` 空桩 `return []` 时运行 `PY -B -m unittest tests.architecture.test_stage_doc_sections -v`：

```
FAIL: test_t1_r1_violation ... AssertionError: [] is not true
FAIL: test_t1_r2_violation ... AssertionError: [] is not true
FAIL: test_t1_r3_violation ... AssertionError: [] is not true
FAIL: test_t1_r4_violation ... AssertionError: [] is not true
FAIL: test_t1_r5_violation ... AssertionError: [] is not true
FAIL: test_t1_r6_violation ... AssertionError: [] is not true
FAIL: test_t4_require_all_flags_missing_sections ... AssertionError: [] is not true
Ran 10 tests in 0.006s
FAILED (failures=7)
```

## 实现后自测（转绿）

`PY -B -m unittest tests.architecture.test_stage_doc_sections -v`：10 个用例全部 ok（T1 六条规则违规样例＋合规样例、T2 真实阶段文件、T3 跨文件编号、T4 REQUIRE_ALL 打补丁）。

## 验收命令逐条结果

| 命令 | 结果 |
|---|---|
| `PY -B -m unittest tests.architecture.test_stage_doc_sections -v` | 10/10 通过（文件在 stash 中，未提交） |
| `PY -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_design_coverage tests.architecture.test_doc_registry_migration tests.architecture.test_agent_doc_budget tests.architecture.test_structure -v` | 58 用例 1 失败：`test_structure` 报 STR006 ownership（冲突二实证；新增测试文件落地前该套件为绿） |
| `PY -B -m unittest tests.architecture.test_layers -v` | 未运行（与本卡无关，树无分层改动） |
| `PY -B smoke_test.py --architecture` | 改动前 685/685 全绿；改动后 `test_agents_md` 门禁清单检查必红（单项实证见失败报告「现象」），整轮未重跑 |

## 提交前自查（code-review 两条轴，会话内完成）

- 规范轴：`tests/architecture/test_stage_doc_sections.py` 复用 `test_requirement_traceability.stage_files()`（契约要求）；只用标准库（re、unittest、unittest.mock）；`problems()` 不读文件、签名与契约一致（约 95 行，低于函数规模棘轮 150）；模块 docstring 列全六条规则并指向 `docs/process/阶段文档写法.md`；样例跳过 ``` 围栏行避免误报。未发现问题。
- 契约轴：R1–R6、REQUIRE_ALL=False、stage_files() 复用、T1–T4 逐条对得上；无规格外行为。遗留缺口即本报告的登记冲突，非实现缺陷。

## 差异清单与待裁决

- 差异清单：无（本轮未写文档事实）。
- 待裁决：architecture.md／governance/structure.json 两处登记放行（见失败报告「需要主控决定」）。

## 工作树状态

```
git stash push -m "R3990 DOC-G1 结构守卫实现（待登记放行）" -- 程序/tests/architecture/test_stage_doc_sections.py
```

stash 后 `git status --short` 仅余本结果文件，已按 §4.13 只提交结果文件。
