# R2125 结果：合入 codex/wip-R2122（R2118：桌面续发材料按步骤取、SKILL 引用按需按节内联）到 master（合并轮）

## 内容
- R2118（d504c3c7）：续发材料只带当前写作步骤及之前的成果，确认件优先，本模型目录没有时取别的模型交付的最新一份；冻结 SKILL 的「仅 `锁` 为…时追加」引用按制作锁跳过，带锚点引用只内联该节。详见 tasks_round_2118_result.md。
- R2122（55d355be）：R2112 已占用 REQ-S01-71，本轮需求顺延为 REQ-S01-72／73，文档、锚定表、测试名同步改号，断言未动。R2122 只有这一个改号提交，记录写在 tasks_round_2118_result.md 的补记里。
- 领号经过：R2114 提交时已被别的会话跳过，改领 R2118；改号提交又被跳过，改领 R2122。第一次合并时主目录另一会话正在合入 R2117（有 MERGE_HEAD 和暂存文件），等它提交 R2123、R2124 后才合并。

## 冲突
- `docs/stages/S01_剧本准备.md` 锚定表：master 的 REQ-S01-71 行与本分支的 72、73 行都保留。
- `desktop_send_choice.py` 自动合并（R2117 把两个发送函数移进来，本分支只改 `_resend_plan`）。

## 合并修复
- 合并后 `--architecture` 红：`workflow_settings.py` 1237 行 > 上限 1176（R2118 新增代码）。没有抬上限，把纯引用扫描函数移到 `skill_registry.py`：`condition_unmet`、`section`、`_anchor_slug` 及两个正则（R2118 新增），以及原有的 `reference_row`、`nested_references`（原 `_reference_row`、`_nested_references`，`workflow_settings` 以原名导入，行为不变）。`workflow_settings.py` 1158 行，`skill_registry.py` 934 行。DES-S01-73 的函数位置同步改写。

## 验证（本轮运行，合并后的主目录）
- 移函数前：`run_selftests -k desktop_send skill_conditional skill_reference_closure desktop_attachment requirement_traceability complexity_ratchet layer req_s01_anchors master_skill request_freeze stage_prompt_governance writing flow_agent_launch client_profiles idea_chat script_composer`：489 条，1 红为 `test_client_profiles.test_req_s01_56_builtin_catalog_covers_every_known_client`（读本机 data/客户端档案.json，同 R2108／R2111 记录，非本轮引入）。
- 移函数后：`smoke_test.py --architecture` 通过；`run_selftests -k skill desktop_send master_skill request_freeze stage_prompt_governance writing flow_agent_launch req_s01_anchors`：521 条全通过；`smoke_test.py`（默认）通过。
- `--all --safe`：由本次提交的 post-commit 钩子在后台触发。

## 未验证
- 没有在真实 Gemini 窗口里实测附件发送与新的材料范围。
