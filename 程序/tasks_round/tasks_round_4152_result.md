# R4152 结果：DOC-INPUT-RETIRE 四项界面需求规格落盘（纯文档轮）
<!-- round-evidence: {"commit_base": "73fe052b", "credential_hits": 0, "evidence_sha256": "a0ca90a1b8f11cb0", "exit": 0, "failed": 0, "passed": 0, "round": 4152, "tests": "docs-only"} -->

## 开头三问

- （一）本轮属于哪种类型：功能轮·文档规格（§3.1／§2.7 文档先行）。只改文档、不改任何 `.py`／测试／配置／skills：把 2026-11-23 用户四项界面要求按设计卡落成 REQ／DES 条目。车道 `codex/doc-s05-usage-block`（复用已有干净车道，未新建），工作树 `.agents/worktrees/doc-s05-usage-block`，基点 HEAD `73fe052b`（R4137）。
- （二）测试跑了吗、三个基线：跑了文档门禁（未跑 smoke／selftest／全量，纯文档轮）。`git diff --check` 干净；`python -B -m unittest` 直跑 6 个文档架构测试文件（requirement_traceability、stage_doc_sections、design_coverage、agent_doc_budget、doc_registry_migration、taskbook_closure）共 49 条用例全绿。默认冒烟、`smoke_test.py --architecture`、全量自测均未跑；规范等价命令 `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage doc_registry_migration taskbook_closure` 记入证据文件备查。
- （三）欠账少了吗：规格欠账登记口径不变——全部新条目 ⬜ 未实现（REQ-APP-03/04/05、REQ/DES-S01-106/107、REQ/DES-S03-54、REQ/DES-RET-03/04/05），实现欠账由五张编码卡承接；REQ-S03-50/51、REQ-S11-32 因 2026-11-23 新决定替代 2026-10-20 裁决 B 由 ✅ 降为 🟡（现状与目标分列，非回退）。无新增流程欠账，未动门禁阈值、基线与登记表。

## 改了哪些文件

- `docs/requirements/产品需求规格.md`：新增 REQ-APP-03（共享输入框技能用途）、REQ-APP-04（共享输入框编辑交互）、REQ-APP-05（退役内置阶段 wrapper 技能），均 ⬜，只作全局目标与权威链接（L50/52/54）。
- `docs/stages/S01_剧本准备.md`：新增 REQ-S01-106（`/` 候选同行用途说明卡）、REQ-S01-107（输入流畅性：输入法／撤销／粘贴／自适应／完整候选／防重）与 DES-S01-106/107，均 ⬜，标注为十三阶段共享输入框目标；测试锚定行登记待编码轮补锚（L131-132、232-233、291）。
- `docs/stages/S03_初步分镜.md`：新增 REQ-S03-54（发送启动制作，移除唯一「手动制作分镜」按钮）与 DES-S03-54（`send_storyboard` 窄接口建议），均 ⬜；REQ-S03-50/51 由 ✅ 改 🟡 并链接 REQ-RET-03/04/05；REQ-S03-53 保持 ✅ 仅改用户可见入口措辞；DES-S03-50 改 🟡、DES-S03-52 补现状／目标分述；「已裁决」段改为「已被替代的决定」（L50-57、100-106、137）。
- `docs/stages/S11_配音与字幕.md`：REQ-S11-32 由 ✅ 改 🟡——「pipeline 总入口权威」属设计卡第 7 条命中的现行断言，链接 REQ-RET-03/05，未重写其他段落（L46 一带）。
- `docs/specs/02_接口与详细设计.md` §6：新增 REQ-RET-03（仅明确清单十三项内置 wrapper 退役技能身份）、REQ-RET-04（配置兼容迁移）、REQ-RET-05（阶段方法与 I/O 先迁非注册规则资源 `配置/工作流/阶段规则/<stage_id>.md`）及 DES-RET-03/04/05，均 ⬜；REQ-RET-01 加注「保留其余内置技能」被十三项例外取代（L226、235-237、261-263）。
- `docs/specs/08_对话式交互与输出排版.md`：§8 现状表补「共享输入框用途与编辑」「S03 发送启动制作」两行（现状标识保留、新目标链接 ⬜）；新增 §13「共享输入框交互」与「工程参考与证据边界」（L116、124、180-181、197 起）。
- `docs/specs/README.md`：§4 覆盖映射表补 REQ-APP-03/04/05 三行（→ 08 §13、02 §6），见「如实说明」一。（L63-65）
- `docs/records/对话需求追溯.md`：表尾追加 2026-11-23 四项摘要与规格编号（用途说明／S03 发送／输入流畅性／明确清单退役），均标 ⬜ 未实现。
- `tasks_round/tasks_round_4152_result.md`：本文件。

## 五张编码卡（主树 `.agent-tmp/`，主会话亲写，本轮未改）

- `D:\漫剧制作助手\.agent-tmp\需求设计-card-UX-SLASH-HINT.md`（REQ-S01-106 用途说明卡）
- `D:\漫剧制作助手\.agent-tmp\需求设计-card-UX-S03-SEND.md`（REQ-S03-54 发送制作）
- `D:\漫剧制作助手\.agent-tmp\需求设计-card-UX-INPUT-FLOW.md`（REQ-S01-107 输入流畅性）
- `D:\漫剧制作助手\.agent-tmp\需求设计-card-RET-PIPELINE-COMPAT.md`（REQ-RET-03/04/05 兼容与非注册规则）
- `D:\漫剧制作助手\.agent-tmp\需求设计-card-RET-PIPELINE-PACK.md`（十三项内置 MD 清除与分发收口）

## 命令与结果

工作目录均为车道 `程序\`，解释器 `D:\漫剧制作助手\运行环境\Python\python.exe`（工作树无自带运行环境，用主工作区解释器）。

| 命令 | 结果 |
| --- | --- |
| `python.exe -B scripts\dev.py claim` | 领到轮次 4152（归属本工作树） |
| `git diff --check` | 干净，exit 0 |
| `python.exe -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_stage_doc_sections tests.architecture.test_design_coverage tests.architecture.test_agent_doc_budget tests.architecture.test_doc_registry_migration tests.architecture.test_taskbook_closure` | 首轮 49 条中 design_coverage 1 红（REQ-APP-03/04/05 无覆盖落点）；补 `docs/specs/README.md` §4 三行后复跑 49 条全绿，exit 0 |
| `python.exe -B scripts\dev.py commit -m "R4152: DOC-INPUT-RETIRE 四项界面需求规格（共享输入框用途说明/S03 发送制作/输入流畅性/13 个内置 wrapper 退役）" --agent sidekick <本轮文件>` | 见下方提交记录 |

检查输出摘要（≤6000 字节）：`D:\漫剧制作助手\.agent-tmp\DOC-INPUT-RETIRE-evidence.txt`。

## 如实说明

- （一）**范围外补一处登记**：设计卡「权威文档范围」9 项未列 `docs/specs/README.md`，但 `test_design_coverage` 硬性要求 PRD 每个 `REQ-APP-*` 在 specs/README.md §4 覆盖映射表有落点行（REQ-APP-01/02 同例）。不补则文档门禁红、合入出口 CI 必失败。已按既有行格式补 3 行纯登记（册号 §章节 → 覆盖方式），未新增任何规格内容；若评审认为越权，删该 3 行即回退，但 REQ-APP 条目须另找落点。
- （二）**未产出任务完成文件**：规则 35／runbook §16 的同名任务完成文件以 `tasks_round/<主题>任务书.md` 为前提；本任务由 `.agent-tmp` 设计卡驱动，tasks_round 下无对应任务书（master 与本车道均核实）。孤儿完成文件会使 `test_taskbook_closure` 真实仓库检查与提交闸（`declares_closure` 命中暂存的 `任务完成/*.md`）拒绝。R4137 同类文档规格轮亦无任务书、无完成文件。是否需要补任务书＋完成文件请 lead 裁定。
- （三）设计卡第 7 条命中：S11 REQ-S11-32 是唯一被改的跨阶段「pipeline 总入口权威」断言（S03-50/51 属本卡点名条目）；未批量替换 pipeline 字样，未触碰 S05-USAGE 未合入内容。
- （四）全部新条目均 ⬜／🟡，无 ✅；REQ-S03-53 API 行为、采用链、三虎入口不变；未做真实付费调用验证。
- （五）未验证项：Windows 拼音 IME、GUI 几何与生命周期均未实测（规格明示留验证项）；产品代码未实现，五张卡均未派发；`smoke_test.py`、`run_selftests.py`、全量自测未跑（纯文档轮）。

## 未覆盖项

- 未跑默认冒烟 8/8、架构门禁全量（700 条）、全量自测——纯文档轮按卡面只跑文档检查入口；未 push、未 merge、未动 project_status.md／AGENTS.md／产品代码／测试／skills／分发清单。
