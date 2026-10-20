# R1763：功能轮——edit_manifest 逐镜补时间码、音轨、字幕与切换依据（C2）

## 三问（AGENTS §7.3）

1. **轮次类型**：功能轮（`AGENTS.md` §3.1）。按 §2.7 先改 `docs/stages/S12_后期剪辑.md` 的 REQ-S12-34 → DES-S12-34，再改代码与测试；新增两条失败用例先红后绿。对应 `REQ-S12-34`／`DES-S12-34`。
2. **测试跑了吗、三个基线**：
   - 默认冒烟：**8/8 通过**（本轮实跑）。
   - 架构门禁：任务书只指定 `tests.architecture.test_requirement_traceability` 与 `test_layers`，**10/10 通过**；未跑 `--architecture` 全部门禁（任务书明确禁止），不拿历史绿色结果顶替。
   - 全量回归与欠账：**未运行**（任务书禁止跑 `run_selftests.py`／全量）；不冒用历史凭据。
3. **`project_status.md` 欠账少了吗**：本轮把 REQ-S12-34 从 🟡 改为 ✅ 并补上锚点；`维护记录/需求锚定基线.json` 中 grep 不到 S12-24／S12-34，故该文件欠账条数不变（本轮未新增欠账）。

## 根因与改动（文件:函数）

**根因**：`Studio.publish_edit_bundle` 只把 `shot／version／sha256／source` 写进 `edit_manifest.json`，时间码只存在于同次生成的 EDL／FCPXML，音轨／字幕只登记在 `edits.json.inputs`，转场设置只在 `edits.json`；清单无法单独回答“这段用了什么、为什么这样切”。

**生产改动**（只改 `engine.py`）：

- `engine.py:EDIT_MANIFEST_SCHEMA`：新常量 `2`，清单顶层版本号。
- `engine.py:edit_clips(chosen)`：抽出 EDL／FCPXML 与清单共用的镜头序列（`shot／file／duration`），`publish_edit_lists` 与 `publish_edit_bundle` 都用它，时间码不另算第二套。
- `engine.py:out_relative(out,path)`：成片目录相对路径（跨盘保留绝对路径），`source`、`audio`、`subtitles` 同一口径。
- `engine.py:shot_input_assets(inputs,shot_id)`：从 `edits.json.inputs` 的 `audio／subtitles` 里按文件名“整词含镜头号”挑条目（`001_SH001_对白` 命中 `SH001`，`SH0011` 不命中），返回 `path／sha256`。
- `engine.py:Studio.publish_edit_bundle`：
  - 每镜在原四字段之外**只增不改**补 `timecode`（`in／out` 时间码字符串、`in_seconds／out_seconds`、`fps`，均由 `edit_export.layout／timecode` 按同一 `output_spec.fps` 得出）、`audio`／`subtitles`（无则 `[]`，键不省略）、`transition`（`kind／seconds／reason`：首镜 `cut`；未设置转场＝concat 硬切；设置了就按实际 `overlap` 记 `xfade／acrossfade` 重叠秒数）。
  - `edit_manifest.json` 顶层改为 `{'schema': 2, 'manifest': [...]}`；`edit_bundle.json` 顶层同步加 `schema`，`manifest` 仍是同一份逐镜数组（S13 现有读取不变）。
  - 复用一次 `self.edit_inputs()` 结果同时写 `edits.json.inputs` 与清单，避免两次读盘。
- `engine.py:read_edit_bundle`：读 `edit_manifest.json` 时同时接受旧顶层数组与新 `{'schema','manifest'}`，旧数据继续按 `legacy` 返回。

**未改**：成片编码、EDL／FCPXML 文本、目录结构与文件名、`edit_bundle.json` 的 `manifest` 形状、`storage_maintenance.edit_source_versions`（它本来就把 dict 取 `manifest`、list 直接当行，天然两种都兼容，故未动）。

**读取方核对**（先 grep 后逐个核对）：`edit_manifest.json` 的 Python 读取方只有 `engine.read_edit_bundle` 与 `storage_maintenance.EXPORT_MANIFEST_NAMES`→`edit_source_versions`；S13 质检／商用只读 `edit_bundle.json` 的 `manifest`（`stage_completion_service` 三处），未读索引文件，故不受影响。

**文档改动**（`docs/stages/S12_后期剪辑.md`）：REQ-S12-34 改 ✅ 并改写为现状（行号引用改函数名）；新增 DES-S12-34；测试锚定表 `REQ-S12-24/34` 合并行只去掉 34（保留 REQ-S12-24 原句），另加 REQ-S12-34 锚点行。

**测试改动**：`tests/test_req_s12_anchors.py` 新增两条（V1／V2／V3 锚点）；`tests/test_integration.py`、`tests/test_edit_adoption.py` 各同步清单顶层形状（明细见下）。

## V1–V5 实测

- **V1 通过**：`test_req_s12_34_assemble_manifest_records_timeline_sources_and_switch` 用真实 `Studio.assemble → _encode → publish_edit_bundle → publish_edit_lists`（只把 ffmpeg／probe／check 换成夹具，沿用 `test_req_s12_anchors.py` 既有做法），断言：顶层 `schema == EDIT_MANIFEST_SCHEMA`；每镜四字段仍在；`timecode.in／out` 与同次 `剪辑清单.edl` 该镜时间线入/出点逐字相等；`fps=30`、秒数 `0–2`／`2–5`；`bundle['schema']` 相同且 `bundle['manifest'] == rows`。
- **V2 通过**：SH001 有 `SH001_对白.wav`／`SH001.srt`，清单 `audio`／`subtitles` 记相对路径与 `agent.core.file_hash` 实测值相等；SH002 无对应文件，`audio == []`、`subtitles == []` 且键存在。
- **V3 通过**：`test_req_s12_34_legacy_manifest_is_still_accepted_by_all_readers` 构造旧格式四字段数组，`read_edit_bundle` 返回 `legacy=True` 且行内容不变；`storage_maintenance.edit_source_versions` 读出 `{('SH001',1)}` 与 `{('SH001','old-hash')}`；同一用例再写新格式 `{'schema','manifest'}`，两个读取方的结果相同。
- **V4 通过**：先红见下；变异验证见下。
- **V5 通过**：REQ-S12-34 ✅、补 DES-S12-34、锚点 docstring 写 `REQ-S12-34`、测试锚定表处理如上；需求追溯门禁通过。

## 先红证据（改实现之前）

```
ERROR: test_req_s12_34_assemble_manifest_records_timeline_sources_and_switch
TypeError: list indices must be integers or slices, not str   # manifest 还是顶层数组，没有 schema
ERROR: test_req_s12_34_legacy_manifest_is_still_accepted_by_all_readers
AttributeError: module 'engine' has no attribute 'EDIT_MANIFEST_SCHEMA'
Ran 2 tests ... FAILED (errors=2)
```

（更早一次红是测试桩本身不完整：`_join_shots` 用的是 `engine.probe`，第一次只 patch 了 `agent.media.probe`，报 `找不到程序 ffprobe`；补上 `engine.probe` 后得到上面这条针对生产行为的红，不是把桩问题当先红。）

## 变异验证

1. 记录 `engine.py` sha256 = `148E63501183E20CB56A4B177F9B6D252FEE3AAF525DAC2E13F3EAB489BCCA3A`。
2. 第一次用 PowerShell 5.1 的 `Get-Content/Set-Content` 改写，默认 ANSI 把中文写坏，红线是 SyntaxError（**无效变异**）；立即从改前备份还原，sha256 复核与改前一致。
3. 改用 .NET UTF8 无 BOM 只把 `'timecode': {'in':` 临时改成 `'mutated_timecode': {'in':`，`import engine` 正常，sha256 `AF94CD787A70F5454162AF896CDC04F4089072A59B65E7A70F9CBA69DA01C792`。
4. 跑 V1：`KeyError: 'timecode'`，1 test FAILED（有效变红）。
5. 从备份还原，sha256 复核 `148E63…CA3A` 与改前完全一致，V1 复跑 OK。

## 实际命令计数

共执行 **23 条**前台 PowerShell 命令：unittest／smoke **11 条**（含 2 次测试桩修正、1 次不带 PYTHONPATH 的失败批次、1 次无效变异下的 red）、只读 git／diff 核对 **5 条**、文件复制／哈希／变异 **7 条**。全部在 15 分钟内返回；最长一条是 8 个消费方测试同批（`test_recovery_delivery_e2e`＋`test_ui_edges` 等 119 条）322.7 秒。没有后台任务、没有超时。

实跑命令与结果：

- `python -B -m unittest tests.test_req_s12_anchors tests.test_edit_adoption` → 18 OK
- `python -B -m unittest tests.test_integration` → 27 OK
- `python -B -m unittest tests.test_video_retention tests.test_critical_chains tests.test_delivery_scope tests.test_edit_export tests.test_req_s13_anchors tests.test_stage_completion_service` → 111 条中 109 OK、2 条 ImportError（缺 `tests/` 到 PYTHONPATH，非产品问题）
- `PYTHONPATH=tests python -B -m unittest tests.test_recovery_delivery_e2e tests.test_ui_edges` → 119 OK
- `PYTHONPATH=tests python -B -m unittest tests.test_editing_scope tests.test_handoff_bundle` → 24 OK
- `PYTHONPATH=tests python -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_layers` → 10 OK
- `python -B smoke_test.py` → 8/8

## 改了哪些既有测试的哪个预期

| 文件::测试 | 改动 | 为什么 |
| --- | --- | --- |
| `tests/test_integration.py::PartialAssembleTests::test_partial_assemble_skips_unready_shots` | `[item["shot"] for item in manifest]` → `manifest["schema"]` 断言 ＋ `manifest["manifest"]` | 清单顶层由数组改为 `{'schema','manifest'}`（本任务明确要求顶层版本字段），镜头行本身未变 |
| `tests/test_integration.py::PartialAssembleTests::test_missing_file_is_skipped_instead_of_crashing` | `[item["shot"] for item in manifest]` → `manifest["manifest"]` | 同上 |
| `tests/test_edit_adoption.py::EditBundleTests::test_bundle_binds_master_and_indexes` | `[item['shot'] for item in index]` → `index['schema']` 断言 ＋ `index['manifest']` | 同上；旧格式仍由同文件 `test_legacy_index_still_reads` 与本轮 V3 用例覆盖 |

## 断言未动声明

没有删除、弱化或跳过任何既有断言；除上表 3 处“按新契约同步读取形状并各加一条 schema 断言”外，其余断言未动。新增断言见 `tests/test_req_s12_anchors.py` 两条 S12-34 用例。

## 需裁决事项

1. **车道是 detached HEAD**：`git branch --show-current` 为空、`git status` 显示 `Not currently on any branch`。按 `AGENTS.md` §2.5 提交方规则 detached HEAD 不得开工；本执行方按任务书在该工作树作业，提交前请切回分支或确认此车道用途。
2. **`edit_manifest.json` 顶层形状变化**：由数组改为 `{'schema':2,'manifest':[…]}` 是为满足“顶层版本字段”。本树 Python 读取方已全部兼容旧格式；若树外还有第三方脚本按旧数组解析，需要同步（本轮 grep 只覆盖本树 `.py`）。`edit_bundle.json.manifest` 保持数组未变。
3. **音轨／字幕归属口径**：按“文件名整词含镜头号”从 `edits.json.inputs` 归属到镜头。S11 现有产物常是整集文件（`整段配音.mp3`、`<集>.srt`、`配音分句/批次/001_SH001_…mp3` 中的批次文件又不在 `edit_inputs` 顶层扫描范围内），这类文件不会自动归到任何单镜，对应镜头的 `audio／subtitles` 会是 `[]`。若产品要求“整集音轨挂到每镜”或新建显式镜头→配音映射，需要新裁决（本轮按“只登记已有来源、不新采集”执行）。
4. 任务书允许“受影响的既有测试（只同步预期值）”；本轮 3 处改的是清单读取形状而非纯预期值，已在上表逐条说明。

## 自检结论

- 验收标准：V1–V5 均满足（见上）。
- 改动范围：`engine.py`、`docs/stages/S12_后期剪辑.md`、`tests/test_req_s12_anchors.py`、`tests/test_integration.py`、`tests/test_edit_adoption.py`；无其它文件（`git status` 已核对）。
- 未引入新问题：成片编码／EDL／FCPXML 文本未变（`edit_export` 未改，`test_edit_export` 绿；V1 直接比对 EDL 时间码）；S13 读 `edit_bundle.json.manifest` 不变，相关测试（`test_req_s13_anchors`、`test_stage_completion_service`、`test_delivery_scope`）绿。
- 未提交、未领号、未改 `project_status.md`／`AGENTS.md`、未读 `private/`、未碰用户真实项目数据（全部临时目录）。
- **结论：通过**，等待调度方独立验收与提交。

## 独立验收（Claude，车道 lane_c2 内隐藏桌面运行）

- 范围：1 个生产文件（engine.py）、1 份 docs/stages（S12）、3 个测试文件（test_req_s12_anchors 追加两条；test_integration 两处、test_edit_adoption 一处按新顶层形状同步读取方式，已逐条核对仅改读取形状并各加 schema 断言）。执行方为官方 deepseek-v4-flash（WorkBuddy 国内站账号被限，已回落）。
- 锚点与消费方：S12 锚点、edit_adoption、integration、editing_scope、handoff_bundle、video_retention、critical_chains、delivery_scope、edit_export、req_s13_anchors、stage_completion_service、recovery_delivery_e2e 全绿；架构追溯与分层 OK。
- 门禁：smoke_test.py 8/8；smoke_test.py --architecture 通过。
- 变异：回退 engine.py 的生产改动，S12-34 两条锚点变红（9 条中 2 个 ERROR），还原后 sha256 一致（148e6350…）。
- test_ui_edges：隐藏桌面上 12 条失败；把 c2 改动整体回退后在同一车道基线跑，同样 9 条失败（隐藏桌面不做字体行高与滚轮几何），多出的 3 条单独重跑全部通过（与并行 GUI 抢占有关）；失败均为界面几何，与清单无关。
- 未跑：run_selftests 全量与 --all --safe（本轮不属触发条件）。
- 待裁决（执行方登记）：整集音轨／整段字幕不会自动归到单镜，对应镜头 audio/subtitles 为空数组；树外脚本若按旧数组解析清单需同步。
