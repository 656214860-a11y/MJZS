# R1764：功能轮——本地与云端“自动验收”统一读 project_settings.auto_review（C3，S10-18）

> 接手说明：进入本车道时工作树已有前一个执行方留下的部分改动（`git status`/`git diff` 核对：`docs/stages/S10_视频生成.md`、`engine.py`、`local_video.py`、`tests/test_req_s10_anchors.py`），无结果文件。本轮在其上继续核验、补做先红／变异验证并交付，未从头重做。

## 三问（AGENTS §7.3）

1. **轮次类型**：功能轮（`AGENTS.md` §3.1）。对应 `REQ-S10-18`／`DES-S10-15`、`DES-S10-18`；按 §2.7 先改 `docs/stages/S10_视频生成.md` 的需求与设计，再是代码与测试。
2. **测试跑了吗、三个基线**：
   - 默认冒烟：**8/8 通过**（本轮实跑 `python -B smoke_test.py`）。
   - 架构门禁：任务书只指定 `tests.architecture.test_requirement_traceability` 与 `tests.architecture.test_layers`，**10/10 通过**；未跑 `--architecture` 全部门禁（任务书明确禁止），不拿历史绿色结果顶替。
   - 全量回归与欠账：**未运行**（任务书禁止 `run_selftests.py`／全量／`--affected`）；不冒用历史凭据。
3. **`project_status.md` 欠账少了吗**：REQ-S10-18 由 🟡 改为 ✅ 并补锚点；`维护记录/需求锚定基线.json` 中 grep 不到 `S10-18`，故欠账条数不变（本轮不新增欠账）。

## 根因与改动（文件:函数）

**根因**：同一“下载＋技术质检通过后自动放行”的语义有两套开关来源。云端 `engine.Studio.poll` 读 `project_settings.auto_review(项目根)`（持久化在项目 `ui_settings.json`）；本地 `local_video.LocalStudio.poll` 读 `pet_ui.should_auto_run(self, self.root, 'auto_review')`，即三虎 `auto_review_var`。三虎变量不持久化（新进程默认 `False`），项目设置持久化，于是重启后云端仍自动放行、本地不放行。

**生产改动**：

- `engine.py:auto_review_ready(project, report)`（新增小函数，与 `review_source`／`content_reviewed` 同层，未新增模块）：自动技术放行的唯一判据——`report` 为空或有 `errors` 一律 `False`；否则 `project_settings.auto_review(project) is True`；`OSError`／`ValueError`／`TypeError`（配置文件读不到、JSON 坏、类型不对）按关处理。默认关：键缺失、读不到、值不是 `True` 都为关。
- `engine.py:Studio.poll`：原 `if not report['errors'] and project_settings.auto_review(self.root):` 改为 `if auto_review_ready(self.root, report):`，行为等价（原条件不含 `report` 为空的情况，现更保守）。
- `local_video.py:LocalStudio.poll`：原 `__import__('pet_ui').should_auto_run(self, self.root, 'auto_review')` 改为调用同一 `auto_review_ready(self.root, report)`；文件顶层导入随之改。本地路径不再读三虎变量，也不依赖 `self.pet`。
- 自动放行写入内容未变：`review=REVIEW_PASS`、`review_by='auto'`、`review_note=AUTO_REVIEW_NOTE`；两条返回文案（`已按自动验收设置放行（未做内容审核）`／`待您验收`／`等您验收`）未变。
- 三虎全自动／手动切换时批量写 `project_settings` 与三虎变量的行为未动（`pet_ui_stages._set_all_auto_actions`）。

**`pet_ui_support.py` 未改（映射保留）**：`AUTO_STAGE_VARIABLES['auto_review']='auto_review_var'` 仍有调用方——`pet_ui_stages.should_auto_run` 按 stage 查该表，`_set_all_auto_actions` 经 `AUTO_VARIABLE_NAMES` 把全部三虎变量（含 `auto_review_var`）与项目设置同步写入，页面/兼容代码可读；按任务书“若还有其它调用方就保留，不要扩大范围”，保留不动。本阶段放行判定已不再经 `should_auto_run('auto_review')`。

**`project_settings.py` 未改**：`auto_review()`／`set_auto_review()`（`:66`、`:70`）任务前已存在，本轮直接复用，无需新增小函数。

**文档改动**（`docs/stages/S10_视频生成.md`）：REQ-S10-18 改 ✅ 并改写为现状（统一判据、默认关、有错不放行、写入字段、重启一致性）；DES-S10-15、DES-S10-18 把“本地读 `pet_ui.should_auto_run`”改为两路同读 `engine.auto_review_ready`；测试锚定表新增 REQ-S10-18 行，`REQ-S10-18/21/31` 合并行只去掉 18（保留 REQ-S10-21/31 原句）。

**测试改动**：`tests/test_req_s10_anchors.py`（既有 S10 锚点文件）新增 `_auto_review_project`／`_local_poll`／`_cloud_poll` 夹具与 `ReqS10AutoReviewAnchorTests` 5 条，docstring 均写 `REQ-S10-18`。本地分支用 `object.__new__(LocalStudio)` + patch `LocalAPI`／`check`／`command`／`record_video_usage`／`publish_manifest`，不创建三虎；云端分支同法构造 `Studio`，两条路径共用同一临时项目。

## V1–V5 实测

- **V1 通过**：`test_req_s10_18_local_auto_review_reads_project_settings_only`——`set_auto_review(root, True)` 后跑本地下载＋质检分支，`qc_pass` 真、`review=='pass'`、`review_by=='auto'`、`review_note==engine.AUTO_REVIEW_NOTE`、返回文案含“已按自动验收设置放行（未做内容审核）”。用例里没有创建三虎，`studio` 无 `pet` 属性，证明不依赖三虎变量。
- **V2 通过**：`test_req_s10_18_off_or_missing_key_waits_for_human_on_both_paths`——键缺失与显式 `False` 两个子用例下，本地与云端版本都停在 `review=='pending'`、`review_by!='auto'`，文案分别含“待您验收”“等您验收”；`test_req_s10_18_qc_errors_never_pass_on_both_paths`——`auto_review=True` 但质检 `errors=['时长不符']` 时两路 `qc_pass` 假、`review!='pass'`。
- **V3 通过**：`test_req_s10_18_restart_keeps_sanhu_variables_off_and_both_paths_agree`——给本地 `studio.pet` 注入“新进程三虎”（`should_auto_run` 恒 `False`），项目设置仍为 `True`，本地与云端结果一致（都 `pass`／`by='auto'`／同一 note）。
- **V4 通过**：先红与变异见下。
- **V5 通过**：REQ-S10-18 ✅ 改写；DES-S10-15／DES-S10-18 统一读法；锚点表补行、合并行只去掉 18；锚点追加在既有 `tests/test_req_s10_anchors.py`（`ls tests/ | grep -i s10` 找到两个既有 S10 文件，选其一，见需裁决事项 2），docstring 写 `REQ-S10-18`；`test_requirement_traceability` 实跑通过。

另：`test_req_s10_18_shared_predicate_defaults_off` 直接锚定共用判据——报告有错、`report=None`、键缺失、值 `'yes'` 都为关；`True` 且无错为开。

## 先红证据

工作树接手时已有实现与测试，**没有前执行方的“实现前”失败日志**。按 V4 以变异回退旧实现补做等价先红：

```
FAIL: test_req_s10_18_local_auto_review_reads_project_settings_only
AssertionError: 'pending' != 'pass'
FAIL: test_req_s10_18_restart_keeps_sanhu_variables_off_and_both_paths_agree
AssertionError: 'pending' != 'pass'
Ran 2 tests ... FAILED (failures=2)
```

即“本地读三虎变量”的旧实现下，V1／V3 都红（不创建三虎时拿不到 `pass`），与“改前先红”的证据力等价；如实说明其来源是变异回退，不是实现前的原始日志。

## 变异验证

1. 改前记录 `local_video.py` sha256 = `901783395AF1AA818411ED539B33BD644B07DC9B6A20E5F8A7C0251C490F44CC`，并备份到临时目录。
2. 用 `edit` 只把 `if auto_review_ready(self.root,report):` 临时改回 `if not report['errors'] and __import__('pet_ui').should_auto_run(self, self.root, 'auto_review'):`（真正的旧实现）。
3. 跑 V1／V3 两条：`FAILED (failures=2)`，均为 `'pending' != 'pass'`（有效变红，不是导入或桩问题）。
4. 从备份还原，sha256 复核 `901783…44CC` 与改前完全一致；复跑 `tests.test_req_s10_anchors` 7 条 **OK**。

## 实际命令计数

共执行约 **21 条** PowerShell 调用（含 3 条因环境问题作废后重跑：嵌套 `pwsh` 不在 PATH、PowerShell 5.1 按 ANSI 读 UTF-8 脚本、缺 `PYTHONPATH=tests`），另有 4 次后台测试批次启动、2 次 `job_kill`（均已被自然结束，无残留）。全部单条在 15 分钟内返回；最长单个测试文件 `test_ui_edges` 307 秒。实跑：

- `PYTHONPATH=tests python -B -m unittest tests.<25 个消费方文件>` 逐个单文件 → 全部 EXIT=0（合计约 953 秒）。文件清单来自 `grep -ln "auto_review\|local_video\|should_auto_run" tests/*.py`：`test_asset_detail`、`test_asset_gating`、`test_execution_deadline`、`test_final_page_loading`、`test_final_viewer`、`test_frame_sources`、`test_idea_chat`、`test_integration`、`test_leak_teardown`、`test_local_video_settings_service`、`test_page_cache`、`test_perf_baseline`、`test_req_s07_anchors`、`test_req_s08_anchors`、`test_req_s10_anchors`、`test_row_targets`、`test_sanhu_mode`、`test_stage_wiring`、`test_timers`、`test_ui_batch6_pages`、`test_ui_edges`、`test_video`、`test_video_generation_scope`、`test_video_revision`、`test_video_ui`。
- `python -B -m unittest tests.test_req_s10_anchors` → 7 条 OK（含 5 条新增）。
- `PYTHONPATH=tests python -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_layers` → 10 条 OK。
- 变异下定向 2 条 → 2 FAIL（见上）；还原后复跑 anchor 文件 → 7 OK。
- `python -B smoke_test.py` → 8/8。
- `tests.test_video_ui` 在本机全绿（含 `PromptBoxHeightTests`），未观察到任务书所述隐藏桌面 4 条失败。

## 改了哪些既有测试的哪个预期

**无。** 本轮既有测试文件只做了追加（`tests/test_req_s10_anchors.py` 新增 5 条），没有改动任何既有测试的断言、预期值、mock 或导入路径。

## 断言未动声明

既有测试断言未动；没有删除、弱化或跳过任何断言。新增断言见 `tests/test_req_s10_anchors.py::ReqS10AutoReviewAnchorTests` 5 条。

## 需裁决事项

1. **先红证据来源**：前一个执行方未留“实现前”失败日志，本轮的 V4 先红由“变异回退到旧实现”补做（证据力等价但时间点不同）。若调度方要求原始终态日志，本工作树无法提供。
2. **既有 S10 锚点文件有两个**：`tests/test_req_s10_anchors.py`（本轮追加处，原有 REQ-S10-03/32）与 `tests/test_req_anchor_s10.py`（REQ-S10-11/13/16/20/23/33）。任务书要求“既有 S10 锚点测试文件”，本轮选前者；如需统一到后者请调度方指定，搬迁即可。
3. **三虎 `auto_review` 映射保留**：`pet_ui_support.AUTO_STAGE_VARIABLES['auto_review']='auto_review_var'` 因 `_set_all_auto_actions`／`AUTO_VARIABLE_NAMES` 仍在批量写入而被保留（任务书“有其它调用方就保留”）；本阶段放行已不读它。若后续要彻底移除，需单独裁决页面兼容。
4. **旧残留变量**：`app.py:339` 的 `self.auto_review=tk.BooleanVar(value=False)` 全树 grep 无读取方（应是死变量）；不在允许改的文件内，本轮未动，仅记录。
5. **判据异常边界**：`auto_review_ready` 捕获 `OSError`／`ValueError`／`TypeError`（覆盖文件不存在、无权限、JSON 坏、类型不对）按关处理；若未来 `project_settings.load` 引入其它异常类型，需要重新评估“读不到一律关”的覆盖范围。

## 自检结论

- 验收标准：V1–V5 均满足（见上）。
- 改动范围：`engine.py`、`local_video.py`、`docs/stages/S10_视频生成.md`、`tests/test_req_s10_anchors.py`；`project_settings.py`、`pet_ui_support.py` 未改。`git status` 仅这 4 个文件被修改，无新增文件、无 `.bak_*`。
- 未引入新问题：两条路径都走同一判据且都是 `not errors + 项目设置`；自动放行写入字段与文案未变；三虎批量同步未动。25 个消费方测试文件（含 `test_integration`、`test_video_ui`）全绿，架构追溯与分层门禁绿，冒烟 8/8。
- 未提交、未领号、未改 `project_status.md`／`AGENTS.md`、未读 `private/`／`.env`、未碰用户真实项目数据（全部临时目录）。
- **结论：通过**，等待调度方独立验收与提交。

## 独立验收（Claude，车道 lane_c3 内隐藏桌面真实环境直接运行）

- 范围：`engine.py`、`local_video.py`、`docs/stages/S10_视频生成.md`、`tests/test_req_s10_anchors.py` 共 4 个文件，`git diff` 逐行读过；生产改动仅 `auto_review_ready` 一个函数与两处调用。
- 定向：`test_req_s10_anchors` 7/7；25 个消费方测试文件逐个跑，22 个全绿。
- 3 个有失败的文件与主干 R1763 基线对照（同一隐藏桌面）：`test_video_ui` 同样 4 条 PromptBoxHeight 失败；`test_asset_detail` 基线同样 3 条 keyboard_buttons 失败，C3 多出的 `test_reload_restores_focus_to_detail_navigation` 单独重跑 2 次均通过（焦点类偶发）；`test_ui_edges` 基线 11 条、C3 10 条，均为缩略图／滚轮／几何，集合有小幅出入，C3 独有的 `test_the_frame_table_shows_thumbnails_in_the_file_column` 在主干单独跑同样失败。判定均与本轮无关，不记为通过。
- 门禁：`test_requirement_traceability`＋`test_layers` 10/10；`smoke_test.py` 8/8；`smoke_test.py --architecture` 375/375。
- 执行方结果文件的先红证据来自变异回退而非实现前日志，已如实写明；`pet_ui_support` 的 auto_review 映射保留，`app.py:339` 的 `auto_review` 变量疑为死变量，均留待后续裁决。
- 用户可见行为变化：本地视频路径的自动放行改由项目设置决定（原由三虎变量决定）；三虎全自动／手动切换仍同步写两处，故会话内行为不变，重启后不再丢。
