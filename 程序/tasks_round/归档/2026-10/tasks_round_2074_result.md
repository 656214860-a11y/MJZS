# R2074 修改习惯第一期：自然剧本修改采集、归纳、确认、注入（功能轮）

轮次类型：功能轮。日期：2026-10-30。分支 `claude/agent-learn-user-edits-d32ad8`。

- 跑了哪些测试与基线：新增 `tests/test_edit_habits.py` 9 条全过；默认冒烟 8/8；`--affected`（8 个改动模块）与 `--architecture` 见下方“仍红”；覆盖率基线已用 `scripts/coverage_report.py` 重跑刷新。
- `project_status.md` 欠账：未减少，也未新增（本轮在分支上，不改状态页，由合并轮同步）。
- 断言未动。

## 做了什么

- 需求与设计：`docs/stages/S01_剧本准备.md` 新增 REQ-S01-58～61、DES-S01-58～61 与测试锚点。
- 采集（REQ-58）：剧本结构页编辑并保存**自然剧本**后，`desktop_script_pages._record_natural_edit` 调 `edit_habits.record_edit`，按行比对只记改动片段（每段 ≤600 字、每次 ≤20 段，只改空白不记），每个项目最多 200 条。记录失败只写日志，不影响保存。
- 存放：修改记录与规则都在本机 `程序/private/编辑习惯/`（记录按项目路径哈希分文件，规则为 `规则.json`），不随程序分发，升级不覆盖，也不写进项目目录（交付或分享项目时不带出修改内容）。两种 JSON 登记到 `artifact_schema`（`edit_records`、`edit_habit_rules`），经 `agent.core.save` 写入。
- 归纳（REQ-59）：剧本准备面板「风格」行新增「修改习惯」按钮，弹窗里点「归纳最近修改」。未归纳记录满 3 条才调用 API 文本模型（桌面引擎不支持），片段作为待分析资料发送；返回 JSON 校验通过才存为“待确认”，同文规则不重复加入；格式不对时如实提示，记录保持未归纳。
- 确认（REQ-60）：弹窗表格可采用、停用、改写（≤80 字）、删除（二次确认），选中后显示改前／改后例子。
- 注入（REQ-61）：`workflow_settings.current()` 建配置时读一次已采用规则写入 `config['edit_habits']`；`workflow_engines.prompt_with_settings` 与 `writing_api` 两处剧本准备系统提示词放在编剧风格之后。最多 10 条、合计 ≤800 字，按出现次数排序，与编剧风格冲突时以编剧风格为准。其他阶段不注入；规则文件损坏时不注入、不阻断任务。
- 第一期不学剧本结构：结构剧本由本地规则生成，不调用模型，学到的规则没有使用方。

## 门禁处理

- `tests/architecture/_layers.py` 登记 `edit_habits`（L3）、`edit_habits_dialog`（L4）。
- 「工作流任务」目录没有路径权威入口，新模块手拼会触发 `test_workflow_dir_ratchet`；因此修改记录改放 `private/`，未改登记表。
- `parse_rules` 的 `json.loads` 解析的是模型返回文本，不是文件读取，按 R1125 `skill_notes` 先例在 `维护记录/架构统一基数.json` 登记豁免。
- `覆盖率基线.json` 重跑后模块 324→326、覆盖 50 个不变；其他模块的 `total` 行数随 R2054 以来各轮改动一并刷新（工具如实输出）。`runbook.md` §11 的数字同步。
- `skill_panel.py`、`workflow_settings.py`、`writing_api.py` 在行数上限，净增 0 行；`_install_script_edit_controls` 抽出 `_record_natural_edit`，保持 150 行以内。

## 仍红（均非本轮引入）

- `--architecture` 3 红 1 错：`test_agents_md` 缺 `维护记录/基准历史.json`（本 worktree 无此文件）；`test_skill_reference_injection`（worktree 未检出子模块 `skills/00全流程SKILL/AIGC创作全流程`）；`test_round_baselines` 轮次连续（等合并轮同步状态页）。
- `--affected` 定向自检 24 个文件有红：均为缺上述子模块导致 SKILL 引用缺失。在干净 HEAD（47df1bce）的临时 worktree 跑同一批 766 条用例，红文件与每个文件的红数逐一相同。

## 手工检查

- 在隐藏桌面实建 `HabitsDialog`：未归纳计数、选中显示例子、采用后表格变「已采用」、无可用模型时归纳给出提示并恢复按钮，均正常。后台归纳线程的未知异常改为兜底回到界面。

## 未运行

- `--all --safe`、真实界面目测、真实模型归纳效果。未 push。

## 回滚

- `git revert` 本轮提交即可；本机 `private/编辑习惯/` 下的数据可直接删除，不影响其他功能。
