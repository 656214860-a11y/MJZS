# R4162 结果：FIX-S03-SEND-GATE——初步分镜发送门禁改用「有可用结构稿」判定
<!-- round-evidence: {"commit_base": "6997ae43", "credential_hits": 0, "evidence_sha256": "8fca6a949bf366c0", "exit": 0, "failed": 0, "passed": 100, "round": 4162, "tests": "run_selftests.py -k shared_input_ui shared_input_gate_s03 script_structure_scope req_anchor_s02 critical_chains stage_doc_sections requirement_traceability design_coverage"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。卡 W7-FIX-S03-SEND-GATE，车道 `codex/fix-s03-send-gate`，基准 `6997ae43`。用户 2026-11-23 反馈：初步分镜页点击发送提示「剧本结构清单未通过核验」，是原来的机制卡住了流程。根因：S03 发送门禁 `upstream_send_error` 的兜底分支复用上游 `script_structure` 的 `completion_evidence`（REQ-S02-23），而 R4119 后 S02 认模型按集写的结构稿，这类稿没有派生的三份清单，完成核验永远不通过，导致「选得到稿却发不出去」。修法按卡面裁定：`stage_completion_service` 新增窄函数 `storyboard_send_readiness`，S03 门禁只对它放行与否负责；`completion_evidence` 一字未动。
- （二）测试跑了吗、三个基线：跑了。定向命令 `run_selftests.py -k shared_input_ui shared_input_gate_s03 script_structure_scope req_anchor_s02 critical_chains stage_doc_sections requirement_traceability design_coverage` 改前 8 条红（原因见下），改后「共 100 条用例，5.5 秒；0 个文件有红」「ALL TESTS PASSED」，退出码 0。架构门禁 `smoke_test.py --architecture`「Ran 700 tests in 283.311s」「OK」，退出码 0。默认冒烟与全量自测本卡未要求，未跑。
- （三）欠账少了吗：没有新增欠账，也没有减少既有欠账。本轮只修 S03 发送门禁一处；`completion_evidence` 的 S02 判定、三虎自动链依赖均未动，相关回归（test_script_structure_scope、test_req_anchor_s02、test_critical_chains）保持绿。

## 缺陷复现（改前红）

先写测试后改产品。改前定向命令：8 个匹配测试文件 / 9 路工作单元 / 100 条用例，2 个文件有红，共 8 条：

- `test_shared_input_gate_s03`（新建文件，后因 STR006 迁入 `test_shared_input_ui.py`，见「如实说明」一）：6 条红，全部为 `AttributeError: module 'orchestrator.stage_completion_service' has no attribute 'storyboard_send_readiness'`——新函数尚不存在。
- `test_shared_input_ui.UpstreamGateTests`：2 条红，失败原文正是卡面缺陷：
  - `test_s03_episode_script_does_not_block_send`：`AssertionError: '请先完成/确认「剧本结构」阶段（剧本结构清单未通过核验：character_manifest.json 还没产出）' != ''`——按集写的结构稿明明可选，发送门禁却被 S02 完成核验拦下。
  - `test_s03_without_script_blocks_with_guidance`：`AssertionError: '结构剧本' not found in '请先完成/确认「剧本结构」阶段（没有找到可读取的剧本结构成果）'`——旧兜底文案不含新指引语。

其中 2 条 UI 红直接复现了缺陷机理（S03 发送复用 S02 完成核验）；6 条 readiness 红是新函数未实现的先红形态。同一批断言迁入 `test_shared_input_ui.py` 后全部转绿。

## 改了哪些文件（文件:行号）

- `程序/orchestrator/stage_completion_service.py`：新增 `storyboard_send_readiness(project)`（813–851 行），返回 `(可发送, 说明, 已自动补清单)`。用 `script_contract.structured_script_paths` 取来源仍可用、mtime 最新的一份结构稿；无可用稿或非结构稿 → 唯一拦截情形，说明「还没有可用的结构剧本，请先到「剧本结构」页确认一份结构剧本，再回来发送」。有稿先跑 `structure_manifest_problems`：无问题直接放行；有问题时用 `structure_manifests` 判断这份稿有没有可派生名单，有才 `write_structure_manifests` 补写一次（只写 `02剧本结构/output/` 三份清单，沿用原子写入）再核验，通过返回「已按当前结构剧本补全清单」、`已自动补清单=True`；派生为空（按集稿）或补写后仍有问题，返回「结构剧本清单未能自动生成（原因：第一条问题），本次不影响分镜制作；需要时可回「剧本结构」页重新整理」且 `可发送=True`。`completion_evidence` 未动。
- `程序/desktop_shared_input.py`：`upstream_send_error` 增加可选参数 `status=None`（82 行），docstring 补一行说明（88 行）；新增 storyboard 分支（122–130 行）：上游为 `script_structure` 且未 skipped 时改调 `storyboard_send_readiness`，不可发送才返回说明（兜底文案同上），可发送且有说明时经 `_say(status, note)` 写状态栏；`SharedStageInput.send()` 调用点传入 `self.status`（972 行）。其他阶段分支与发送流程未动。
- `程序/tests/test_shared_input_ui.py`：`UpstreamGateTests` 新增 2 条（543–576 行：按集稿不拦且说明进状态栏、无结构稿拦且文案不含「清单未通过核验」）；新增 `StoryboardSendReadinessTests`（579–664 行，6 条：清单齐全静默放行、清单缺失自动补写、清单过期按稿重写、按集稿只提示不拦、无稿拦截、来源已删不算可用）。全部用临时目录，不建真实 Desktop/Tk 窗口（本类不含 Tk；所在文件由运行器走隐藏桌面）。
- `程序/docs/stages/S03_初步分镜.md`：新增 REQ-S03-55 与 DES-S03-55（47 行、105 行附近），锚定表加一行（137 行）。
- `程序/docs/stages/S02_剧本结构.md`：REQ-S02-21② 局限说明补一句指向 REQ-S03-55（25 行）。
- `程序/tasks_round/tasks_round_4162_result.md`：本文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k shared_input_ui shared_input_gate_s03 script_structure_scope req_anchor_s02 critical_chains stage_doc_sections requirement_traceability design_coverage`（改前，产品未改） | 退出码 1；「共 100 条用例，4.1 秒；2 个文件有红」，8 条红（原因见上） |
| 同上（改后） | 退出码 0；「定向：忽略增量台账，执行 7 个匹配测试文件」「共 100 条用例，5.5 秒；0 个文件有红」「实际跳过 0 条用例」「ALL TESTS PASSED」。尾部：`test_shared_input_ui#1 2.7 秒 / 16 条`、`test_shared_input_ui#2 1.8 秒 / 14 条`、`test_shared_input_ui#3 0.1 秒 / 7 条` |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（中途曾红两条，修完后重跑） | 退出码 0；「Ran 700 tests in 283.311s」「OK」「✅ 架构治理测试：tests/architecture」 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 退出码 0，轮次 4162 |

注：改后定向命令显示「7 个匹配测试文件」——`shared_input_gate_s03` 关键词已无对应文件（见下），其用例由 `shared_input_ui` 关键词覆盖，总用例数仍为 100。

## 如实说明

- （一）测试文件位置偏差（对卡面的唯一偏离）：卡面允许新建 `程序/tests/test_shared_input_gate_s03.py` 并要求先红后绿。该文件按卡建出并看到 8 条红后，产品修复完成时架构门禁报两条与本改动相关的红：`desktop_shared_input.py: 1004 行 > 上限 1000`（模块行数棘轮，新文件压到 1000 行整后消除），以及 `STR006 程序/tests/test_shared_input_gate_s03.py ownership`——结构检查要求新测试文件与某个生产模块同名，或在 `governance/structure.json` 登记归属；登记表不在允许修改清单内。同类处境 R4099/R4108 结果文件有先例（登记表不可改时调整文件归属）。因此把 6 条 readiness 用例原样迁入允许修改的既有文件 `tests/test_shared_input_ui.py`（`StoryboardSendReadinessTests`），删除新文件；S03 文档锚定表同步改为 `test_shared_input_ui`（`UpstreamGateTests`、`StoryboardSendReadinessTests`）。断言场景与改前红测一一对应，无删减、无弱化。
- （二）`desktop_shared_input.py` 现为 1000 行，正好压在棘轮上限（判定是 `> 上限` 才红）。后续再向该文件加行会触发棘轮，需要拆分或换模块——本卡范围内不处理。
- （三）`upstream_send_error` 新增的 `status` 参数带默认值 `None`，既有两参调用点不受影响；`_say(None, text)` 内部已判空，不会因未传状态栏而崩。
- （四）`storyboard_send_readiness` 内 `structure_manifest_problems` 首次调用未单独 try（该函数内部对读盘错误有兜底，正常不会抛）；门禁侧对整个 readiness 调用保留了 try/except 兜底，与相邻 `completion_evidence` 分支风格一致。
- （五）被拒绝的命令：无。未使用 git add／git commit／push／merge／stash／checkout 等禁止命令。

## 未覆盖项

- 未跑默认冒烟、未跑全量自测（卡面只要求上述两条命令）。
- 未在真实桌面窗口里端到端点过「发送」按钮；门禁经 `upstream_send_error` 与 `storyboard_send_readiness` 直接断言覆盖，`send()` 只改了调用点传参。
- 补写清单只在「结构稿可派生出非空名单」时发生；多集稿、手写混合版式等更冷门稿型只覆盖了按集稿（派生为空）与标准版式（派生成功）两端。
- 用户真实项目里是哪一种触发场景（按集稿／清单过期／其他）未核实，卡面亦注明拿不到项目文件。
- `shared_input_gate_s03` 关键词在定向命令里已无匹配文件；若后续卡要求恢复该文件名，需要先解决 STR006 归属登记。
