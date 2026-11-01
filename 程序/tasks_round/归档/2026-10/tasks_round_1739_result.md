# R1739：验证/基线轮——S07 分镜定稿补 13 条需求测试锚点（REQ07）

- 车道：`D:\漫剧制作助手\.wt\lane_req07`（分支 worktree，执行方不领号、不提交、不改 `project_status.md`）
- 轮次类型（§3）：**验证/基线轮（§3.10）**——只补测试资产、更新锚定基线与结果记录，未改任何产品代码。
- 结果文件编号：pending（未领号；提交方合入后再按轮次归档）。

## 0. 每轮三问（§7.3）

1. **本轮属于哪种类型？** §3.10 验证/基线轮：为 13 条已标 ✅ 但无锚点测试的 S07 需求补真实断言，并把 `维护记录/需求锚定基线.json` 中登记的历史欠账按规则 27／§2.7 第 4 条移除；无需降级（全部 13 条行为经测试确认与需求一致）。
2. **测试跑了吗、三个基线过了吗？**
   - 本批定向：`python -B -m unittest tests.test_req_s07_anchors tests.architecture.test_requirement_traceability` → `Ran 17 tests ... OK`（12 锚点 + 5 门禁）。
   - 增量回归（任务书命令）：`python -B run_selftests.py -k test_req_s07 test_storyboard_final_controller test_final_service test_file_cache` → `共 44 条用例；0 个文件有红；ALL TESTS PASSED`（5 个测试单位，8.4s）。
   - §2.5 三个基线数：默认冒烟 `smoke_test.py` **未运行**（本轮未改产品代码，任务书未要求；8/8 沿用现基线，不代表本轮已复验）；架构门禁只跑与本轮改动直接相关的 `tests.architecture.test_requirement_traceability`（5 条通过），未跑 `--architecture` 全表；全量 `--all --safe` **未运行**（分支不累计欠账，交提交方按 §5 基线决定）。
3. **`project_status.md` 的欠账少了吗？** 是：`需求锚定基线.json` 的 `untested_done` 移出 13 条 `REQ-S07-*`（该文件 13 行删除，无其他改动），现存条目中已无 `REQ-S07-*`。本轮该文件新增欠账：无。

## 1. 交付物与改动范围

| 文件 | 改动 | 性质 |
| --- | --- | --- |
| `程序/tests/test_req_s07_anchors.py` | 新增（文件 docstring 含「REQ-S07 测试锚定」，共 12 个 `test_req_s07_xx_*` 用例，REQ-19 含 3 段子场景、REQ-31 含 6 段子场景） | 新测试 |
| `程序/tests/test_storyboard_final_controller.py` | 仅补 docstring（REQ-S07-32 锚点：3 个既有用例 + 文件头） | docstring-only |
| `程序/tests/test_final_service.py` | 仅补 docstring（REQ-S07-05／31 备份锚点：文件头 + 1 个既有用例） | docstring-only |
| `程序/tests/test_file_cache.py` | 仅补 docstring（REQ-S07-21 备份锚点，`test_final_lineage_prefers_...`，第 283 行） | docstring-only |
| `程序/维护记录/需求锚定基线.json` | 删除 13 条 `REQ-S07-*`（`indent=2`／`ensure_ascii=False`／末尾换行保持不变） | 基线更新 |
| `程序/docs/stages/S07_分镜定稿.md` | **未改**（13 条全部满足，无 🟡 降级） | — |
| `程序/维护记录/skip台账.json` | **未改**（本轮无新增 skip，未用 Tk，无 `PLATFORM_TKINTER` 引用） | — |

产品代码（任何非测试 `.py`）零改动；`D:\漫剧制作助手\程序` 主树未触碰。

## 2. 逐条锚点表（13 条）

对应断言一律写行为，不查源码字符串；「自证红输出」为把产品实现临时反转后同一用例的真实失败首行（驱动脚本：`C:\Users\LAIBIAO\AppData\Local\Temp\opencode\req07_red.py`；日志：`...\req07_red_log.txt`；反转只发生在驱动加载的副本/mock 上，车道产品代码保持原样）。

| 编号 | 锚点测试 | 断言 → 需求原文 | 自证红输出 | 结论 |
| --- | --- | --- | --- | --- |
| REQ-S07-05 | `test_req_s07_05_busy_production_blocks_manual_and_waits_auto`；备份锚点 `test_final_service.py::test_decision_distinguishes_repeat_wait_and_dispatch` docstring | `worker` 或视频会话 `busy` 时 `Desktop.make_final_storyboard` 抛 `ValueError('等待当前制作任务结束')` 且不派发后台任务；`poll_auto_final` 遇忙只置 `auto_final_blocked`、`auto_final_busy` 为假、队列空 → 「手动入口在有 `worker` 或视频会话忙时拒绝；自动入口遇忙等待，不抢跑」 | `AssertionError: ValueError not raised` | ✅ 与需求一致 |
| REQ-S07-10 | `test_req_s07_10_asset_names_resolve_to_ids_or_fail_loudly` | 名称解析为编号（`CHAR_001`／`LOC_001`）并写 `名称编号对照.json`；无编号且无名称即 `ValueError('无法匹配资产编号：None')`，且不新建目录、不覆盖已有定稿、不动源稿 → 「镜头里的角色／场景／道具先解析为资产编号…解析不到编号即抛『无法匹配资产编号』，不静默跳过」 | `AssertionError: ValueError not raised` | ✅ 与需求一致 |
| REQ-S07-11 | `test_req_s07_11_asset_bindings_and_missing_assets_are_recorded` | 逐镜 `asset_bindings`（名称／图片／状态）、`reference_images` 只含已导入资产的图、`asset_status` 为「待补齐资产/已匹配资产」；未导入资产汇入顶层 `missing_assets=['CHAR_002']`、`assets_ready` 为假，但定稿仍落盘 → 「每镜写入 `asset_bindings`…资产缺图不阻止定稿，只标缺」 | `KeyError: 'CHAR_001'`（bindings 被清空后断言取值失败） | ✅ 与需求一致 |
| REQ-S07-12 | `test_req_s07_12_dialogue_speaker_is_replaced_by_the_character_id` | 台词 `speaker` 由「主角」替换为 `CHAR_001` → 「台词 `speaker` 按名称映射替换为角色编号」 | `AssertionError: Lists differ: [{'speaker': '主角', …}] != [{'speaker': 'CHAR_001', …}]` | ✅ 与需求一致 |
| REQ-S07-16 | `test_req_s07_16_identical_content_reuses_the_existing_final` | 同内容签名二次定稿返回同一目录、目录数不增、仍按需退役工作稿、`产物来源关系.json` entries 不重复；内容一变即换新目录 → 「定稿以内容签名复用：已存在签名相同的定稿则不新建，只补血缘并按需退役工作稿」 | `AssertionError: …/EP001_分镜定稿_20261019 != …/EP001_分镜定稿_20261019_2`（签名比对失效后新建了第二份） | ✅ 与需求一致 |
| REQ-S07-17 | `test_req_s07_17_the_same_episode_writes_back_to_the_same_directory` | 经「文件路径映射.json」的别名映射二次定稿写回原目录且落到新内容；源本身是定稿时同样写回原目录、不新建 → 「同一集再次定稿写回同一目录（同 `episode_id` 的别名映射，或源本身就是定稿）」 | `AssertionError: …EP001_分镜定稿_20261019_2 != …EP001_分镜定稿_20261019` | ✅ 与需求一致 |
| REQ-S07-18 | `test_req_s07_18_source_changed_during_sync_aborts_and_publishes_nothing` | 让源在同步窗口内被追加字节 → 抛 `ValueError('同步期间已修改')`，`07分镜定稿/分镜/**/episode.json` 为空，源文件内容保留不被改写；`writing.validate_episode` 在一次定稿中被调用 ≥2 次 → 「发布前后各复核：源文件在同步期间被修改则中止并保留原 JSON；两次 `validate_episode`」 | `AssertionError: ValueError not raised` | ✅ 与需求一致 |
| REQ-S07-19 | `test_req_s07_19_bundle_is_paired_copied_and_rolled_back_on_failure` | `episode.json`＋`assets.json` 成对落盘；资产图与帧图复制进定稿目录；同名异内容加哈希后缀并把 `assets.json`／`reference_images`／`asset_bindings` 三处引用一起改写；`publish_final_storyboard_bundle` 校验失败保留原有两份文件、新建失败时删除半成品 → 「发布走原子发布包…同名异内容时加哈希／随机后缀并改写引用」 | `AssertionError: {'shots': []} != {'old': 'episode'}`（回滚失效，旧 `episode.json` 被覆盖） | ✅ 与需求一致 |
| REQ-S07-20 | `test_req_s07_20_retire_happens_only_after_publish_and_only_for_working_sources` | 退役回调被调用时定稿已落盘（`published=True`）、收到 `target=<定稿>/episode.json`、`source` 与 `expected` 哈希；无注入时抛 `TypeError('定稿退役需要 L3 编排入口。')` 且该错发生在发布之后（定稿目录已存在）；源本身是定稿时不触发退役 → 「发布完成后才退役工作稿…缺注入即抛 `TypeError`」 | `KeyError: 'published'`（退役回调整段被移除） | ✅ 与需求一致 |
| REQ-S07-21 | `test_req_s07_21_lineage_points_at_the_structured_script_not_the_working_json`；备份锚点 `test_file_cache.py::test_final_lineage_prefers_stable_structured_script_over_working_json` docstring | 血缘 entry 的 `source == '02剧本/EP001_结构剧本.json'`（源 JSON 的 `source_script`），且不等于会被退役的工作 JSON 路径；源本身是定稿时 `产物来源关系.json` 字节不变（不新记） → 「定稿记录追溯到稳定的结构剧本…源本身是定稿时不新记」 | `AssertionError: '03初步分镜/分镜文档/EP001_分镜.json' != '02剧本/EP001_结构剧本.json'` | ✅ 与需求一致 |
| REQ-S07-30 | `test_req_s07_30_manual_entry_runs_async_reports_and_rebuilds_the_page` | `stage_flow.MANUAL_LABELS['final'] == '手动同步资产'`；`make_final_storyboard` 只排 1 个后台 job；完成回调后三虎播报 `stage='final'` 且文案含「已刷新」、切到 `PAGE['final']`（=6）、记忆列表为 `['episode.json']` → 「手动入口按钮名『手动同步资产』…异步定稿，完成后三虎播报并重建定稿页」 | `TypeError: 'NoneType' object is not subscriptable`（三虎播报被丢弃后读 `stub.report` 失败） | ✅ 与需求一致 |
| REQ-S07-31 | `test_req_s07_31_unattended_runs_only_when_ticked_for_a_working_source_once`；备份锚点 `test_final_service.py` docstring | 未勾选 `should_auto_run('final')` → 清签名、不阻塞、不派发；制作忙 → 阻塞不抢跑；同一签名 → 不重复定稿；正常 → 置忙并经队列派发，产物目录 `EP001_分镜定稿_<今日>`、工作稿被退役；失败 → `auto_final_due` 至少 +290s、签名清空、状态栏含失败原文；扫描 `auto_final_scan`／`auto_final_target` 只认「工作稿且资产齐」的稿、已在定稿目录里的稿不再入队 → 「仅当用户在定稿页显式勾选…当前分镜仍是工作稿、同一份稿只定稿一次（签名去重）、失败退避重试」 | `AssertionError: False is not true`（未勾选仍放行）；`AssertionError: 'skip' != 'wait'`（决策不再区分重复/等待） | ✅ 与需求一致 |
| REQ-S07-32 | `tests/test_storyboard_final_controller.py::test_choose_persists_view_and_tracks_preview_navigation`、`::test_save_edited_validates_before_atomic_persistence`、`::test_failed_publish_preserves_document_preview_and_navigation`（docstring 锚点） | 只读预览与镜头导航；保存前先校验合法 JSON 再经 L3 `save_edited_stage_storyboard` 原子发布；发布失败保留原预览与当前镜头导航 → 「定稿页只读预览、编辑保存与镜头导航…发布失败保留原预览」 | `AssertionError: "合法 JSON" does not match "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"`（去掉 `json.loads` 校验后非法 JSON 直接进发布） | ✅ 与需求一致 |

## 3. 自证红汇总

驱动脚本对 13 条需求做了 15 次实现反转（storyboard_final 的解析/绑定/血缘/写回/退役、`desktop` 的忙判与播报、`storyboard_final_controller` 的校验与失败保留、`final_service` 的决策），**15/15 全部把对应锚点跑红**，日志尾行 `ALL 15 REVERSALS TURNED THE ANCHORS RED`。无「删除实现仍绿」的伪锚点。

## 4. 验证命令与实际计数

| 命令 | 实际输出 |
| --- | --- |
| `PYTHONPATH=.;tests python -B -m unittest tests.test_req_s07_anchors tests.architecture.test_requirement_traceability` | `Ran 17 tests in 6.340s` → `OK` |
| `python -B run_selftests.py -k test_req_s07 test_storyboard_final_controller test_final_service test_file_cache` | `共 44 条用例（8.4 秒）；0 个文件有红` → `ALL TESTS PASSED`；分单位：`test_req_s07_anchors 12 条`、`test_file_cache#1 11 条`／`#2 15 条`、`test_storyboard_final_controller 5 条`、`test_final_service 1 条` |
| `python -B tests/architecture/test_requirement_traceability.py --find REQ-S07-05 …-32` | 13 条编号均能定位到本轮锚点（方法级），无「引用不存在编号」红 |
| 基线 JSON 形态自检 | `untested_done` 中 `REQ-S07-*` 剩 `[]`；末尾换行 `True`；`indent=2` `True`（`git diff` 该文件仅 13 行删除） |

## 5. 需裁决事项

1. **REQ-S07-10 报错文案**：需求只要求「解析不到编号即抛错」。实测行为是镜头字段完全无 `id`／`name` 时抛 `ValueError('无法匹配资产编号：None')`（`None` 来自取不到的名称）；给出**未登记**的新名称时 `asset_plan._sync_plan` 会自动分配新编号而非报错。锚点按实测行为断言（无名称才报错），请裁决是否要为「未知名称也报错」改文档或改代码——本轮未改。
2. **REQ-S07-05 自动入口语义**：需求写「自动入口遇忙等待」。实测是置 `auto_final_blocked` 并跳过本轮轮询，而不是阻塞等待；下一轮 tick 再试。锚点按「不抢跑、不派发」断言，字面「等待」是否需改为「跳过本轮」请裁决。
3. **REQ-S07-31 的扫描职责**：`auto_final_scan`／`auto_final_target`（含 `missing` 资产、已定稿排除）被纳入本轮锚点；需求原文未点这些字段，属实现细节，若认为超出需求边界可拆分。
4. **`docs/stages/S07_分镜定稿.md` 未改**：13 条均已实现且锚定，无需 ✅→🟡。请确认无遗漏的降级判断。
5. **§2.5 三个基线数**：默认冒烟与 `--architecture` 全表本轮未跑（任务书未列），提交方按 §5 决定是否补跑；本轮无产品代码改动，风险面仅测试文件。

## 6. 交付前自检（§4.2）

- 验收标准：13 条 ✅ 无锚点需求全部有真锚点、逐条自证红、基线移除 → 满足。
- 改动范围：仅允许的 6 个文件（1 新增测试、3 docstring、1 基线、1 结果）；产品代码与主树未动 → 满足。
- §5 适用验证：任务书两条命令已跑并贴计数；未运行项已如实标注 → 满足。
- 新问题：无新增 skip、无 Tk 依赖、无真实用户项目读写（全部 `tempfile`）→ 结论：**通过**。

## 独立验收（Claude，主工作区）

- 主树 `test_req_s07_anchors`＋门禁 17 条 OK；docstring 所在三文件定向 0 红。
- 裁决：①S07-10 未登记名称自动分配编号属「能解析」，按实测锚定，不改文档／代码；②S07-05「遇忙等待」即本轮跳过、下轮再试，语义一致，不改；③S07-31 锚点含扫描字段可接受。
