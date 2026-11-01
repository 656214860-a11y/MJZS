# R1682 验证基线轮：为阶段 S10 视频生成补齐 6 条需求锚点测试

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.10 验证/基线轮。只新增测试文件与缩减需求锚定基线，未改任何产品代码，不算源码轮。

2. **测试跑了吗？三个基线过了吗？**
   - 定向 `run_selftests.py -k req_anchor_s10 requirement_traceability`：19 条 / 0 红（`test_req_anchor_s10` 15 条、`architecture.test_requirement_traceability` 4 条；其中 `test_baseline_only_shrinks` 与 `test_new_done_requirement_needs_a_test_anchor` 均通过）。
   - 默认冒烟 `smoke_test.py`：8/8。
   - `run_selftests.py -k agents_md`：15 条 / 0 红（新测试文件未引起架构门禁变化，无需登记）。
   - `run_selftests.py -k round_baselines`：5 条中 4 绿，唯一红为 `test_full_safe_all_is_required_after_eight_source_rounds`（R1682 欠一次完整安全全量，系 R1676 起的既有欠账，由 post-commit 后台自动补跑，与本轮无关）。
   - 未跑架构门禁全量与安全全量（本轮仅测试与文档，不算源码轮，不触发全量欠账）。

3. **project_status.md 的欠账少了吗？** 需求锚定欠账减少：`维护记录/需求锚定基线.json` 的 `untested_done` 从 152 条减为 146 条（删除 REQ-S10-11/13/16/20/23/33 共 6 条）。

## A 改动

- 新增 `tests/test_req_anchor_s10.py`（15 条用例，锚定 REQ-S10-11/13/16/20/23/33 共 6 条需求）：
  - REQ-S10-11：服务商表（万相/Seedance/自定义）、会话目录命名、密钥读取优先模型池。
  - REQ-S10-13：`RequestLedger.authorize_units`/`settle_units` 授权与结算、失败保守保留、落盘后记条数+秒数、云端已结算不重复记。
  - REQ-S10-16：生成期锁定（`prompt_locked`/`generation_active`/`assert_prompt_editable`）。
  - REQ-S10-20：版本目录 `data/<镜头>/vNNN/` 命名、下载发布 qc.json 与 mp4、版本记录 file/sha256。
  - REQ-S10-23：进入成片只认锁定版优先否则最后已验收版；文件缺失/被替换判不可用、不进剪辑。
  - REQ-S10-33：视频提示词只写动作与运镜（prompt_templates/storyboard_contract/stage_parallel）。
  - 断言均针对真实代码行为（真实函数/真实常量/真实 SKILL 与源码），未用 mock 造被测事实、未用 `assertTrue(True)` 或空断言；新测试在 `tempfile.TemporaryDirectory()` 隔离环境运行，不写仓库内项目/data/logs 目录。
- `维护记录/需求锚定基线.json`：`untested_done` 删除 6 条 REQ-S10-* 编号（JSON 格式不变、编号保持升序）。

## C 待用户裁决

无。6 条需求原文与代码一致，未降级任何 ✅；无纯描述/无法自动验证的条目。

## 提交

见提交信息 `R1682:`。
