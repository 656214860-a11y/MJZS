# R1335：阶段④自然剧本按集解析与分集增量账本

类型：功能轮（§3.1）——为阶段④自然剧本新增按集解析与分集增量追踪，让后续生成只注入「有改动的集」正文，不再整篇重读。中央轮次 1335（沿用共享计数器最新值；开工时原领 1331，随后被并行轮次超过，按规则 27 重新认领）。

## 三个必答
- 本轮类型：功能轮（§3.1，默认）。
- 测试：跑了，全是本轮实测。定向：`tests.test_script_contract` 52 条（新增 `EpisodeIncrementalTests` 5/5 全绿，仅 1 条既有红＝缺 gitlink）、`tests.test_writing_api` 52 条（新增 1 条全绿，30 error＋2 failure 与改动前基线逐字同形）、`tests.test_script_agent_delivery_assembly` 9/9、架构棘轮 `tests.architecture.test_unification_ratchet` 3/3；默认冒烟 `python smoke_test.py` 8/8 通过。受影响门禁 `--affected script_contract writing_api script_agent_delivery_assembly`：115 条 / 6 段红，红点全部落在缺失的 `skills/00全流程SKILL/AIGC创作全流程` gitlink（77 处 `screenplay-gate-engine.md` 缺文件＋3 处断言），与本轮无关（见「验证」）。
- 欠账：本轮不写 `程序/project_status.md`（非 master，pre-commit 拒绝）；状态页轮次头与正文未同步，属跨分支欠账，待合并 master 后由收口轮补齐。

## 问题
- 阶段④自然剧本已按 `# 第{集数}集：{标题}` 分段输出（`skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md:128`），但系统只把整篇当不透明大 blob：`structure_script()`（改动前 `script_contract.py:419`，现 604）每次整篇重排，没有任何按集解析或变更追踪。
- 用户改前几集后要求「参考这些修改继续写」，模型只能整篇重读或靠对话口头描述，无法得知「哪几集变了、变成什么」。

## 实现
- `script_contract.py` 新增与 02 场次解析完全平行的按集解析与账本能力（不动 `structure_script()`）：
  - `split_script_episodes()`：用 `_EPISODE_HEADING` 识别 `# 第N集：标题`，容错全半角冒号、零填充、`#` 级数与标题文字缺失；返回 `{集号: 正文块}`（保留标题行）；首个标题前的正文记 `未分集`；无标题→整篇一个 `未分集` 块；空→`{}`。不报错、不阻断。
  - `episode_digest()` / `episode_ledger_path()` / `read_episode_ledger()` / `write_episode_ledger()`：账本落 `write_dir(project,'script')/'剧本分集增量账本.json'`（路径口径同 `natural_script_selection_path()`），记录每集 `sha256` 与生成时其余各集的 `based_on` sha256 快照；读写走 `agent.core.read/save`；坏账本／缺失一律返回空账本。
  - `episode_change_report()` / `episode_reference_block()`：比对当前分集与账本，只贴变化集正文，未变集只列集号；账本缺失或从未记录（首次）→ 退化为把全部已有集正文当参考（等价旧全量行为）。
  - `script_episode_baseline()` / `record_episode_ledger()`：基准正文取「最新可见自然剧本」；记录时对改动／新增集写 `based_on`＝生成前版本其余集指纹，未变集保留旧记录。
- 触发链逐行核实：阶段④续写入口＝`desktop.py:1875 reply_to_writing` → `stage_execution_service.py:277 reply_to_writing` → `writing_api.py:804 reply()`。`_preparation_step()`（`writing_api.py:681`）只产阶段①②③，进入自然剧本时返回 `{'next_stage':'自然剧本'}` 明确「不在本轮重复撰写自然剧本」（`writing_api.py:721`），不是接入点。`idea_brief_form.py`／`idea_semantic_brief_service.py` 仓库内不存在（实际为 `idea_chat.py` 的 `receive_brief`／`semantic_brief_request`），只产创作简报，同样不写自然剧本。
- `writing_api.py` 接入：调用前 `reply()` 两条主路径都注入 `_episode_reference_hint()`（四角色走 `supplement`，直连 API 走 `task +=`）；调用后统一在唯一发布点 `_save_formal_script()` 用生成前捕获的 baseline 调 `_record_episode_ledger()` 更新账本。新增函数全部 try/except（OSError/ValueError/TypeError），账本问题绝不阻断生成。
- `workflow_tasks.py` 本地 Agent 路径：新增 `_episode_change_notice()`，在 `script_prompt`／`script_followup` 的 `agent_delivery` 分支紧跟 `_AGENT_READING_SCOPE` 注入，只给「哪几集有改动」的集号列表，不暴露账本文件与实现细节。

## 验证
- 三类退化场景定向覆盖（任务硬要求）：`EpisodeIncrementalTests`——(1) `test_split_is_tolerant_and_falls_back_to_one_unsplit_block`（标题容错＋无标题整篇一个「未分集」）；(2) `test_missing_ledger_degrades_to_full_reference`（账本缺失退化全量）；(3) `test_only_changed_episodes_keep_their_text`（只注入改动集、未变集只给集号）。另含 `test_ledger_records_other_episode_snapshot`（based_on 快照）与 `test_broken_ledger_does_not_break_the_reference`（坏账本不阻断）。
- `writing_api` 往返：`test_episode_incremental_hint_and_ledger_round_trip`（首存写账本→无改动不贴正文→改一集只贴该集）。
- Agent 路径：`test_script_agent_delivery_assembly.test_agent_prompt_only_lists_changed_episode_numbers`（只列改动集号，不贴正文）。
- 零新增红对照：`git stash` 后实测 `tests.test_writing_api`＝51 条 / 2 failure＋30 error，与本轮 52 条 / 2 failure＋30 error 同形（仅多 1 条本轮新增绿）；`tests.test_script_contract`＝47 条 / 1 failure，与本轮 52 条 / 1 failure 同一红点。
- 台账：`writing_api.py` 第四项 `json.loads` 行号随本轮插入由 486 平移至 522（AST 实测 `[522]`），`架构统一基数.json` 同步；架构棘轮 3/3 通过。
- 环境限制（非本轮引入）：本工作树缺 `程序/skills/00全流程SKILL/AIGC创作全流程`（gitlink 160000 未实体化，`.gitmodules` 不存在，无法 `submodule update`），受影响门禁红点全部来自 `freeze_skills` 校验该目录下 `screenplay-gate-engine.md` 缺失及其引出的断言，`.agent-handoff/risks.md` 早有同记录。
- 全量 `run_selftests.py --all --safe` 未跑：按任务约定「最多一次」，且同一 gitlink 缺口会让全量产生大批已知假红、污染凭据；留待合并 master／主工作树收口补跑。

## 范围外未改
- 未改 `程序/skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md`（标题格式本就正确）。
- 未改 `structure_script()` 的场次解析逻辑（按集解析是新增的平行能力，不替换）。
- 未改既有测试断言迁就实现；新增用例只在既有测试文件内追加。

## 风险与边界
- 标题正则把 `#` 设为可选，理论上正文中「行首以第N集开头」的整句可能被误判为集标题；模板正文用 `## 本集目标`／`### 场景` 等不会命中，实测无影响，属可接受的容错边界。
- `based_on` 记录的是「生成前版本的其余集指纹」；同一次生成里多集同变时各集 `based_on` 互指上一版，语义为「相对上一版」，符合任务定义。
- 未重启桌面应用、未做真实四角色／直连 API 端到端点击；单元与静态验证不等于真实交互验收。

[TASK_COMPLETE] 阶段④自然剧本已能按集解析并记录分集增量账本；续写时只把「相对上次生成有改动」的集正文注入模型（首次／无账本退化为全量），未变集只给集号；本地 Agent 同获集号提示；三类退化场景与新增用例定向覆盖，默认冒烟 8/8。

## 合入 master（R1366）
- 按规则 27 在中央入口重新认领 R1366，把分支 `codex/episode-incremental-context` 合入 master（merge commit `f252de3`，父提交 master `9777bf4`）。
- 冲突解析：`程序/维护记录/架构统一基数.json` 的 writing_api.py `json.loads` 行号按合并后实测定为 **548**（分支记 522、master 记 512 均已失效）；`.agent-handoff/snapshot.md`／`work-log.md` 保留 master 现状并补合入记录；其余文件自动合并无冲突。
- 合并树实测：定向 12/12（EpisodeIncrementalTests 5＋Agent 集号 4＋架构棘轮 3）、分集往返 1/1、默认冒烟 8/8；`tests.test_script_contract`／`tests.test_writing_api` 仅既有缺 gitlink 假红（3 failure＋30 error 全部指向 `skills/00全流程SKILL/AIGC创作全流程` 未实体化）。
- 轮次记账：未改 `program/project_status.md` 轮次头、未新建 `tasks_round_1366_result.md`——主工作树中另有并行轮次已把 `project_status.md`（当前轮次：1366）与 `tasks_round_1365_result.md` 暂存待提交，新增 1366 结果会让「当前轮次＝最新结果＋1」失衡；留待该并行轮提交后统一。