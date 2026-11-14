# R2443 结果：P0-2 收口 writing_api 的低层反向依赖（阶段配置 → L1 协议，回退口令 → L2 启发式）

## 三个必答（§7）

- **轮次类型**：结构治理轮·执行（§3.3）——按 `tasks_round/tasks_round_182_optimization_backlog.md` P0-2 中「`writing_api` 直接读阶段配置／工作任务」一项，消除低层反向依赖。不改分层登记、不新增顶层模块、不用白名单压过测试。
- **测试跑了吗、三个基线过了吗**：
  - 定向（本轮改动模块相关的架构门禁）：`unittest tests.architecture.test_layers test_complexity_ratchet test_module_size_ratchet test_writing_api_json_boundary test_writing_publication_boundary test_stage_command_contract test_project_context_boundary` **38/38 通过**；新增门禁 `test_writing_api_stage_config_boundary` 4/4、门禁清单一致性 `test_agents_md` 相关断言通过，合计本轮相关 **21/21 绿**（单独一轮复跑确认）。
  - 默认冒烟：`smoke_test.py --affected writing_api` 的 8 项快速检查 **8/8 通过**；其 `run_selftests.py --serial -k writing_api …` 定向门禁在本 DSH 沙箱内因 `multiprocessing.Pipe()` 命中 `PermissionError [WinError 5]`（无法创建命名管道）而退出，**属环境限制非本轮回归**（与 R2428「架构 416 条 2 红为功能工作树环境限制」同源）。
  - 架构门禁：`unittest discover tests/architecture` **416 条，1 failure + 16 errors**，全部为环境性、非本轮引入——1 条 `test_skill_reference_injection…screenplay-gate-engine.md` 缺失（外部嵌套仓库 gitlink 资产），16 条 `PermissionError [WinError 5]`（`tempfile` 在 `C:\Users\LAIBIAO\AppData\Local\Temp\dsh-*` 清理被沙箱拒绝）。**本轮改动涉及的架构门禁全部绿**，改前改后无差异。
  - 全量回归：未跑（DSH 沙箱无法派生工作进程，见 AGENTS.md §5 / runbook.md §4；本轮为分支轮，全量欠账不在此累计）。
- **project_status.md 的欠账少了吗**：本分支轮只写结果文件，不改 `project_status.md`（仅 master 可提交，§2.6 规则 41）；P0-2 中 `writing_api` 子项由「未完成」推进为「已收口」，合入 master 后补记。

## 改动内容

1. **`writing_api.py`**：读阶段模型的 3 处从 L3 `stage_config.get(project,'script')['model']` 改为 L1 `stage_model_value.value(project,'script')`——`selected_model()`（1 处）与 `_versioned_publisher()` 的生成期模型变更核对（2 处）。`import stage_config` 移除，改 `import stage_model_value`。该 L1 协议自 R1647 起即为此用途建立，`asset_batch_service`／`keyframe_model_service` 同口径复用。语义不变：`stage_config.get` 把空值归一为 `'auto'`、`stage_model_value` 返回原始空串，但 `selected_model` 的 `not chosen or chosen == model_pool.AUTO` 守卫对两者等价；`_versioned_publisher` 用同一函数自比，不受归一化差异影响。
2. **`idea_script_heuristic.py`**（L2，纯文本谓词既有归属）：新增 `writing_restart_requested(text)`，为原 `workflow_tasks.writing_restart_requested` 的逐字下沉（同一正则、同一 `rstrip('。！!')` 首行口径）。
3. **`workflow_tasks.py`**：`writing_restart_requested` 改为按原名转发到 L2 `idea_script_heuristic`，保留既有 `workflow_tasks.writing_restart_requested` 调用与测试锚点；移除因此不再使用的 `import re`。
4. **`writing_api.py` `preparation_restart_intent`**：回退口令判定从 `from workflow_tasks import writing_restart_requested` 改为 `from idea_script_heuristic import writing_restart_requested`。
5. **`tests/architecture/test_writing_api_stage_config_boundary.py`**（新增，4 条用例）：正向钉住反向依赖已消除——`writing_api` 读阶段模型走 L1 `stage_model_value`（`assertNotIn('import stage_config')`／`assertNotIn('stage_config.get')`），回退口令走 L2 `idea_script_heuristic`（`assertNotIn('from workflow_tasks import writing_restart_requested')`），L2 启发式保持纯文本、`workflow_tasks` 按名转发。用门禁自证而非白名单。
6. **`architecture.md`**：新增 R2443 记录，并在 §「当前架构门禁清单」补一行 `test_writing_api_stage_config_boundary.py`（满足 `test_agents_md` 的门禁清单与实际文件集合完全相等的强约束）。

## 验证证据

- `py_compile`：`writing_api.py`／`workflow_tasks.py`／`idea_script_heuristic.py`／`test_writing_api_stage_config_boundary.py` 均通过。
- 行为逐字等价核验（直接调用）：
  - `writing_restart_requested`：`重新创作项目设定`→True、`请重新生成角色卡。`→True、`重新输出自然剧本`→True、`随便说点什么`/`修改主角`/`确认`/`''`→False；`workflow_tasks.writing_restart_requested` 与 `idea_script_heuristic.writing_restart_requested` 输出一致。
  - `preparation_restart_intent`：`回到设定阶段`/`大纲要重写`/`角色卡推翻重来`/`重新创作项目设定`/`请重新生成角色卡。`→对应阶段，`修改主角`/`确认`/`开始创作`/`继续输出项目大纲`→None。
  - `selected_model`：空项目→`('', {})`，`stage_config.put(..., model='gpt-4o')` 后→`('gpt-4o', {record})`（与改前一致）。
- 断言未动：未改任何既有测试文件；新增 4 条正向门禁用例（见上）；`workflow_tasks.writing_restart_requested` 的 patch/import 锚点经按名转发保留。

## 边界与未做项

- 不改 `writing_api` 的 L3 分层登记：其另有 `workflow_settings`／`workflow_context_controller`／`project_context_factory`／`edit_habits` 等 L3 依赖，本轮只收口 P0-2 点名的「阶段配置／工作任务」两条，其余留待后续专项（R1647 已声明「按批分轮推进」）。
- `script_prompt` 仍由 `writing_api.reply` 惰性 `from workflow_tasks import script_prompt`（L3 同层，非越层）；未改其参数签名以免撞 `test_complexity_ratchet` 的 7 参数上限。

## 已提交

- 分支：`codex/wip-R2443`；轮次 `round_claim.py next` 已领取 2443（`round-counter.json last_claimed=2443`）。
- commit hash：见下方（`R2443: P0-2 收口 writing_api 低层反向依赖…`）。
