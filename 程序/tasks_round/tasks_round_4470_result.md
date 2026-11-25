# tasks_round_4470_result — DOC-Z1 开启 13 阶段文档接口/交互全量守卫 REQUIRE_ALL=True
<!-- round-evidence: {"commit_base": "4e99a65a4", "credential_hits": 0, "evidence_sha256": "7a0d3aeac1f6b8a4", "exit": 0, "failed": 0, "passed": 34, "round": 4470, "tests": "run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage"} -->

## 三问

1. 本轮类型：§3 之外的任务卡轮——文档守卫收口轮（DOC-Z1，W3，工作树 `doc-z1`，分支 `codex/doc-z1`，基准 `4e99a65a4`）。只改 `tests/architecture/test_stage_doc_sections.py` 与本结果文件；未改任何阶段文档、产品代码或权威文档。
2. 测试：按卡面跑 `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（4 文件 34 用例，0 红，退出码 0）；`smoke_test.py --architecture`（708 用例，OK，退出码 0）；另跑默认冒烟 `smoke_test.py`（通过 9 项、失败 0，退出码 0；基线 8/8 口径内）。全量 `run_selftests --all --safe` 未跑（见「未验证项」）。
3. 欠账：无新增欠账；`REQUIRE_ALL` 收口为 `True` 后，缺节即报的断言在 T2 真实文件用例中全绿，守卫由「两节皆无才放行」收口为「任缺必报」。

## 13 个阶段文件「## 接口」「## 交互」两节核实表

核实方式：`grep -n '^## 接口'` / `grep -n '^## 交互'`（文件为 CRLF 行尾，`$` 锚定不上行尾，故用前缀匹配；下文行号为 1 起）。13 个文件全部命中，无一缺失，故未触发卡面「立即停下上报」条款，也未给任何文件补空壳。

| 文件 | `## 接口` | `## 交互` |
| --- | --- | --- |
| `docs/stages/S01_剧本准备.md` | 行 335 | 行 412 |
| `docs/stages/S02_剧本结构.md` | 行 127 | 行 178 |
| `docs/stages/S03_初步分镜.md` | 行 139 | 行 213 |
| `docs/stages/S04_分镜预演.md` | 行 194 | 行 260 |
| `docs/stages/S05_资产管理.md` | 行 117 | 行 185 |
| `docs/stages/S06_连贯性清单.md` | 行 98 | 行 145 |
| `docs/stages/S07_分镜定稿.md` | 行 151 | 行 207 |
| `docs/stages/S08_首帧管理.md` | 行 118 | 行 171 |
| `docs/stages/S09_白模预演.md` | 行 116 | 行 194 |
| `docs/stages/S10_视频生成.md` | 行 123 | 行 200 |
| `docs/stages/S11_配音与字幕.md` | 行 111 | 行 174 |
| `docs/stages/S12_后期剪辑.md` | 行 108 | 行 184 |
| `docs/stages/S13_质检与交付.md` | 行 125 | 行 179 |

两节内容完整性另由守卫自身覆盖：`test_t2_real_stage_files_are_clean` 对 13 个真实文件逐文件跑 R1–R6（标题顺序、三级标题、编号、状态记号），本轮 34 用例全绿。

## 改动

仅 `tests/architecture/test_stage_doc_sections.py`（`git diff --numstat`：`7 4`）：

1. `REQUIRE_ALL = False` → `REQUIRE_ALL = True`（`:27`）。
2. docstring 同步为「两节一个都没有且 `REQUIRE_ALL = False` 时 `problems` 返回空清单；`REQUIRE_ALL` 自 DOC-Z1 收口轮起默认为 `True`，缺节即报。」（`:15-16`）。
3. `test_t4_require_all_flags_missing_sections`（`:200-207`）重写为三分支断言：先 `assertIs(REQUIRE_ALL, True)` 锁定默认值为 True，再断言默认（True）下 `problems(sample, 'S01')` 非空；False 分支用 `patch.object(sys.modules[__name__], 'REQUIRE_ALL', False)` 显式测试并断言返回 `[]`；True 分支 `patch.object(..., 'REQUIRE_ALL', True)` 断言报错。三处断言均为新增或等价保留，无任何弱化／删除／跳过。

## 读过的文件清单（证据为 file:line）

- `tests/architecture/test_stage_doc_sections.py:1-285`：全文，守卫 R1–R6 判定（`:60-141`）与 T1–T4 用例（`:148-207`）。
- `docs/stages/S01_剧本准备.md`：`## 需求 :3`、`## 设计 :158`、`## 接口 :335`、`## 交互 :412`（标题级定位，未逐行复读全文）。
- `docs/stages/S02..S13` 各文件：`## 接口`/`## 交互` 行号见上表（grep 定位）。
- `.devin/config.local.json:4-13`：本车道 exec 白名单。
- `tasks_round/tasks_round_4462_result.md`（git show）：DOC-S04 结果文件格式参照。

## 验收命令真实尾部

命令 1（cwd=`程序/`）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`，退出码 0，尾部原文：

```
IMPORT OK: all modules imported
定向：忽略增量台账，执行 4 个匹配测试文件
跑 4 个测试文件 / 4 路工作单元（8 路并行）
  architecture.test_design_coverage     8 条     0.1 秒
  architecture.test_stage_doc_sections    10 条     0.1 秒
  architecture.test_agent_doc_budget    11 条     0.2 秒
  architecture.test_requirement_traceability     5 条     1.9 秒

共 34 条用例，2.7 秒；0 个文件有红
…
ALL TESTS PASSED
```

命令 2（cwd=`程序/`）：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`，退出码 0，尾部原文：

```
----------------------------------------------------------------------
Ran 708 tests in 300.418s

OK
✅ 架构治理测试：tests/architecture
```

附加（非卡面验收项，§5 每轮默认冒烟）：`smoke_test.py` 退出码 0，尾部原文：

```
通过：9 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

## 未验证项

- `run_selftests.py --all --safe` 全量未跑：卡面验收只点名定向四文件与 `--architecture`；本车道路径白名单不含该命令所需范围，按授权边界不越界执行。
- 13 个阶段文件两节内部三级标题与编号行未逐行人工复读，由 T2 真实文件用例（34 用例全绿）覆盖。
- `test_t4` 的三分支断言直接对模块常量与 `problems()` 行为断言，未额外构造「只缺一节」样例——该情形在 `problems` R1 段既有判定（`:82-85`）覆盖，卡面未要求新增用例。
