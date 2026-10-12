# R1332：修复轮——剧本准备页 API 对话支持“回退到已确认阶段重新创作”，失效前二次确认

类型：修复轮（§3.2）。中央轮次 1332。来源：用户直接指定的修复条目。用户未给出只读诊断报告路径与 J/K 条目编号，本轮按用户逐条列出的执行口径实施（信息缺口，照实记录，不补造来源报告）。

## 三个必答
1. 本轮属于 §3 哪种类型？——§3.2 修复轮（修阻塞：对话里无法触发既有回退能力）。
2. 测试跑了吗？三个基线过了吗？——跑了。定向 `--affected writing_api writing_restart workflow_tasks stage_execution_service`：0 个文件有红（465 秒，含 test_writing_api、test_writing_restart、新增 test_writing_restart_intent）；默认冒烟 8/8；架构门禁 312/312 OK。全量未跑：本轮无“轮次号 − last_full_safe_all_round ≥ 5”，也未改动启动路径／Tk 控件生命周期／删除语义／层级登记表，不满足 §5 的全量升级条件。
3. project_status.md 的欠账少了吗？——未新增欠账，也未清偿既有欠账。

## 根因
- `writing_api._preparation_step()` 的实现只把阶段意图交给模型判断：system/task 提示模型在“修订当前阶段”和“推进下一阶段”（输出 `{"next_stage":"自然剧本"}`）之间选择，程序侧没有任何回退分支。
- 真正的回退能力早已存在：`writing_api.restart_preparation(project, stage, publish=...)`（经 L3 `stage_execution_service.restart_writing_preparation` 暴露），它把 `state['revision'] = {'documents': documents[:index]}`，使该阶段起重新进入“待确认”。但唯一调用方是桌面右键菜单（`desktop.py` 的 `从本阶段重新创作`），对话路径调不到。
- 用户说“回到设定阶段重新写”一类回退话时，模型没有对应动作，只能继续在“修订当前阶段”上打转。

## 实现（只改 L2 `writing_api.py`，+99 行；不新增生产模块）
- 新增意图识别 `preparation_restart_intent(text)`：取用户原话首行、去尾标点，先按阶段别名定位目标阶段（`_preparation_stage_alias`，取最长别名，避免“项目设定/设定”歧义），再判定是否回退指令。
  - 与 Agent 路径同口径：`first` 交给 `workflow_tasks.writing_restart_requested()`（既有“重新创作X”短语识别），命中即回退。
  - 在同一短语模式（只认开头短语、附件与正文里的字样不算、`fullmatch`）上补充回退说法：`_PREPARATION_BACK`（回到/返回/退回…X[阶段][重新写/重写…]）与 `_PREPARATION_REWRITE`（X[阶段][要/需要]推翻|推倒|重写|重做|重来…）。覆盖用户给的三例“回到设定阶段／大纲要重写／角色卡推翻重来”，以及“回到设定阶段重新写”“把大纲推翻重来”“重新创作项目设定”“请重新生成角色卡。”。
  - 未点名阶段（如裸“重新创作”）返回 None，交回原有流程——回退必须知道目标阶段，`restart_preparation` 的入参就是阶段名。
- `_preparation_restart_affirmative(text)`：二次确认词（确认/确定/是/好的/可以/继续/同意…），仅首行整词匹配。
- `_preparation_rollback(stage, documents)`：复用 `_preparation_state()` 已按 SHA256 校验过的 `documents` 与 `confirmed` 标记（不另写失效判断）算出“回退会使哪些已确认阶段失效”：目标阶段的 `prefix` 必须齐全且已确认（与 `restart_preparation` 同一前置条件），失效清单为目标下标起所有 `confirmed` 的阶段；清单为空（没有已确认的下游）返回 None。
- `_preparation_step()` 新增分支（放在 `index == len(PREPARATION_STAGES)` 提前返回之前，保证三个阶段都确认后依然能触发回退）：
  - 命中回退意图且失效清单非空：只回复一条程序生成的说明（列出将失效的阶段），把 `state['pending_restart'] = {'stage', 'invalidates'}` 落盘，本轮不调用模型。
  - 存在 `pending_restart` 且本轮是确认词：先清 `pending_restart` 落盘，再调用既有 `restart_preparation(project, stage, publish=response_publisher)`，然后重读状态继续本轮（模型将改写回退目标阶段）。
  - 存在 `pending_restart` 但既不是确认词也不是新的回退意图（不确认）：清 `pending_restart`，按原有流程继续——不执行回退。
- 未改 `restart_preparation()` 行为；未改 UI（`desktop.py` 右键菜单路径不变）；未改 `workflow_tasks.writing_restart_requested`（仅调用）。

## 范围与调用方核验
- 生产改动仅 `程序/writing_api.py` 1 个模块（§3.2 只改根因模块）。
- `writing_restart_requested` 只被 `preparation_restart_intent` 调用，未改其定义，`test_claude_writing_session.py` 的既有断言未动。
- `desktop.py`、`stage_execution_service.py`、`workflow_tasks.py` diff=0。
- 新增测试文件 `程序/tests/test_writing_restart_intent.py`（4 条）：三选一意图识别（修订/推进不被劫持 + 回退命中）、回退二次确认全流程（确认前不调模型、确认后才真回退）、不确认不执行、无已确认下游时不拦截。

## 验证
- 定向：`smoke_test.py --affected writing_api writing_restart workflow_tasks stage_execution_service` → 0 个文件有红（465 秒；含 `test_writing_api`、`test_writing_restart`、`test_writing_restart_intent`、`architecture.test_writing_api_json_boundary` 等）。
- 默认冒烟：`smoke_test.py` → 8/8。
- 架构门禁：`smoke_test.py --architecture` → 312/312 OK（新增测试文件在 `ROOT.rglob('*.py')` 扫描范围内，实测未触发任何边界门禁）。
- 未跑全量：见“三个必答”2 的判定。

## 自审（§4.2）
1. 验收：对话路径新增第三分支可触发既有回退；回退前必须先说明失效并二次确认；确认后才调用 `restart_preparation()`；不确认不执行；`restart_preparation()` 行为未改；UI 未改——均达成，并有定向用例覆盖。
2. 范围：只改根因模块 `writing_api.py`；未改测试断言迁就实现（既有用例全绿，新断言为新增）；未改用户数据；未动 `.agent-handoff/`。
3. 验证：定向、默认冒烟与架构门禁为本轮实测绿；全量未跑并已注明理由。
4. 新问题：`pending_restart` 是 `preparation_state.json` 的新增可选键，`_preparation_state` 的校验不拒绝未知键、`restart_preparation`/`preparation_file_labels` 不受影响；未新增文件路径。潜在残余风险：用户在二次确认前改用桌面右键“从本阶段重新创作”，可能留下过期 `pending_restart`；下次对话确认时会按该阶段再设一次 revision（幂等，不破坏已采用版本），如后续需要可在右键入口清理。

## 收尾提交
- 已提交；轮次类型：修复轮。提交首行：`R1332: 修复轮——对话路径支持回退到已确认阶段重写并二次确认`。
- 工作树因预提交门禁（只有 master 可提交 `project_status.md`）不把状态页并入本提交。
