# R4240：FEAT-SCRIPT-FILES 完整修复（LOST-04）
<!-- round-evidence: {"commit_base": "e4f0c15c", "credential_hits": 0, "evidence_sha256": "28ff7f0007ff1308", "exit": 0, "failed": 0, "passed": 666, "round": 4240, "tests": "run_selftests.py -k writing preparation files_panel stage_completion idea_chat"} -->

- 轮次类型：功能轮（§3.1）。测试跑了；定向自测改前红→改后绿（见下）；三个基线：默认冒烟未跑（卡面验收为定向命令＋`smoke_test.py --architecture`）、架构门禁见下、全量回归欠账以 `full-safe-receipts.json` 为准未新增。
- 欠账：无新增。
- 提交：`dev.py commit`（自动暂存、白名单、生成 `tasks_round/evidence/R4240.json` 并写结果文件机器头）；commit hash 见完成报告与 `git log`。

## 一、L0→L5 只读盘点（改前）

- **L0 命名/阶段锁**：`contract/script_contract.py` `stage_file_info`/`stage_file_name`（stage-v1 四段名解析）；`domain/idea_document_paths.py` 四类目录映射（项目设定/项目大纲/角色卡/项目剧本）。未改——stage-v1 解析保持兼容；「已确认」不是文件名契约的一部分，只是台账/标签语义。
- **L1 字段校验**：`writing_api._preparation_state` 校验 documents 位置对位（`document['stage'] != PREPARATION_STAGES[index]` → 记录无效），稀疏台账会被误判。
- **L2 领域**：`domain/idea_chat.py` `import_downloaded_documents`/`import_local_document` 按正文/文件名独立判类四类文档（本已任意顺序，无需改）；`domain/asset_reference_prompts.discover` 扫 writing/ 下全部 .md 的「角色卡/人物卡/角色设定」提示词段，与确认状态无关——角色卡→资产提示参考链路已通，`domain/asset_plan.py` 已接线 `sync_reference_prompts`，无需改。
- **L3 编排**：`orchestrator/stage_completion_service.py` `completion_evidence` script 分支被 `preparation_progress['blocked']` 串行门拦截（改前约 748-753 行）；`writing_api._preparation_state/_preparation_task/_preparation_step`、`orchestrator/writing_preparation_ledger.py`（`_confirmed_prefix`/`_preparation_work_index`/`_preparation_draft_is_parallel`）、`orchestrator/writing_unconfirm.py`（`confirm/unconfirm_preparation_document`/`apply_partial_adoption`）构成位置序串行链。
- **L4 UI**：「已确认」前缀产生点 `writing_api.preparation_file_labels`（返回 '已确认'/'待确认'/'重写待确认'），消费点 `ui/desktop_files_panel_index.py` 拼 `[已确认] 文件名`；`ui/desktop_script_pages.py` 无前置灰显逻辑（grep 证实），缺前置卡点经 `desktop_shared_input.py` `completion_evidence` 传导。
- **L5 文档**：`docs/stages/S01_剧本准备.md` REQ-S01-111 登记 LOST-04；REQ-S01-10/11/13/89 与 DES-S01-78/89 的串行表述本轮同步修订。

## 二、改前红（原文）

`test_idea_chat.py` `ScriptFilesCompletionTests.test_adopted_natural_script_completes_without_serial_preparation_confirmation`：
`AssertionError: False is not true : 剧本准备卡在「项目设定」：文件缺失；请补齐并确认后再继续`
（定向自测改前：该条红 + `test_script_contract` 审计红 1 条，后者为基线既有红）

## 三、变更点

- `orchestrator/stage_completion_service.py`：`completion_evidence` script 分支删除串行门，完成＝`resolve_script_source`＋质检门；`preparation_progress` 改为各文档独立现状报告（blocked/missing 恒空兼容位、confirmed 计数不要求连号、stages 逐阶段给存在/确认、next_actions 只跟自然稿采用状态）。
- `orchestrator/writing_preparation_ledger.py`：新增 `_document_stage_index`/`_document_for_stage`/`_upsert_stage_document`/`_preparation_texts_map`；`_confirmed_prefix` 改按阶段名判定前缀；`_preparation_work_index` 改为「阶段序里最早未确认草稿优先→无草稿取第一个尚无已确认记录的阶段→三阶段全确认返回 3 进自然剧本」，点名任意阶段直达；`_preparation_draft_is_parallel`/`_preparation_rollback`/`_preparation_natural_requested` 按阶段名判定。重写意图判定族（`preparation_restart_intent`/`_preparation_restart_affirmative`/`_preparation_restart_target`）先迁入后按架构边界测试要求移回 `writing_api.py`（P0-2：回退口令判定须走 L2 `idea_script_heuristic`，测试扫描 writing_api.py 源文本）。
- `writing_api.py`：`_preparation_state` 校验放宽为「阶段名合法且不重复」（稀疏台账合法），重启块按阶段名对位；重写已确认目标仍要求已确认前缀（`_confirmed_prefix` 为 None 且目标非未确认草稿→`ValueError`，REQ-S01-14 语义保留，`test_writing_edited_restart` 钉住），仅重写未确认草稿跳过前缀校验（REQ-S01-89）；`_preparation_task` pending/标签按阶段名、资料优先级块按阶段名映射标签；`_preparation_step` 点名自然剧本直通阶段④（`_preparation_natural_requested`＋`_promote_revision`）、确认位与写入按阶段名对位、`_upsert_stage_document` 按阶段序插入稀疏台账、返回改 `{stage: text}` 映射；`advancing` 前缀门保留但只约束「推进确认」链路。
- `orchestrator/writing_unconfirm.py`：`confirm_preparation_document` 取消前置确认要求，任何阶段可独立设为定稿（同阶段替换、已确认下游照旧作废、未确认草稿保留；revision 未覆盖目标阶段时回退采用版本并清 revision/pending_restart）；`unconfirm_preparation_document`/`apply_partial_adoption` 按阶段名查找、连带取消下游已确认，不再按下标截断、保留全部草稿记录。
- `ui/desktop_files_panel_index.py`：文件名标签跳过 '已确认'，已确认稿不再显示 `[已确认]` 前缀；未确认草稿仍标「待确认／重写待确认」。
- `docs/stages/S01_剧本准备.md`：REQ-S01-111 ✅；REQ-S01-10/11/13/89 加 LOST-04 注记、REQ-S01-89 改写为任意顺序口径；DES-S01-78/89 改为现行阶段名对位实现描述。
- 测试（契约有意变更，台账由位置对位改为阶段名对位、取消/部分采用不再截断草稿）：`tests/test_writing_unconfirm.py`、`tests/test_preparation_monitor.py`、`tests/test_preparation_parallel.py`（点名远阶段改断言稀疏台账、独立确认保留草稿）、`tests/test_preparation_confirmation.py`（无前缀独立确认、简报变化后独立重确认）、`tests/test_preparation_source_priority.py`（夹具 stage 键 '项目大纲'→'剧本大纲'，对齐真实台账键；断言全部不变）。保留 `tests/test_idea_chat.py` +26 行红测原样。

## 四、验收命令（最终代码，含回退修正后复跑）

- `python -B run_selftests.py -k script_contract stage_completion idea_chat script_page asset`（卡面验收命令 1，原样）：655 条用例全量执行（GUI 令牌空闲，无 deferred），273.6 秒，退出码 1——唯一红 `test_script_contract.AuditTests.test_the_audit_covers_every_script_skill`（SKILL 清单审计，基线 e4f0c15c 改前首轮同样红，与本卡无关；tests/test_script_contract.py 与 skills/ 不在允许清单未动）。本卡红测 `test_adopted_natural_script_completes_without_serial_preparation_confirmation` 已转绿，test_idea_chat 全部 11 分片、test_stage_completion_service、test_desktop_script_pages、test_script_page_layout、test_ui_batch5 全绿。
- `python -B smoke_test.py --architecture`（卡面验收命令 2，最终代码复跑）：退出码 0，700 条架构用例全 OK（242.7 秒），含模块棘轮 `test_no_module_exceeds_its_cap` 与 `test_writing_api_stage_config_boundary` 4 条。
- `python -B run_selftests.py -k writing`（回退修正后复跑，216 条用例 / 21 文件）：退出码 0，0 红（108.7 秒）；含 `test_writing_edited_restart` 11 条（此前发现并已修复的回退点）。
- `python -B run_selftests.py -k preparation files_panel`：55 条用例 0 红；其中 test_files_panel／test_files_panel_stages 两个 Tk 文件因跨树 GUI 令牌被占 deferred，令牌释放后单独 `python -B run_selftests.py -k files_panel` 复跑：171 条用例 0 红（233.2 秒），退出码 0。
- `python -B run_selftests.py -k preparation writing_unconfirm writing_restart writing_api files_panel`（早期补跑，回退前）：331 条用例 0 红（249.4 秒）；回退后由上面 `writing`／`preparation`／`files_panel` 三批复验覆盖同一文件集。
- `python -B run_selftests.py -k writing_api_stage_config source_priority`：退出码 0，15 条用例（架构边界＋优先级块修复复验，回退前；架构边界由本轮 `--architecture` 700 条复验覆盖）。

## 五、覆盖核对

- 任意顺序/任意组合生成：`_preparation_work_index` 点名任意阶段直达、稀疏台账按阶段名对位写入；旧「之前还有阶段未起草」报错已移除（test_preparation_parallel 改断言生成稀疏台账）。
- 缺前置不灰显/不卡点：完成核验与发送门禁不再要求串行确认。
- 完成口径：至少一份已采用自然剧本（`resolve_script_source`）＋质检门（新红测转绿）。
- 旧「已确认」文件名兼容：台账按 stage+path+sha256 读取，不改名不迁移；`preparation_file_labels` API 保持返回 '已确认'（test_writing_restart 兼容），仅 UI 展示层去前缀。
- stage-v1 命名解析回归：`script_contract` 未改，定向自测通过。
- 角色卡参考有/无：`asset_reference_prompts.discover` 对存在/不存在卡面段均安全，asset_plan 已接线；有/无两支由既有 asset 测试覆盖（定向 -k asset 全绿）。
- 独立确认/取消/部分采用/重写回退/简报重置/自然剧本独立：test_writing_unconfirm、test_preparation_confirmation、test_writing_restart、test_writing_restart_intent、test_writing_edited_restart、test_preparation_monitor 全绿。

## 六、未验证项

- `test_script_contract.AuditTests.test_the_audit_covers_every_script_skill` 红为基线既有问题（SKILL 清单审计期望 script-forging/编剧技能集，仓库登记缺；改前首轮运行同样红，与本卡无关；tests/architecture 与 skills 不在允许清单，未动）。
- 默认冒烟 `smoke_test.py`（无参）未跑——卡面验收只列定向命令与 `--architecture`。
- 全量 `run_selftests.py --all --safe` 未跑（非 master 提交点、卡面未要求）。
