# R4271 结果：SANHU-CONTEXT-GAPS 三虎快照带项目事实（计数、缺口、门禁）
<!-- round-evidence: {"commit_base": "c247e8df", "credential_hits": 0, "evidence_sha256": "2cef365326cb18b5", "exit": 0, "failed": 0, "passed": 107, "round": 4271, "tests": "run_selftests.py -k pet_context_facts pet_agent pet_ui_voice"} -->

> 由合入接管会话代提交，原执行者中断。改动为车道 `codex/sanhu-context-gaps` 里未提交的工作区内容，接管会话未改产品逻辑，只做验证、补结果文件并提交合入。

## 开头三问

- 本轮属于功能接线：新增 `程序/ui/pet_context_facts.py`（`facts_snapshot(voice)` 返回 `counts`／`gaps`（最多 4 句）／`blocked`），`PetAgent` 增可选 `facts` 回调，`context()` 在其返回非空字典时多带 `facts` 键；宿主 `ui/pet_ui_voice.py` 的 `projects_brief()` 把快照挂到 agent。
- 测试跑了吗：`run_selftests.py -k pet_context_facts -k pet_agent -k pet_ui_voice` 在车道工作树全绿（9 路并行，退出码 0，`test_pet_context_facts` 4 条、`test_pet_agent` 七分片 93 条、`test_pet_agent_error_wiring` 10 条）。出口 CI 由合入命令在车道工作树执行。
- 欠账少了吗：无新增欠账；未弱化、未删除、未跳过任何既有测试。

## 改动文件

- `ui/pet_context_facts.py`（新）
- `pet_agent.py`：`Agent.__init__` 增 `self.facts`；`context()` 末尾取 facts，异常记 `self.errors`
- `ui/pet_ui_voice.py`：`projects_brief()` 挂 `facts` 回调
- `tests/test_pet_context_facts.py`（新，4 条）、`tests/test_pet_agent.py`（新增 `FactsContextTests` 4 条）

## 未验证

- 没有真调模型看回答质量（卡面已注明）。
