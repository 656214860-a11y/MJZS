# R1735：契约轮——需求／设计文档按阶段拆为 docs/stages 13 个文件（DOCS_SPLIT）

执行者：opencode（DeepSeek Harness）。车道：`D:\漫剧制作助手\.wt\lane_docs\程序`；解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`。
未执行任何 git 写命令，未领号、未提交，未改 `project_status.md`，未改任何产品代码。

## 三个问题

1. **本轮属于 §3 哪种类型？** 契约轮（文档结构）：只改 `docs/` 的分文件结构、文档锚定门禁读路径与其基线说明，以及引用旧路径的三份文档；不改生产代码与用户数据。
2. **测试跑了吗、三个基线过了吗？** 跑了任务书 §验证 的 4 项，另加 2 项文档相关回归：一致性自检 PASS；门禁单测 5 个用例 0 红（另有先红后绿两次复现）；`smoke_test.py --architecture` 369 个用例 0 红（144.5s）；`smoke_test.py` 本轮 8 项全过（8/0）；`tests.test_distribution_selfcheck`＋`tests.test_line_endings` 19 个用例 0 红。默认冒烟基线 8/8 保持。
3. **`project_status.md` 的欠账少了吗？** 车道不写状态页（派发执行方不领号、不改状态页），本轮不涉及 `project_status.md` 欠账增减；新增/移除的架构测试条目已在本报告说明。

## 拆分清单（文件 → 条目数）

旧两份文件读自 `git show HEAD:程序/docs/...`；需求＝定义行 `- **REQ-Sxx-nn** 状态`，设计＝唯一的 `DES-Sxx-nn` 编号数。

| 阶段 | 新文件 | 需求 | 设计 | 设计删减字符 |
| --- | --- | --- | --- | --- |
| S01 剧本准备 | `docs/stages/S01_剧本准备.md` | 35 | 24 | 102 |
| S02 剧本结构 | `docs/stages/S02_剧本结构.md` | 17 | 13 | 0 |
| S03 初步分镜 | `docs/stages/S03_初步分镜.md` | 31 | 14 | 0 |
| S04 分镜预演 | `docs/stages/S04_分镜预演.md` | 29 | 14 | 0 |
| S05 资产管理 | `docs/stages/S05_资产管理.md` | 24 | 16 | 0 |
| S06 连贯性清单 | `docs/stages/S06_连贯性清单.md` | 23 | 16 | 0 |
| S07 分镜定稿 | `docs/stages/S07_分镜定稿.md` | 32 | 16 | 67 |
| S08 首帧管理 | `docs/stages/S08_首帧管理.md` | 26 | 16 | 0 |
| S09 白模预演 | `docs/stages/S09_白模预演.md` | 27 | 20 | 0 |
| S10 视频生成 | `docs/stages/S10_视频生成.md` | 24 | 22 | 1089 |
| S11 配音与字幕 | `docs/stages/S11_配音与字幕.md` | 18 | 12 | 0 |
| S12 后期剪辑 | `docs/stages/S12_后期剪辑.md` | 27 | 16 | 0 |
| S13 质检与交付 | `docs/stages/S13_质检与交付.md` | 33 | 17 | 0 |
| 合计 | `docs/stages/`（13 个） | 346 | 216 | 1258 |

另新建 `程序/docs/README.md`（合并两份旧文件的开头说明：编号规则、状态符号、原地修改不记历史、分层以 `architecture.md` 为准），并列出上表 13 个阶段的索引。
旧文件 `程序/docs/REQUIREMENTS.md`、`程序/docs/DESIGN.md` 用 Python `os.remove` 删除（git 历史可恢复；当前 `git status` 显示为 `D`）。

## 一致性自检输出

脚本：`工作流任务\probe_docs\doc_split.py`（`build` 生成、`check` 只读核对；旧文件一律 `git show HEAD` 读取）。核对项：编号集合、每条 REQ 状态符号、逐阶段「需求正文＝原文」「设计正文＝原文减声明的删除」、设计节无残余行号、定义行只出现在对应阶段文件。

```text
      跨阶段引用（允许）：REQ-S02-25 → S03_初步分镜.md
      跨阶段引用（允许）：REQ-S03-20 → S04_分镜预演.md
      跨阶段引用（允许）：REQ-S02-23 → S05_资产管理.md
    旧文件编号：REQ 346，DES 216；新文件编号：REQ 346，DES 216
    需求条目 346；阶段文件 13 个
      S01 剧本准备 设计删减 102 字符
      S02 剧本结构 设计删减 0 字符
      S03 初步分镜 设计删减 0 字符
      S04 分镜预演 设计删减 0 字符
      S05 资产管理 设计删减 0 字符
      S06 连贯性清单 设计删减 0 字符
      S07 分镜定稿 设计删减 67 字符
      S08 首帧管理 设计删减 0 字符
      S09 白模预演 设计删减 0 字符
      S10 视频生成 设计删减 1089 字符
      S11 配音与字幕 设计删减 0 字符
      S12 后期剪辑 设计删减 0 字符
      S13 质检与交付 设计删减 0 字符
    PASS：编号集合、状态符号、文字差异均符合拆分规则
```

## 第 3 条删除表（原文 → 删后）

删除项：① 行号；② 写法说明（只保留一行委托／避免扩大行数之类）；③ 与 `architecture.md` 重复的分层描述。删除只作用于 `## 设计`；`## 需求` 一字未动。下表按实际顺序累计，共 58 处。

> 顺序说明：删除项 4 先整段删掉 38 处含行号的括注（如 `（`engine.py:228`）`），删除项 5 再处理剩下的 15 处行内引用；另有 39 处行内引用本就在删除项 4 的括注里，随括注一并移除，不再重复计入。`doc_split.py check` 的 `check_deletion_coverage` 对每条正则**独立**计数得 38／54／2 次（54 含上述被括注整段删除的那 39 处）。

| 删除项 | 类别 | 阶段 | 原文 | 删后 |
| --- | --- | --- | --- | --- |
| 1 | 字符串 | S01 剧本准备 | 「`desktop_writing_page` 的 `restart_preparation` 只保留一行委托给模块级 `_restart_preparation`，避免扩大 `writing()` 行数。」 | （删除） |
| 2 | 字符串 | S07 分镜定稿 | 「该调用与上一行写在同一物理行，避免平移 `storyboard_final.py:164` 的裸 `json.loads` 债务标识。」 | （删除） |
| 3 | 字符串 | S10 视频生成 | 「`tests/architecture/_layers.py` 把 `cloud_video`、`local_video` 登记为 L4，`engine` 为 L3，`cloud_video_service` 为 L2；`architecture.md` 的 L2 行原误含 `cloud_video`、`local_video`，已移到 L4 行。」 | 「分层以 `architecture.md` 第 3 节为准。」 |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:228`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:240`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`stage_parallel.py:841` 起）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`stage_parallel.py:140`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:329`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`video_task_state.py:65`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:341`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:368`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:390-400`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`cloud_video_service.py:64`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`cloud_video_service.py:80`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`cloud_video.py:173`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`local_video.py:29`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`local_video.py:178`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`local_video.py:297`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:378`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:394,399,433`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:296`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:388`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:411-416`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:449-452`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:455-456`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`video_task_state.py:9`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`video_source_evidence.py:5`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:471`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:509`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:493`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:457`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`local_video.py:236`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`video_task_state.py:46-52`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`video_task_state.py:20`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`video_lifecycle_service.py:33`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:280`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:371-373`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:283`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`stage_completion_service.py:413`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:17`）」 | （删除） |
| 4 | 正则 | S10 视频生成 | 「（`engine.py:64`）」 | （删除） |
| 5 | 正则 | S10 视频生成 | 「`stage_layout.py:55-56`」 | 「`stage_layout.py`」 |
| 5 | 正则 | S10 视频生成 | 「`stage_path_service.py:27`」 | 「`stage_path_service.py`」 |
| 5 | 正则 | S10 视频生成 | 「`script_contract.py:830`」 | 「`script_contract.py`」 |
| 5 | 正则 | S10 视频生成 | 「`stage_flow.py:60-64`」 | 「`stage_flow.py`」 |
| 5 | 正则 | S10 视频生成 | 「`stage_parallel.py:534`」 | 「`stage_parallel.py`」 |
| 5 | 正则 | S10 视频生成 | 「`stage_flow.py:76`」 | 「`stage_flow.py`」 |
| 5 | 正则 | S10 视频生成 | 「`pet_ui_stages.py:275`」 | 「`pet_ui_stages.py`」 |
| 5 | 正则 | S10 视频生成 | 「`stage_parallel.py:75-78`」 | 「`stage_parallel.py`」 |
| 5 | 正则 | S10 视频生成 | 「`cloud_video_service.py:23-28`」 | 「`cloud_video_service.py`」 |
| 5 | 正则 | S10 视频生成 | 「`cloud_video.py:172`」 | 「`cloud_video.py`」 |
| 5 | 正则 | S10 视频生成 | 「`pet_ui_stages.py:28-30,35-37,99-101`」 | 「`pet_ui_stages.py`」 |
| 5 | 正则 | S10 视频生成 | 「`skill_tools.py:461-464`」 | 「`skill_tools.py`」 |
| 5 | 正则 | S10 视频生成 | 「`skill_tools.py:416,420,488-489`」 | 「`skill_tools.py`」 |
| 5 | 正则 | S10 视频生成 | 「`stage_layout.py:156`」 | 「`stage_layout.py`」 |
| 5 | 正则 | S10 视频生成 | 「`stage_parallel.py:214`」 | 「`stage_parallel.py`」 |
| 6 | 正则 | S10 视频生成 | 「（`:443-445`）」 | （删除） |
| 6 | 正则 | S10 视频生成 | 「（`:446-455`）」 | （删除） |

## 引用改动清单

`git grep` 命中的旧路径只有下面 4 个非历史文件（其余命中是 `STAGE_LOCK_REQUIREMENTS`、KUNLUN Design System 等同名字符串，与本次路径无关，未动；`tasks_round/` 历史结果未动）：

| 文件 | 位置 | 改动 |
| --- | --- | --- |
| `程序/AGENTS.md` | §2.7 适用范围 | `docs/` 下已建 `REQUIREMENTS.md`／`DESIGN.md` → `docs/stages/` 下已建需求与设计 |
| `程序/AGENTS.md` | §2.7 第 5 条 | `写入 REQUIREMENTS／DESIGN` → `写入对应阶段文件（docs/stages/Sxx_*.md 的 ## 需求／## 设计）` |
| `程序/AGENTS.md` | §2.7 第 6 条 | `DESIGN.md 只描述…` → `阶段文件的 ## 设计 节只描述…` |
| `程序/architecture.md` | 258／259／268 行（阶段表） | `需求与设计见 docs/` → `需求与设计见 docs/stages/`（3 处） |
| `程序/architecture.md` | 259 行 | `见 docs/REQUIREMENTS.md REQ-S03-43/44` → `见 docs/stages/S03_初步分镜.md REQ-S03-43/44` |
| `程序/architecture.md` | 332 行 | `见 docs/REQUIREMENTS.md REQ-S02-23` → `见 docs/stages/S02_剧本结构.md REQ-S02-23` |
| `程序/architecture.md` | 471 行（门禁清单） | `REQUIREMENTS 里 ✅` → `docs/stages/ 里 ✅` |
| `程序/distribution_manifest.md` | 44 行（必须排除表） | `程序/docs/REQUIREMENTS.md`、`程序/docs/DESIGN.md` → `程序/docs/README.md`、`程序/docs/stages/**` |
| `程序/维护记录/需求锚定基线.json` | `说明` 字段 | `REQUIREMENTS.md 中标 ✅…` → `docs/stages/*.md 中标 ✅…` |

未改 `AGENTS.md` §5 的「先红后绿」规则正文（DOCS_SPLIT 第 5 条：本任务只同步路径）。

## 门禁改动与「先红后绿」证据

`tests/architecture/test_requirement_traceability.py`：

- 需求来源由单文件 `docs/REQUIREMENTS.md` 改为 `docs/stages/*.md`（`stage_files()`／`requirement_rows()` 两个小函数），四条既有检查的逻辑与断言不变；
- 新增第五项检查 `test_requirements_stay_in_their_stage_file`：每条需求的定义行（`- **REQ-Sxx-nn** 状态`）只许写在对应 `Sxx_*.md`；
- 模块 docstring 的路径同步为 `docs/stages/Sxx_*.md`。

先红后绿（临时文件用完即删，工作区已确认无残留）：

探针 1：在 `tests/_probe_unknown_req.py` 的 docstring 写不存在的 `REQ-S99-99`，门禁退出码 1，`test_tests_do_not_reference_unknown_requirements` 报 `['REQ-S99-99'] != []`。

```text
    ....F
    ======================================================================
    FAIL: test_tests_do_not_reference_unknown_requirements (tests.architecture.test_requirement_traceability.RequirementTraceabilityTests.test_tests_do_not_reference_unknown_requirements)
    ----------------------------------------------------------------------
    Traceback (most recent call last):
      File "D:\漫剧制作助手\.wt\lane_docs\程序\tests\architecture\test_requirement_traceability.py", line 152, in test_tests_do_not_reference_unknown_requirements
        self.assertEqual(unknown, [], '测试引用了阶段文件里不存在的编号')
        ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    AssertionError: Lists differ: ['REQ-S99-99'] != []
    
    First list contains 1 additional elements.
    First extra element 0:
    'REQ-S99-99'
    
    - ['REQ-S99-99']
    + [] : 测试引用了阶段文件里不存在的编号
    
    ----------------------------------------------------------------------
    Ran 5 tests in 0.578s
    
    FAILED (failures=1)
```

探针 2：在 `docs/stages/S14_临时.md` 里把 `REQ-S03-99` 定义在 S14，门禁退出码 1，新检查 `test_requirements_stay_in_their_stage_file` 报错「REQ-S03-99 写在了 S14_临时.md，应写在 S14 的阶段文件里」。

```text
    .F.F.
    ======================================================================
    FAIL: test_new_done_requirement_needs_a_test_anchor (tests.architecture.test_requirement_traceability.RequirementTraceabilityTests.test_new_done_requirement_needs_a_test_anchor)
    ----------------------------------------------------------------------
    Traceback (most recent call last):
      File "D:\漫剧制作助手\.wt\lane_docs\程序\tests\architecture\test_requirement_traceability.py", line 157, in test_new_done_requirement_needs_a_test_anchor
        self.assertEqual(new, [],
        ~~~~~~~~~~~~~~~~^^^^^^^^^
                         '以下 ✅ 需求没有测试锚定：补测试（docstring 写 REQ-xx），或降为 🟡')
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    AssertionError: Lists differ: ['REQ-S03-99'] != []
    
    First list contains 1 additional elements.
    First extra element 0:
    'REQ-S03-99'
    
    - ['REQ-S03-99']
    + [] : 以下 ✅ 需求没有测试锚定：补测试（docstring 写 REQ-xx），或降为 🟡
    
    ======================================================================
    FAIL: test_requirements_stay_in_their_stage_file (tests.architecture.test_requirement_traceability.RequirementTraceabilityTests.test_requirements_stay_in_their_stage_file)
    ----------------------------------------------------------------------
    Traceback (most recent call last):
      File "D:\漫剧制作助手\.wt\lane_docs\程序\tests\architecture\test_requirement_traceability.py", line 146, in test_requirements_stay_in_their_stage_file
        self.assertTrue(
        ~~~~~~~~~~~~~~~^
            rid.startswith('REQ-%s-' % stage),
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            '%s 写在了 %s，应写在 %s 的阶段文件里' % (rid, path.name, stage))
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    AssertionError: False is not true : REQ-S03-99 写在了 S14_临时.md，应写在 S14 的阶段文件里
    
    ----------------------------------------------------------------------
    Ran 5 tests in 0.616s
    
    FAILED (failures=2)
```

改回后复跑：退出码 0，5 个用例 OK：

```text
    .....
    ----------------------------------------------------------------------
    Ran 5 tests in 0.569s
    
    OK
```

## 命令实际计数

| 命令 | 次数 | 结果 |
| --- | --- | --- |
| `python -B doc_split.py build` | 3 | 每次写出 13 个阶段文件＋`docs/README.md`；3 条字符串删除项各命中 1 次，3 条正则删除项分别命中 38／54／2 次 |
| `python -B doc_split.py check` | 2 | 最终 PASS（编号集合、状态符号、文字差异均符合） |
| `python -B -m unittest tests.architecture.test_requirement_traceability` | 4 | 先红 2 次（退出码 1）、改回后 2 次绿（5 用例 OK，退出码 0） |
| `python -B smoke_test.py --architecture` | 1 | 369 用例 OK，144.5s，退出码 0 |
| `python -B smoke_test.py` | 1 | 本轮检查项 8 通过／0 失败，退出码 0 |
| `python -B -m unittest tests.test_distribution_selfcheck tests.test_line_endings` | 1 | 19 用例 OK，退出码 0（验证分发清单改动与新文件行尾） |

## 需裁决事项

1. **新检查的口径**：任务书写「每个 `REQ-Sxx` 只出现在对应的 `Sxx_*.md` 里」。但需求正文里有 3 处跨阶段引用（S03 引用 `REQ-S02-25`、S04 引用 `REQ-S03-20`、S05 引用 `REQ-S02-23`），这些是条文内容，按第 1 条「条目文字原样搬」不能改。因此新检查只针对**定义行**（`- **REQ-Sxx-nn** 状态`），正文里的跨阶段引用放行。若要求严格到「整份文件里不出现他阶段编号」，需要先允许改这 3 处需求正文，请拍板。
2. **行号范围**：第 3 条只要求「设计去实现细节」，所以删除只作用于 `## 设计`；`## 需求` 正文里的行号引用（`file.py:NNN` 形，共 36 处）按「原样搬」保留未删。若要求需求也去行号，请明示（会改动需求文字）。
3. **删掉整句写法说明会连带删掉其中提到的私有函数名**：例如 S01 的「只保留一行委托」那句里提到 `_restart_preparation`，S07 那句里提到 `storyboard_final.py:164`。第 3 条把这类句子列为可删，但它们包含模块/函数名。本次按「整句可删」处理；若要求逐一保留函数名，需要给出保留方式。
4. **含行号的括注按整段删除**：如 「（`engine.py:228`）」 整段删掉，没有保留成 「（`engine.py`）」。理由：这些括注通篇只是行号指引，删后读起来干净；涉及的模块名都在同节顶部的「模块分工」表里作为唯一来源保留。若要求「只删数字、留下模块名」，请拍板，改动量仅是删除项 4 的替换值。
5. **分发清单**：新文件若不在 `程序/docs/README.md`、`程序/docs/stages/**` 下声明，会被 `distribution_build.plan()` 判为 undecided（`test_distribution_selfcheck` 红）。已按 `程序/docs/stages/**` 归入「必须排除」。
6. **结果文件命名**：按 DOCS2 任务书写到 `tasks_round_pending_DOCS_result.md`（不是带轮次号的`tasks_round_N_result.md`）；本轮由派发执行方交付，不领号。

## 改动文件（`git status --porcelain`）

```text
     M "\347\250\213\345\272\217/AGENTS.md"
     M "\347\250\213\345\272\217/architecture.md"
     M "\347\250\213\345\272\217/distribution_manifest.md"
     D "\347\250\213\345\272\217/docs/DESIGN.md"
     D "\347\250\213\345\272\217/docs/REQUIREMENTS.md"
     M "\347\250\213\345\272\217/tests/architecture/test_requirement_traceability.py"
     M "\347\250\213\345\272\217/\347\273\264\346\212\244\350\256\260\345\275\225/\351\234\200\346\261\202\351\224\232\345\256\232\345\237\272\347\272\277.json"
    ?? "\347\250\213\345\272\217/docs/README.md"
    ?? "\347\250\213\345\272\217/docs/stages/"
    ?? "\347\250\213\345\272\217/tasks_round/tasks_round_pending_DOCS_result.md"
```

## 独立验收（Claude，主工作区）

- 车道 diff 应用到 R1734；`architecture.md` 与 R1734 的同一行冲突，合并为两边改动都保留。
- `doc_split.py check` PASS；在 `test_ui_batch3_shell.py` docstring 写入 `REQ-S01-99`，`test_tests_do_not_reference_unknown_requirements` 红，还原后绿。
- `smoke_test.py --architecture` 374 条 0 红；`smoke_test.py` 8/8。
- `test_distribution_selfcheck` 在主工作区红 2 条，原因是仓库根下被 gitignore 的 `工作流任务/`（889 个本地任务书）未声明，属本机环境；在干净车道同一测试 OK，与本轮无关。
- 裁决：①新检查只管定义行，正文跨阶段引用放行——接受；②需求正文里的行号按原样保留——接受（需求文字不动）；③④整句／整段删除——接受，模块名在各阶段「模块分工」表中保留；⑤docs/stages 归开发文档排除——接受。
