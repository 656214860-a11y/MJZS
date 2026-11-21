# R4002 结果：对话区排版接入任务书；任务书补「新增测试文件登记」规则；工程文档任务书勘误
<!-- round-evidence: {"commit_base": "c1978d68", "credential_hits": 0, "evidence_sha256": "a9fffa2d524395cc", "exit": 0, "failed": 0, "passed": 0, "round": 4002, "tests": "docs-only"} -->

## 1. 三问

- 轮次类型：文档轮。只写任务书、阶段文档条目和勘误；没有改代码，没有改测试。
- 测试跑了吗、三个基线过了吗：跑了文档类架构守卫 5 个模块（命令见 §4），退出码 0。本轮不动代码和测试，三个基线不受影响；合入时出口检查再跑一遍。
- 欠账少了吗：没有变化。新增的两条需求是 ⬜（未实现），由新任务书的 CHT-3、CHT-4 落地并补测试锚定。

## 2. 本轮改了什么

| 文件 | 改动 |
| --- | --- |
| `tasks_round/对话区排版接入任务书.md`（新增） | 把已有的排版模块 `ui/skill_note_render.py` 接到「01 剧本准备」页的模型回话上。四张卡串行：CHT-1 对话口径的解析规则；CHT-2 按位置插入的 `insert()`；CHT-3 模型回话改用 `insert()`；CHT-4 流式输出时已写完的行按排版显示。每张卡有允许修改文件、接口契约、测试清单、验收命令、禁止事项、失败报告格式。 |
| `docs/stages/S01_剧本准备.md` | 新增 REQ-S01-99、REQ-S01-100（⬜，来源 2026-11-21 会话 6c3dd20b）和 DES-S01-99、DES-S01-100（标注「未实现」）。文档先行，实现卡落地后把状态改成 ✅。 |
| `tasks_round/工程文档细化任务书.md` | ① DOC-G1 卡的「允许修改文件」补上 `architecture.md` 和 `governance/structure.json` 两处登记，验收、禁止事项、提交命令同步；② §4.0 加第 11 条（见 §3）；③ §2.4、DOC-T1A、DOC-T1D 三处把排版模块的位置更正为 `ui/skill_note_render.py`（`parse`、`apply`）；④ §4.1 错字「不重抱一遍」改为「不重复写一遍」。 |
| `tasks_round/错误代码统一任务书.md`、`tasks_round/L5入口层优化任务书.md`、`tasks_round/减红第二步任务书.md`、`tasks_round/L4界面层优化任务书.md` | 通用规则里各补一条「新增测试文件的登记」（文字相同，见 §3）。 |

## 3. 主控裁决：新增测试文件必须登记

起因：DOC-G1 第一次执行（R3990，车道 `codex/doc-format`）把守卫测试写好了，但卡的「允许修改文件」没列登记处，执行者按规则停下并写了失败报告。错在任务卡，不在执行者。

裁决（对所有任务书生效）：

1. 新增的 `test_*.py` 如果没有同名的生产模块，必须在 `程序/governance/structure.json` 的 `test_ownership` 里登记一条（守卫 `tests/architecture/test_structure.py`，规则 STR006）。
2. 新增的 `tests/architecture/test_*.py` 还必须在 `程序/architecture.md`「当前架构门禁清单」里登记一行（守卫 `tests/architecture/test_agents_md.py`）。
3. 任务卡要求新增测试文件时，这两处登记视为允许：各只加这一处，别的内容不动，提交时把这两个文件一起列上，结果文件写明。

已做的补救：

- DOC-G1 已按这条裁决重新派出（同一条车道接着做，从暂存里取回已写好的测试，领新轮号）。交回后主控要核对：`architecture.md` 只多一行，`governance/structure.json` 只多一条。
- 还没派出的代码卡（L5 的 E1～E4、L4 的 U7b／U7c／U8a／U12、错误代码的 EC-2／EC-3）派单文字里已附上这条。
- 已经在跑的卡（U2～U6、U7a、U7d、EC-1）派单时没有这条。它们如果因为同样的原因停下，按本节裁决补派一次即可，不算执行者失败。

## 4. 验证

在车道的 `程序\` 下运行：

```
PY -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_design_coverage tests.architecture.test_doc_registry_migration tests.architecture.test_agent_doc_budget tests.architecture.test_structure
```

结果：退出码 0；结构检查输出 `finding_count: 0`。

新任务书里的代码事实（排版模块的解析规则、气泡的写入位置、文本控件标签的优先级、同层依赖登记表、字号令牌）都是主控读源码得到的，行号以基线 `93f7765b` 为准；执行者动手前按卡里的「先读」清单自己核对一遍。

## 5. 新增的待用户确认事项

此前的待确认事项见上一份会话交接文件（R3997 合入）。下面是那之后新增的，都还没有答复：

| 事项 | 事实 | 选项 | 用户答复前怎么办 |
| --- | --- | --- | --- |
| 全自动档遇到付费步骤 | 界面文字写「付费或阻塞时会停下」（`ui/pet_ui_support.py:70`）；代码里只有半自动档遇到付费步骤才停（`pet_agent.py` 738–754 行的 `approve`），全自动档会打开资产、视频、配音的无人值守开关并自动提交付费任务（`ui/pet_ui_stages.py` 298–311、`ui/desktop_pet_bridge.py` 54–92） | A（推荐）加一个单独的开关「全自动时也自动做付费步骤」，默认关；B 行为不变，只把文字改成实际行为；C 付费步骤一律停下 | 不改这段代码；写进专题五的「未决事项」 |
| 账号页「推荐模型线路」卡片 | 《07 业务域规格》§7.9.7 写着有，`ui/desktop_account_page.py` 里搜不到；哪一轮去掉的没有查到记录（专题九盘点报告 D-01） | A 有意去掉，改文档；B 恢复卡片 | 不动；写进专题九的「未决事项」 |
| 专题五、六、八、九的讨论题 | 各盘点报告的「给主控的问题建议」一节，每专题不超过 5 题，都带选项和建议 | 见各报告 | 还没有整理成问卷发给用户；写专题册前要先问 |

## 6. 下一步

1. 《对话区排版接入任务书》的 CHT-1～4 可以直接派给执行模型，四张卡在车道 `codex/chat-render` 里按顺序做，做完一次合入。L4-U5（聊天框对齐）如果改了 `ui/desktop_idea_bubbles.py`，等它先合入再开这条车道。
2. DOC-G1 交回并核对后，开写 12 个阶段文档的「接口」「交互」两节。
3. 表格在对话区怎么对齐、「过程与回话区」放在哪、模型回话的组织规则，三件事在新任务书 §4.5 列为待补卡，等用户答复和演示截图后再写。
