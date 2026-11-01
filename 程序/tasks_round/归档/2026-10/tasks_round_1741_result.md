# R1741：验证/基线轮——S05 资产管理 10 条锚定、1 条降 🟡（REQ05）

执行者：opencode（DeepSeek Harness）。车道：`D:\漫剧制作助手\.wt\lane_req05\程序`；解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`。
未执行任何 git 写命令，未领号、未提交，未改 `project_status.md`、`AGENTS.md`，未改任何生产代码（非 `tests/` 的 `.py` 零改动）。

## 逐条结果

| 编号 | 锚点测试 | 对应的断言 → 需求原文 | 自证红的输出（改反实现／mock 后） | 结论 |
| --- | --- | --- | --- | --- |
| REQ-S05-01 | `tests/test_req_s05_anchors.py::ReqS05AnchorTests.test_req_s05_01_only_adopted_storyboards_export_assets`（新增） | 未采用分镜作为来源时 `_sync_plan(scope='adopted', _adopting=False)` 返回 `{}`、落盘清单没有 `CHAR_002`；已采用分镜才产出 `CHAR_001`；没有采用分镜时 `active_source`／`_sync_plan` 报「手动采用分镜」且不生成 `assets.json` → 「清单只由『已采用』的分镜 JSON 导出……没有采用任何分镜时，`active_source` 报……不凭空建清单」 | `AssertionError: {'CHAR_002': {'name': 'CHAR_002', ...}} != {}`（把 `storyboard_adoption_contract.adopted` 改成返回全部候选分镜） | 锚定 |
| REQ-S05-03 | 无（尝试的断言未保留） | `asset_contract.defaults('scene', {'aspect_ratio': '9:16', 'resolution': '1080x1920'})['resolution']` 应为 `1080x1920` → 「画幅默认 `16:9`、分辨率默认 `1920x1080`，项目锁优先」；同时 `stage_lock_requirements('assets') == ()` 与 `resolve_aspect_ratio` 的锁优先已通过 | `AssertionError: REQ-S05-03 项目锁 resolution 未生效`；探测输出 `defaults(scene, lock)= {'aspect_ratio': '9:16', 'resolution': '1920x1080'}` | **降为 🟡**：画幅按项目锁优先，但 `resolution` 固定写死 `1920x1080`，未读项目锁 `resolution`；测试命令天然红，按任务书删测试并改文档。编号因门禁要求（非 ✅ 不得留在基线）从基线删除（见「需裁决事项」） |
| REQ-S05-04 | 同文件 `test_req_s05_04_shared_references_are_reused_without_formal_asset_registration`（新增） | `import_animatic_references` 把参考图按内容摘要写入 `shared_reference_dir`，`animatic_reference_paths` 能读到；写入后资产阶段没有 `assets/资产清单/assets.json` 或 `assets.json` → 「共享参考图目录 `reference_images` 由分镜预演准备、本阶段复用……本地 ComfyUI 草图不进入正式资产登记」 | `AssertionError: Tuples differ: (.../wrong.png,) != (.../_shared/reference_images/<digest>.png,)`（把 `import_animatic_references` 换成写到别处的桩件） | 锚定 |
| REQ-S05-11 | 同文件 `test_req_s05_11_sync_preserves_existing_fields_and_records_used_in`（新增）；`tests/test_asset_contract.py::DefaultsTests.test_normalize_fills_missing_keys_without_touching_the_rest`、`test_normalize_keeps_existing_values`（docstring 认领） | 同步前 `name='旧名'`、`character_anchor='银发'`、`locked=True`、`custom='keep'`、`used_in=['OLD']`；同步后这些值全部保留，缺失的 `base_anchor` 被补上，`used_in` 增加 `SH001` → 「只补缺失的契约字段……已有值一个不动；`used_in` 记录引用该资产的镜头编号」 | `AssertionError: '覆盖' != '旧名'`（把 `asset_contract.normalize` 改成覆盖 `name`） | 锚定 |
| REQ-S05-12 | `tests/test_assets.py::NormalizeShotTests.test_ordinary_prop_moves_out`、`test_inline_text`（docstring 认领） | 普通道具从 `props`／`first_frame_assets` 移到 `ordinary_props`；`inline_text` 把名称与描述写进镜头提示词 → 「只有被标记『需要独立资产』的道具才进清单……普通道具写进镜头提示词，不分配编号」 | 既有测试，未新增红证 | 已有测试锚定 |
| REQ-S05-15 | `tests/test_asset_contract.py::MissingAndSchemaTests.test_missing_ids_reports_unknown_and_promptless_assets`；`tests/test_confirm_gates.py::ObjectiveTests.test_g04_catches_a_missing_asset`（docstring 认领） | `missing_ids` 报出缺 `image_prompt` 的 `CHAR_001`、清单里没有的 `CHAR_002`／`LOC_001`；G-04 对缺资产的 `CHAR_007` 判不通过 → 「分镜引用的编号在清单里缺 `name` 或生图提示词，由 `missing_ids` 报出（门禁 G-04 使用）」 | 既有测试，未新增红证 | 已有测试锚定 |
| REQ-S05-16 | `tests/test_asset_plan.py::AssetPlanPublicationTests.test_bundle_publication_writes_and_verifies_all_four_files`、`test_failed_bundle_publication_restores_all_existing_files`（docstring 认领） | 四份文件（名称编号对照／`assets.json`／来源／导入进度）写入后逐一复核；第二次保存抛 `OSError` 时四份文件字节全部回到发布前 → 「清单、名称编号对照、来源、导入进度四份文件作为一个发布包原子写入，写后复核；失败则整体回滚」 | 既有测试，未新增红证 | 已有测试锚定 |
| REQ-S05-17 | 同文件 `test_req_s05_17_only_registered_existing_images_count_as_imported`（新增） | 计划自带 `image: assets/characters/fake.png` 时状态为「待导入」且行里没有 `image`；登记表指向存在的 `real.png` 时状态为「已导入」；登记后文件被删又回到「待导入」 → 「只有登记过且文件真实存在于资产库内的图片才算『已导入』；计划里自带的 `image` 路径不被采信」 | `AssertionError: '已导入' != '待导入'`（用 wrapper 把 `_sync_plan` 的每一行强制改成已导入） | 锚定 |
| REQ-S05-22 | 同文件 `test_req_s05_22_backend_names_come_from_l0_and_formal_assets_need_online`（新增） | `cloud_assets.LOCAL == production_model_contract.ASSET_LOCAL_MODEL`、`cloud_assets.MODELS == list(ASSET_CLOUD_MODELS)`；`asset_batch_service.current_model(temp)` 默认返回本地模型；`require_formal_asset_generation(online_model=False)` 报「线上 API 模型」，`True` 放行 → 「本地与云端模型名由 L0 `production_model_contract` 统一；正式资产请选线上 API 模型」 | `AssertionError: '错误模型' != '本地 FLUX.2 Klein / 自定义工作流'`（把 `current_model` 换成错误模型） | 锚定 |
| REQ-S05-33 | 同文件 `test_req_s05_33_deletion_recycles_and_restores_the_same_bytes`（新增）；`tests/test_asset_image_removal_service.py::test_recycles_image_then_clears_registered_pointer`、`tests/test_asset_image_restore_service.py::test_restores_image_then_registers_pointer`（docstring 认领） | `asset_impact`／`deletion_references` 列出引用镜头 `SH001` 且 `protected=True`；`remove_asset_image` 后原位置文件消失；`restore_asset_image` 后同一路径字节与删除前完全一致 → 「删除前由 `deletion_references`／`asset_impact` 列出被哪些镜头引用；删除走回收站；恢复可还原相同字节」 | `AssertionError: True is not false : 删除后原位置不再保留文件`（把 `storage_maintenance.recycle_paths` 换成不搬文件的桩件） | 锚定 |
| REQ-S05-41 | 同文件 `test_req_s05_41_canon_admission_and_conflicts_do_not_overwrite_assets`（新增） | `pipeline-assets.skill.md` 含「资产缺少可追溯来源、身份锚点或版本时不得进入正典」「发现冲突只生成待修复项，不覆盖已确认资产」、定向读取 `continuity-bible.md#the-identity-string-contract` 与 `image-model-adapters.md#4-character-consistency-playbook-cheapest-first`、以及「不得加载 00 包全文」；`conflict_candidates` 对冲突只返回 G-08 待修复项，输入资产字典前后不变 → 需求原文三句 | `AssertionError: '资产缺少可追溯来源、身份锚点或版本时不得进入正典' not found in '---\nname: pipeline-assets...'`（把 `_skill_text` 返回的文本替换掉该句） | 锚定（SKILL 条款）；冲突行为同时有行为断言 |

结论：11 条中 10 条锚定（01/04/11/12/15/16/17/22/33/41），1 条降为 🟡（03）。`docs/stages/S05_资产管理.md` 只改了 REQ-S05-03 这一行。

## 改动清单

- 新增 `tests/test_req_s05_anchors.py`：文件 docstring 含「REQ-S05 测试锚定」，7 个 `test_req_s05_xx_*`，不 import tkinter、不加 skip。
- docstring 认领（只加测试方法 docstring，断言未动）：
  - `tests/test_assets.py`：REQ-S05-12（`test_ordinary_prop_moves_out`、`test_inline_text`）。
  - `tests/test_asset_contract.py`：REQ-S05-11（两个 `normalize` 测试）、REQ-S05-15（`test_missing_ids_reports_unknown_and_promptless_assets`）。
  - `tests/test_asset_plan.py`：REQ-S05-16（两个发布包测试）。
  - `tests/test_confirm_gates.py`：REQ-S05-15（`test_g04_catches_a_missing_asset`）。
  - `tests/test_asset_image_removal_service.py`、`tests/test_asset_image_restore_service.py`：REQ-S05-33（回收／恢复）。
- `docs/stages/S05_资产管理.md`：REQ-S05-03 由 ✅ 改为 🟡，句末加 `（REQ05 核对：画幅按项目锁优先，但 resolution 固定为 1920x1080，未按项目锁 resolution 取值）`。
- `维护记录/需求锚定基线.json`：从 `untested_done` 删除 01/03/04/11/12/15/16/17/22/33/41 共 11 个 S05 编号，其余编号未动；保持 `indent=2`、`ensure_ascii=False`、末尾换行。
- 新增本结果文件。

## 验证命令与实际计数

1. `PYTHONPATH=.;tests python -B -m unittest tests.test_req_s05_anchors tests.architecture.test_requirement_traceability`
   → `Ran 12 tests in 1.106s`，`OK`，exit=0（7 条新锚点 + 5 条门禁），0 红。
2. 先红后绿自证：临时脚本用 `unittest.mock.patch` 逐条改反实现／替换桩件（不落盘、不改生产代码），7 条新测试全部转红，输出见上表；恢复后 `python -B -m unittest tests.test_req_s05_anchors` → `Ran 7 tests ... OK`。
3. `python -B run_selftests.py -k test_assets test_asset_contract test_asset_plan test_confirm_gates test_asset_image_removal_service test_asset_image_restore_service test_req_s05`
   → `定向：忽略增量台账，执行 11 个匹配测试文件`；`共 180 条用例，4.9 秒；0 个文件有红`；`实际跳过 0 条用例`；`ALL TESTS PASSED`，exit=0。
4. 未等待 GUI 令牌（本轮命令未进入 GUI 锁等待），未新增 skip，`维护记录/skip台账.json` 未改。

## 需裁决事项

1. **REQ-S05-03 的基线处理与任务书字面冲突**：任务书要求降 🟡 后「编号留在基线」，但 `tests/architecture/test_requirement_traceability.py::test_baseline_only_shrinks` 明确要求「不再是 ✅ 的编号必须从基线删除」。保留 `REQ-S05-03` 时门禁红：`AssertionError: Lists differ: ['REQ-S05-03'] != []`。为满足任务书第 1 条验证（门禁 0 红），已按门禁删除该编号。若必须保留，需要同时改门禁规则，请拍板。
2. **REQ-S05-03 的需求解释**：`asset_contract.defaults('scene', lock, pref)` 只让 `aspect_ratio` 读项目锁，`resolution` 固定 `1920x1080`；`script_contract.stage_lock_requirements('assets') == ()`（本阶段确实不要求锁值），`resolve_aspect_ratio` 的优先级也正确。若需求里的「项目锁优先」只指画幅、分辨率允许固定默认，则本条可恢复 ✅ 并另补锚点；若 `resolution` 也必须读锁，则当前 🟡 与核对句准确。
3. **REQ-S05-41 的锚点形态**：该条主要由 `pipeline-assets.skill.md` 的 SKILL 条款实现（正典准入、定向注入），没有可执行的产品函数；测试按 SKILL 文本断言条款，并用 `conflict_candidates` 的行为断言补「冲突只生成待修复项、不覆盖资产」。若要求只以代码行为锚定，请给出可判定的代码入口。

## 独立验收（Claude，主工作区）

- 主树 `test_req_s05_anchors`＋追溯门禁 OK；`run_selftests -k` 覆盖 7 个相关测试文件全绿。
- 既有测试 diff 只含 docstring 行（`git diff -U0` 过滤后为空），断言未动。
- 核实降级：`asset_contract.py:71` 的 scene `resolution` 写死 `1920x1080`，不读项目锁，REQ-S05-03 标 🟡 属实；修复留作后续功能项。
- 基线冲突（车道基于旧 master）：以 HEAD 版为准删 S05 编号，`untested_done` 清空。
