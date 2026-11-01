# R1758：文档轮——12 条 🟡 需求按已定裁决收口为 ✅ 并补测试锚点（DOC1）

## 三问

- 轮次类型：§3 文档轮（零生产代码；仅文档、SKILL 文本、需求锚点测试与本结果文件）。
- 测试跑了吗：跑了任务书要求的窄测试；12 个需求锚点均命中，相关测试文件、需求锚定门禁、两个 SKILL 精确用例和默认冒烟均通过。任务书点名的两个 `run_selftests.py -k` 运行超时后改用精确文件并通过；未运行 `--architecture`、全量、`--affected` 或其他宽 `-k`。
- 三个基线：默认冒烟 8/8 通过；完整架构门禁未运行（任务书明确禁止），窄需求锚定门禁 5/5 通过；完整 `--all --safe` 未运行，未生成或引用全量绿凭据。
- 欠账：未修改 `project_status.md`。`维护记录/需求锚定基线.json` 本轮未改，当前 `untested_done` 仍为空；12 条新增锚点没有增加锚定欠账，也没有可减少的历史锚定欠账。

## 12 条收口

- REQ-S03-51 — `docs/stages/S03_初步分镜.md:50` 标 ✅，说明旧 `FLOWS/DEFAULT_SKILLS` 是兼容层、AIGC 阶段预设为权威；`:95` 同步为已裁决。锚点：`tests/test_req_s03_anchors.py:80` `test_req_s03_51_legacy_flow_coexists_but_stage_preset_is_authoritative`。
- REQ-S04-52 — `docs/stages/S04_分镜预演.md:47` 标 ✅，收窄为只读画幅／低配预览规格；`:94` 同步为已裁决。`skills/04 分镜预演SKILL/pipeline-animatic.skill.md` 删除“配置缺口／返回准备阶段”，保留项目设置优先与总控可替换含义。锚点：`tests/test_req_s04_anchors.py:347` `test_req_s04_52_skill_only_promises_the_locks_the_stage_reads`。
- REQ-S05-05 — `docs/stages/S05_资产管理.md:13` 标 ✅；`skills/05资产管理SKILL/pipeline-assets.skill.md` 的 `input` 收窄为 `storyboardDraft, assetRequirements`。锚点：`tests/test_req_s05_anchors.py:123` `test_req_s05_05_skill_inputs_do_not_require_manifests`。
- REQ-S06-16 — `docs/stages/S06_连贯性清单.md:21` 标 ✅，漂移范围限定为角色锚点。锚点：`tests/test_req_s06_anchors.py:13` `test_req_s06_16_drift_compares_character_anchors_only`。
- REQ-S06-25 — `docs/stages/S06_连贯性清单.md:31` 标 ✅，页面现场计算不落盘、手动生成才发布。锚点：`tests/test_req_s06_anchors.py:29` `test_req_s06_25_page_preview_is_read_only_but_manual_generate_publishes`。
- REQ-S07-03 — `docs/stages/S07_分镜定稿.md:13` 标 ✅，`DEPENDS` 仅表数据依赖，资产／连贯性前置由 SG-01／SG-02 表达；`:102` 同步记录已裁决。锚点：`tests/test_req_s07_anchors.py:524` `test_req_s07_03_depends_is_data_graph_and_sg_gates_are_business_preconditions`。
- REQ-S07-53 — `docs/stages/S07_分镜定稿.md:53` 标 ✅；`skills/07分镜定稿SKILL/storyboard-version-snapshot.skill.md` 改为登记、日期后缀和回收站退役，不再承诺独立快照、比较或回滚。锚点：`tests/test_req_s07_anchors.py:535` `test_req_s07_53_skill_describes_registration_not_unimplemented_snapshots`。
- REQ-S10-03 — `docs/stages/S10_视频生成.md:11` 与 DES `:78` 标 ✅，说明视频依赖表只表 `keyframe` 数据依赖，复杂镜头预演由 SG-05 表达，未改 SKILL `dependsOn`。锚点：`tests/test_req_s10_anchors.py:16` `test_req_s10_03_video_depends_on_keyframe_and_previs_is_only_sg05`。
- REQ-S10-32 — `docs/stages/S10_视频生成.md:39` 标 ✅；`skills/10视频生成SKILL/` 中 4 个含旧阶段号的页面位置改为现算的“10 视频生成”，全部 5 个 SKILL 已无“08 视频生成”，元数据未改。锚点：`tests/test_req_s10_anchors.py:23` `test_req_s10_32_skill_page_locations_use_current_stage_label`。
- REQ-S11-13 — `docs/stages/S11_配音与字幕.md:23` 标 ✅，明确程序只保证 ID→显示名→默认音色绑定，一角一音色与年龄／性别相符属人工判断。锚点：`tests/test_audio_role_binding.py:27` 与 `:32` 两个既有 `voice_for` 回退测试仅追加 `REQ-S11-13` docstring。
- REQ-S11-32 — `docs/stages/S11_配音与字幕.md:42` 标 ✅，旧 `DEFAULT_SKILLS['audio']` 保持空串并作为兼容层，AIGC 阶段预设以 `pipeline-audio-subtitle` 为权威。锚点：`tests/test_req_s11_anchors.py:9` `test_req_s11_32_legacy_audio_default_is_empty_and_stage_preset_is_authoritative`。
- REQ-S13-27 — `docs/stages/S13_质检与交付.md:34` 标 ✅；`docs/stages/S12_后期剪辑.md:27` 增加反向边界说明，确认后期剪辑完成核验读取交付阶段归属的 `13质检交付/导出成片`。锚点：`tests/test_req_s13_anchors.py:491` `test_req_s13_27_edit_completion_reads_delivery_export_folder`。

## 实际命令与计数

| 命令 | 结果 |
| --- | --- |
| `python -B tests/test_req_s03_anchors.py` | 13/13，退出 0 |
| `python -B tests/test_req_s04_anchors.py` | 13/13，退出 0（最终补强后复跑） |
| `python -B tests/test_req_s05_anchors.py` | 9/9，退出 0 |
| `python -B tests/test_req_s06_anchors.py` | 2/2，退出 0 |
| `python -B tests/test_req_s07_anchors.py` | 14/14，退出 0 |
| `python -B tests/test_req_s10_anchors.py` | 2/2，退出 0 |
| `python -B tests/test_req_s11_anchors.py` | 1/1，退出 0 |
| `python -B tests/test_req_s13_anchors.py` | 23/23，退出 0 |
| `python -B tests/test_audio_role_binding.py` | 18/18，退出 0 |
| `python -B tests/architecture/test_requirement_traceability.py` | 5/5，退出 0 |
| `python -B -m unittest tests.test_skill_registry_parse -v` | 2/2，退出 0 |
| `python -B -m unittest tests.architecture.test_skill_reference_injection -v` | 9/9，退出 0 |
| `python -B smoke_test.py` | 8/8，退出 0 |
| `git diff --check` | 无空白错误，退出 0 |
| `python -B tests/architecture/test_requirement_traceability.py --find <12 个编号>` | 12 个编号均命中，退出 0 |

任务书要求的两个宽命令 `python -B run_selftests.py -k skill_registry` 与 `python -B run_selftests.py -k skill_reference_injection` 各运行 10 分钟仍无输出，按任务书停止。随后经 `--list` 定位精确模块，分别直接运行 `tests.test_skill_registry_parse` 和 `tests.architecture.test_skill_reference_injection`，结果为 2/2、9/9；不声明这两个宽命令已通过。

## 断言与范围

- 生产 `.py` 代码未改；未读 `private/`、`.env`；未执行 git 写命令，未领号、未提交、未改 `project_status.md` 或 `AGENTS.md`。
- 既有测试断言未改、未弱化、未跳过。`tests/test_audio_role_binding.py` 只在两个既有测试上追加 `REQ-S11-13` docstring，断言原样保留；其余改动是新增锚点用例或新增测试文件。
- 新增测试均使用临时目录、既有常量或既有函数，没有联网、没有读写真实用户项目，也没有新增 `skipTest`。
- 12 条均已有可判别锚点，本轮无因无法锚定而保留 🟡 的条目。

## 需裁决事项

- `architecture.md:79` 仍写“输出提示词和快照”，与 REQ-S07-53 的现状仍有文字差异；任务书明确禁止本轮修改，保留待后续裁决。
- `skills/10视频生成SKILL/` 总入口 `parallelizable: false` 与其余四个页面 SKILL 的 `true` 存在元数据差异；任务书要求本批只改文字，保留待后续裁决。
- 两个宽 `run_selftests.py -k` 命令在 10 分钟窗口内无输出；精确测试文件通过，但宽命令本身没有可声明为完成的运行结果。

## 独立验收（Claude，车道 lane_doc1 内直接运行，真实环境）

- 范围：22 个已改文件＋3 个新建测试，无任何生产 `.py`（`git diff` 与 `git status` 核对）；改动只在 `docs/stages/*.md`、4 个 SKILL 目录下 7 份 `*.skill.md`、`tests/test_req_*_anchors.py`、`tests/test_audio_role_binding.py`（仅追加 REQ docstring）。
- 锚点：9 个相关测试文件复跑 13/13、13/13、9/9、2/2、14/14、2/2、1/1、23/23、18/18 全绿，与执行方自报计数一致（须用 `-m unittest tests.<名>` 形式，直接 `python tests/x.py` 因随附解释器不读 PYTHONPATH 会找不到模块，这是调用方式问题，与改动无关）。
- 变异：临时回退 `skills/` 全部改动，S04-52、S05-05、S07-53、S10-32 四条文字类锚点均变红，还原后补丁哈希一致；行为类锚点（S06-16 构造角色／场景／道具冻结值只出角色、S06-25 页面读取不改文件而手动生成才写盘、S13-27 成片目录核验、S03-51／S11-32／S07-03／S10-03 取现有常量与门禁表）由测试构造即可判别。
- 门禁：`architecture.test_requirement_traceability`＋`test_skill_reference_injection`＋`test_agents_md`＋`test_skill_registry_parse` 31/31；`smoke_test.py` 8/8；`smoke_test.py --architecture` 375/375。
- 执行方的两条宽 `run_selftests -k skill_*` 超时已如实写入结果文件，不记为通过。
- 遗留裁决：`architecture.md:79`“输出提示词和快照”与 REQ-S07-53 仍有文字差异；`skills/10视频生成SKILL/` 总入口 `parallelizable:false` 与其余四个 `true` 的差异——均未在本批改动。
