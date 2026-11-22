# R4004 结果：DOC-G1 阶段文件「接口」「交互」两节的结构守卫 —— 失败报告（停止）

## 开头三问

- 本轮属于哪种类型：测试轮（任务书 §4.3 DOC-G1）。按主控裁决（2026-11-21）补两处登记后推进到提交步，因提交门禁拒绝按 §4.13 停止。
- 测试跑了吗、三个基线：跑了。默认冒烟 9 项通过 0 失败（绿）；架构门禁 `smoke_test.py --architecture` 实测 695/695 全绿（改动前基线 685，本卡新增 10 个用例），失败集合为空；全量回归未运行（任务书禁止）。实现本身全部就绪，只是提交被车道冲突门禁拦下。
- 欠账少了吗：本轮未新增欠账。R3990 欠的两处登记已在本车道的暂存改动里补齐并通过验收，随 stash 留在车道待放行。

## 失败报告（§4.13）

```yaml
失败报告:
  任务卡: DOC-G1
  轮次: R4004
  停在哪一步: 步骤 6「提交」
  现象: |
    PY -B scripts\dev.py commit -m "R4004: 阶段文件接口与交互两节的结构守卫" --agent Devin
      tests/architecture/test_stage_doc_sections.py architecture.md
      governance/structure.json governance/structure-baseline.json
      tasks_round/tasks_round_4004_result.md --tests stage_doc_sections
    拒绝提交：路径 程序/governance/structure-baseline.json 与活跃分支
      codex/l2-maturity-takeover 的未合入改动重叠，试合并有真实冲突
    拒绝提交：路径 程序/governance/structure.json 同上
    （architecture.md 与 6 条车道重叠但试合并可自动合并，不拦截）
  已经试过:
    - 领号 R4004；前置核验通过：DOC-F0 提交 13ed7f81 在本车道 git log，docs/process/阶段文档写法.md 存在。
    - 按裁决取回 stash@{0}（「R3990 DOC-G1 结构守卫实现（待登记放行）」）并 drop，文件原样回到工作树，10/10 自测绿。
    - architecture.md「当前架构门禁清单」加一行 test_stage_doc_sections.py；structure.json test_ownership 加一条（kind=architecture、targets=docs/process/阶段文档写法.md）。
    - structure.json 变更触发 test_structure 的 policy_sha256 复核：必须先跑 governance\check_structure.py --write-baseline 显式重写基线（先例 R3956 同法）。重写后 delta added/removed 均空，violations 不变。
    - 全部验收命令重跑全绿（见下表），随后提交被车道冲突门禁拦下。
    - 核对冲突本质：活跃车道 codex/l2-maturity-takeover（尖 b98026a1，2026-11-21 01:03，24h 活跃窗内）在 structure.json 同一位置（test_ownership 末尾）追加了 5 条登记、并重写了基线同样三行溯源字段。
      structure-baseline.json 的改动位置（第 3–5 行 source_commit/inventory_sha256/policy_sha256）任何 policy 变更都会改，无法「错开改动位置」；
      structure.json 的登记可错开，但 baseline 单独存在已足够拦下提交。
    - 不把 baseline 与 policy 拆成两次提交：structure.json 入库而 baseline 未更新会让 test_structure 变红（ValueError: Directory policy changed without explicit baseline review），两者必须同批。
    - 不绕过：--no-verify 被本任务禁止；门禁无放行开关。
  我的判断: |
    卡本身已全部完成且验收全绿；阻塞纯来自并行车道的提交门禁：
    对方也在改 structure.json 登记区与基线溯源行，试合并必然真实冲突，
    唯一出路是等 codex/l2-maturity-takeover 合入（或其自然失活超过 24h）后再提交，
    或由主控协调两条车道的合入顺序。本轮范围内无可行的合规动作。
  需要主控决定: |
    协调顺序：待 codex/l2-maturity-takeover 合入 master 后，在本车道重放 stash
    （stash 说明见下），重跑 --write-baseline 与验收命令，按原提交行提交即可；
    届时 structure.json 若仍撞车，把本车道登记移到 test_ownership 内不与对方重叠的位置，
    baseline 以本车道当时的 policy 重算。若主控判定该车道短期不合入，
    也可由主控侧直接携带本批改动合入。
  工作树状态: |
    git stash push -u 存下 4 个文件：tests/architecture/test_stage_doc_sections.py（新增）、
    architecture.md（+1 行）、governance/structure.json（+1 条）、
    governance/structure-baseline.json（溯源重写）；本结果文件为唯一提交内容。
```

## 与 R3990 的关系

- R3990 按 §4.13 停在步骤 3（登记文件当时不在允许范围），测试文件存 stash；本轮领新号 R4004，按主控裁决补登记并完成全部验收，停在步骤 6（提交门禁拒绝）。
- 「先红后绿」证据沿用 `tasks_round_3990_result.md`「T1 改前失败输出」一节（空桩 7 项 FAIL），实现后 10/10 绿。

## 改动清单（已就绪、随 stash 留在车道）

| 文件 | 改动 |
|---|---|
| `tests/architecture/test_stage_doc_sections.py` | 新增（R3990 写就，本轮自 stash 取回，未再改动） |
| `architecture.md` | 「## 当前架构门禁清单」加一行 `test_stage_doc_sections.py` |
| `governance/structure.json` | `test_ownership` 加一条 `程序/tests/architecture/test_stage_doc_sections.py`（kind=architecture，targets=`程序/docs/process/阶段文档写法.md`） |
| `governance/structure-baseline.json` | `--write-baseline` 显式重写，仅三个溯源字段，violations 不变；baseline 重写是 structure.json 变更的强制配套（test_structure policy_sha256 复核，先例 R3956） |

## 验收命令逐条结果（改后实测，全绿）

| 命令 | 结果 |
|---|---|
| `PY -B -m unittest tests.architecture.test_stage_doc_sections -v` | 10/10 通过（OK） |
| `PY -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_design_coverage tests.architecture.test_doc_registry_migration tests.architecture.test_agent_doc_budget tests.architecture.test_structure -v` | 58/58 通过（OK），结构检查 delta 为空 |
| `PY -B -m unittest tests.architecture.test_layers -v` | 27/27 通过（OK） |
| `PY -B smoke_test.py --architecture` | 695/695 通过，失败集合为空（改动前 685，+10 即本卡新用例） |
| `PY -B smoke_test.py`（默认冒烟基线） | 9 项通过 0 失败 |
| `PY -B scripts\dev.py commit ...`（任务卡提交行＋裁决追加文件） | 拒绝提交：与活跃分支 codex/l2-maturity-takeover 试合并真实冲突（structure.json、structure-baseline.json） |

## 提交前自查（code-review 两条轴，会话内完成）

- 规范轴：测试文件只用标准库、`problems()` 不读文件、复用 `stage_files()`、docstring 列全六条规则并指向 `docs/process/阶段文档写法.md`；两处登记各一处、照相邻条目写法；baseline 由官方入口重写未手改。未发现问题。
- 契约轴：`problems(text, stage) -> list[str]`、两节全缺返回空列表、R1–R6、`REQUIRE_ALL = False`、T1–T4、裁决两处登记的键值逐字照办；规格外动作只有 baseline 重写（门禁强制配套，已说明）。未发现问题。
