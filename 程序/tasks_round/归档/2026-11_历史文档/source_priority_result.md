# 剧本准备资料优先级与冲突裁决（功能轮）

- **轮次类型**：§3.1 功能轮（L2/L3 提示词与上下文装配）。
- **三个问题**：本轮属于 §3 哪种类型＝功能轮；测试跑了吗＝跑了（新测试 11/11、架构门禁 56/56、默认冒烟 8/8、test_workflow 98/98、循环依赖+分层 8/8）；欠账少了吗＝本任务不产生新欠账，未新增/未删除历史欠账条目。
- **提交**：本 worktree 任务由调度方提交，本轮不自行 commit（任务书明确「不提交（调度方提交）」）。

## 一、优先级规则的唯一定义位置

`程序/workflow_context.py`（L2，上下文装配处）末尾新增一段，是全链路唯一权威：

- `PREPARATION_SOURCE_ORDER = ('附档', '项目设定', '项目大纲', '角色卡')` —— 生成链固定排序（附档最低）。
- `_PREPARATION_CONFLICT_RULE` —— 冲突裁决措辞（冲突取高、低者补缺、不得覆盖高结论）。
- `preparation_priority_block(present, *, user_edited=())` —— 按「实际存在资料」从低到高编号列出的动态段；空集返回空串。
- `preparation_source_priority(documents, creative_text='')` —— 由阶段文件记录（含 `user_edited`）与创意输入附档边界（`【附档：`）拼动态段。
- `preparation_priority_rule()` —— 桌面／命令行任务书用的静态全链规则。

措辞与排序只在此一处；API 与桌面／命令行两条路径均从这里取值，未在别处另写一份。

## 二、各生成路径注入点清单

| 路径 | 注入点 | 形式 |
| --- | --- | --- |
| API（`writing_api._preparation_task`） | 拼接「前三阶段每次只输出一份…」后，追加 `workflow_context.preparation_source_priority(documents, creative)` | 动态段：列本次实际存在的附档/设定/大纲/角色卡（从低到高），并标注 `user_edited` |
| 桌面／命令行（`workflow_tasks.script_prompt` writing 分支） | 「暂不调用图片、视频或分镜制作。」之后追加 `workflow_context.preparation_priority_rule()` | 静态全链规则 |

说明：`script_followup`（续发路径）不重复注入——它延续初始任务书已加载的规则，只发本轮指令与改动材料，不再整段复制；桌面续发台账（REQ-S01-69）按完整/增量稿语义不变。

## 三、改动文件

- `程序/workflow_context.py`：新增唯一权威常量与 3 个纯函数（+63 行）。
- `程序/writing_api.py`：`_preparation_task` 追加动态优先级段；模块级 import 行并入 `workflow_context`（净 0 行，仍 1372 行，未破体量棘轮）。
- `程序/workflow_tasks.py`：`script_prompt` 注入静态规则（+2 行）。
- `程序/docs/stages/S01_剧本准备.md`：新增 `REQ-S01-78`（需求）与 `DES-S01-78`（设计，标注实现 REQ-S01-78）。
- `程序/tests/test_preparation_source_priority.py`：新增测试（12 个 REQ-S01-78 锚点）。

## 四、测试命令与实际结果

解释器：`D:\漫剧制作助手\运行环境\Python\python.exe`（本 worktree 无 `运行环境`，用主树绝对路径）。

| 命令 | 结果 |
| --- | --- |
| `python -B -m unittest tests.test_preparation_source_priority` | 11/11 通过（0.004s） |
| `python -B run_selftests.py -k ratchet requirement_traceability layers` | 共 56 条用例、24.1 秒、0 红、实际跳过 0 |
| `python -B -m unittest tests.architecture.test_no_circular_import tests.architecture.test_layers` | 8/8 通过 |
| `python -B smoke_test.py`（默认冒烟） | 8/8 通过 |
| `python -B -m unittest tests.test_workflow` | 98/98 通过 |
| `python -B -m unittest tests.test_script_agent_delivery_assembly tests.test_claude_writing_session tests.test_writer_style_agent_delivery tests.test_agent_current_script_notice tests.test_script_agent_delivery_paths` | 通过（`test_workflow_writing_stages` 混入其中时 36 项里 2 项环境缺件报错，见下） |
| `python -B -m unittest tests.architecture.test_module_size_ratchet` | 通过（`writing_api.py` 1372 行 = 上限 1372） |
| `python -B tests/architecture/test_requirement_traceability.py --find REQ-S01-78` | 锚定到 `test_preparation_source_priority.py` 12 处 |

### 环境缺件导致的红灯（与本任务改动无关，需区分）

`run_selftests.py -k writing preparation idea_chat workflow_context` 与 `smoke_test.py --affected writing workflow_context workflow_tasks` 中的红灯全部是 **`skills/00全流程SKILL/AIGC创作全流程/sd-decision-engine/SKILL.md` 缺失**（`pipeline-script-preparation.skill.md` 引用它，`freeze_skills` 报「SKILL 引用缺失」）。核实：主树 `D:\漫剧制作助手\程序\skills\00全流程SKILL\...` 存在该文件，而本 worktree 的 `skills/00全流程SKILL` 技能子模块未完整检出。受影响的是任何经 `capture_request`→`freeze_skills` 的用例（`test_writing_api.py`、`test_idea_chat.py`、`test_workflow_writing_stages.py` 的 2 条），与本次新增的优先级逻辑无关。

## 五、断言处理声明

**断言未动**：未修改任何既有测试的断言、skip 或 mock 目标；仅新增 `test_preparation_source_priority.py`。契约（`preparation_state.json` 结构、分层、发布边界）未变更，故无旧测试需要同步。

## 六、未验证项

- **真实模型是否遵守优先级规则未做端到端验证**：本轮只把规则注入请求正文并验证文本/排序正确，未真实调用 API/桌面模型确认其是否按「冲突取高、低者补缺」执行。
- 桌面路径（`script_prompt`）的静态规则为全文注入，实际由 Agent 读取文件后自行取舍，未做桌面实机验证。
- 时间判定的回退口径：当前文档记录不含时间戳，优先级按生成链固定排序，`user_edited` 取自 `preparation_state.json` 既有字段；文件 mtime 回退未在本轮路径触发（因排序无需 mtime），未做 mtime 回退的专项测试。
