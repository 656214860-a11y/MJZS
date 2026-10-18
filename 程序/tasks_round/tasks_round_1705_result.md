# R1705 功能轮（SKILL 文档）：03 初步分镜／07 分镜定稿接入 sd-decision-engine

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮，但只改阶段 SKILL、docs 与测试，没有改产品源码；按 §2.7 先写 REQ／DES，再改 SKILL，最后补测试。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 8/8 通过；定向单测与 `test_aigc_package_diff` 通过。`run_selftests` 的 `import_all` 被并行 R1706 的 `client_profiles.py:156` 语法错误阻断，4 个测试文件无法启动；`smoke_test.py --affected` 与 `--architecture` 两次尝试均未取到结果（见 C）。未跑全量安全自检。
3. **project_status.md 的欠账少了吗？** 本轮没改源码，不增加源码轮欠账；未跑全量，状态页未改（任务书禁止改 `project_status.md`）。

## A 现状核对

- 01 已在 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md:33` 引用决策引擎，只取步骤 2 与前 3 列，并明确把情境 ID、80/15/5、雷区留给 03／07。
- 03 原「按职责引用」只有 `sd-storyboard-engine` 与三个打戏引擎；07 原「新版子技能章节」只有 `sd-storyboard-engine` 与 `sd-feed-engine`，两处都没有 `sd-decision-engine`。本轮已补。
- 决策引擎步骤 3–6 与三份 reference 的可选 ID、权重、雷区、6 列表格均已核对；`context-mapping.md` §八 明确景别阶梯跃迁与机位配额以既有权威为准，本轮照此只写一句边界。
- 03 的实际初稿是 `03初步分镜/分镜拆分/EP…_分镜.json`；`storyboard_draft.json` 是 `storyboard_selection.sync_draft_outputs` 生成的已采用索引（`storyboard_selection.py:203,244-249`），不适合承载锚点表。07 `storyboard_final.finalize` 用 `copy.deepcopy(read(source))` 读源（`storyboard_final.py:48`），顶层与镜头扩展字段会原样保留；`prop_assets.normalize_shot` 与 `shot_batches.normalize` 也都基于副本补字段。
- 07 现有资产对齐口径是 `storyboard-asset-sync` 的缺项清单加 `名称编号对照.json`（`storyboard_final.py:46`）；本轮只在这条清单的分镜编号旁增加追溯列，不改资产编号解析与锁定规则。

## B 改动

- `程序/docs/REQUIREMENTS.md`：新增 `REQ-S03-52`（03 接决策引擎步骤 3–6、追溯字段与落点）与 `REQ-S07-54`（07 只核对保持、对齐清单增加追溯列）。
- `程序/docs/DESIGN.md`：新增 `DES-S03-51`、`DES-S07-53`，并在 S03／S07 测试锚定表各加一行 `test_req_anchor_s03_s07`。
- `程序/skills/03初步分镜SKILL/pipeline-storyboard-draft.skill.md`：在「V7.4.20 按职责引用」新增决策引擎条目，链接总入口与 `context-mapping.md`／`emotion-anchor-table.md`／`forbidden-zone-whitelist.md` 的具体锚点；写明以 01 节拍表为输入、不重切节拍、E-ID 禁止编造、80/15/5、雷区自查，以及镜头级 `beat_no`／`context_id`／`forbidden_limits` 与顶层 `beat_source`／`emotion_anchor_table`／`shot_count_decision`／`forbidden_zone_report`。另加一句说明落点是实际初稿 JSON，不是派生索引。
- `程序/skills/07分镜定稿SKILL/pipeline-storyboard-final.skill.md`：在「新版子技能章节」新增一条，只链接 07 用得到的雷区判定流程与锚点表格式；写明定稿不重做选型、不补造 E-ID，只核对并保持 03 的三类追溯字段；资产对齐清单以分镜编号为主键，右侧增加一列「节拍＃／E-ID」追溯（`beat_no`／`context_id` 组合）。
- `程序/维护记录/AIGC包阶段归属.json`：只改 `sd-decision-engine` 一行，`stages` 改为 `["01","03","07"]`，note 改为“01 节拍已吸收；03 选 E-ID／权重／雷区、07 追溯核对已接”。其余三行未动。
- `程序/tests/test_req_anchor_s03_s07.py`（新增）：2 条用例，钉 03／07 的决策引擎链接存在、锚点存在、追溯字段与清单口径存在；没有改任何既有断言，没有 skip。
- 未新增代码、路径常量、执行门禁或文件路径；未改 `sd-decision-engine` 包与 00 包内文件；未全文注入原包，只做链接与取舍说明。

## C 验证

| 命令／项 | 实际结果 |
| --- | --- |
| `python -B -m unittest tests.test_req_anchor_s03_s07` | 2/2 通过 |
| `python -B -m unittest tests.test_workflow_writing_stages` | 6/6 通过 |
| 直接 unittest：`test_skill_reference_closure test_master_skill test_aigc_package_diff test_req_anchor_s03_s07` | 共 41 条；40 条通过，1 条是 `test_codex_skill_sync` 的加载器 import 错误（缺 `tests` 路径），不是产品断言失败 |
| 直接 unittest：`test_codex_skill_sync`（补 `program;tests` 到 PYTHONPATH） | 11/11 通过 |
| `python -B run_selftests.py -k test_workflow_writing_stages test_skill_reference_closure test_codex_skill_sync test_skill_registry_parse test_aigc_package_diff test_master_skill test_req_anchor_s03_s07` | 未完成：`client_profiles.py:156` 语法错误导致 `import_all` 失败；4 个文件红（`test_master_skill`／`test_skill_reference_closure`／`test_codex_skill_sync`／`test_workflow_writing_stages`）。`test_req_anchor_s03_s07` 2 条、`test_skill_registry_parse` 2 条、`test_aigc_package_diff` 9 条通过 |
| `python -B smoke_test.py` | 8/8 通过 |
| `python -B smoke_test.py --affected workflow_settings skill_registry` | 两次尝试均无输出；第一次约 150 秒、第二次约 8 分钟，CPU 基本停滞，主动中止。未取得结果，需 Claude 在无并行自检的会话复跑 |
| `python -B smoke_test.py --architecture` | 一次尝试约 150 秒无输出，主动中止；未取得结果 |
| `python -B -m unittest tests.architecture.test_requirement_traceability` | 3/4 通过；红项为 `REQ-S01-53/54/55/56` 没有测试锚定，均属并行 R1706 的客户端适配条目，不是本轮新增 |
| `python -B 维护记录/基准脚本/aigc_package_diff.py --json` | `ok=True`、`changes=0`、`broken_links=0`、`unlinked_engines=1`（仅 `assets`） |
| `codex_skill_sync.sync_codex_skills`（临时 home） | `pipeline-storyboard-draft`、`pipeline-storyboard-final` 均在 `written`；无冲突、无错误。仓库内没有需要同步的阶段技能清单 |
| `run_selftests.py --all --safe` | 未运行（任务书禁止） |

## D 断言未动与留给 Claude／用户的事项

### 断言未动

没有改动、弱化或删除任何既有断言；新增测试文件只增加 2 条用例，未加 skip。`test_workflow_writing_stages`、`test_skill_reference_closure`、`test_codex_skill_sync` 的既有断言均未动。

### 留给 Claude／用户

1. **并行 R1706 的语法错误阻断门禁**：`client_profiles.py:156` 的列表推导缺右括号，`run_selftests` 的 `import_all` 直接失败。该文件不在本轮范围，未修；请在验收前由 R1706 修好。
2. **并行 R1706 的需求锚定欠账**：`REQ-S01-53/54/55/56` 是 ✅ 但没有测试锚定，`test_requirement_traceability` 因此红；与本轮无关。
3. **03 锚点表落点**：选在实际初稿 `03初步分镜/分镜拆分/EP…_分镜.json` 顶层，原因是 `storyboard_draft.json` 由程序派生、会重建，不能承载自定义节；`finalize` 的 deepcopy 能把它带进 07。若 Claude 认为应另立文件，需按任务书先裁决，本轮没有新增路径。
4. **`beat_no` 口径**：为避免多场同号，本轮写成 `场<场次>-节拍<编号>`（如 `场2-节拍3`）；01 节拍表仍是“场次／节拍＃”两列。若不认可这个拼接格式，可改为两个字段，但需要同时改 03／07 与测试。
5. **与 reference「不写进分镜本体」的取舍**：`emotion-anchor-table.md` §四 要求节拍号与 E-ID 不进分镜本体；本轮把“本体”理解为 `frame_prompt`／`video_prompt` 正文，追溯字段只放镜头 JSON 元数据。若要求 JSON 里也不出现，则 07 无法逐镜追溯，需要重新裁决。
6. **引用闭包体积**：按现有 `_inline_skill_report(strict=True)` 实测，03 为 138,007 字符、07 为 175,675 字符，均低于 300,000 上限；新增三份 reference 会被现有机制整文件内联。若“不全文注入”按运行期口径理解，需要另做引用裁剪机制，本轮按任务书只做链接、未改机制。
7. **未实机验证**：没有用新 SKILL 在应用里真跑一次 03／07，锚点表与追溯字段的实际产出质量待用户复验。

## E 提交

未提交，由 Claude 验收后提交。
