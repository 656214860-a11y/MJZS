# R1736：验证/基线轮——S03 初步分镜补 12 条需求测试锚点（REQ03）

任务书：`REQ03_taskbook.md`。工作树：`D:\漫剧制作助手\.wt\lane_req03\程序`（只改本树，未执行任何 git 写命令）。
生产代码（非 `tests/` 的 `.py`）零改动；只新增测试、给已有测试加 docstring、删基线编号。

## 逐条结果

| 编号 | 锚点测试 | 对应的断言 → 需求原文 | 自证红的输出（改反实现后） | 结论 |
| --- | --- | --- | --- | --- |
| REQ-S03-03 | `tests/test_req_s03_anchors.py::ReqS03AnchorTests.test_req_s03_03_workflow_lock_blocks_manual_and_auto_before_start`（新增） | `start(..., 'manual')` 与 `start(..., 'auto')` 都返回含「故事画幅」「发送框内写明制作锁」的锁错误且未打开分镜任务 → 「启动前先过总控制作锁门禁，手动与自动同样阻断」；桌面按钮 `pet_storyboard_batch()` 只调 `stage_handler_registry.start` → 「入口只有 stage_handler_registry.start()」 | `AssertionError: '故事画幅' not found in ''`（把 `_workflow_lock_error` 改为恒返回空串） | 锚定 |
| REQ-S03-04 | 同文件 `test_req_s03_04_empty_work_plan_skips_agent_and_only_auto_reports`（新增） | `todo`/`revise` 皆空时手动返回 `''` 且 `open_storyboard_skill` 未调用；自动且 `auto.active=='storyboard'` 时播报「已确认所有已选结构剧本的分镜均已生成并采用」；有待办时才 `open_storyboard_skill(None)` → 「两者都为空时不再启动 Agent…自动触发播报…手动触发无动作」 | `AssertionError: - opened`（把 `_start_storyboard` 改成恒打开技能页） | 锚定 |
| REQ-S03-06 | 同文件 `test_req_s03_06_single_json_per_episode_and_stitch_across_scenes`（新增） | `stage_parallel.brief_text('storyboard')` 含「同一集只输出一份分镜 JSON」「不生成副本、不换文件名重写」「按剧本顺序拼接」「上一场结束状态＝下一场开始状态」；同集同内容两份 JSON 经 `catalog` 只剩 1 份 → 「同一集只输出一份分镜 JSON，已存在则跳过并说明…各场景做完后按剧本顺序拼接，并核对跨场景衔接」 | `AssertionError: 2 != 1 : 同一集的同内容副本只能算一份分镜`（把 `storyboard_storage.unique_entries` 改成原样返回） | 锚定 |
| REQ-S03-15 | 同文件 `test_req_s03_15_contract_requires_triplet_without_duplicating_archives`（新增） | `storyboard_contract.rules()` 含「每镜先写清镜头三元组」「核心人物／画面主体」「可见动作」「景别机位与运镜」「按动作闭合点切镜」「不要把结构剧本的角色／场景／道具档案重复写入分镜初稿」 → 需求原文两句 | `AssertionError: '每镜先写清镜头三元组' not found in ''`（`rules()` 返回空串） | 锚定 |
| REQ-S03-20 | 同文件 `test_req_s03_20_storyboard_stage_does_not_write_batch_id`（新增） | 阶段并行提示含「批次划分（batch_id）属于 07 分镜定稿，本阶段不写」；`storyboard_contract.rules()` 不含 `batch_id` → 「03 不写 batch_id，批次划分归 07」 | `AssertionError: '批次划分（batch_id）属于 07 分镜定稿，本阶段不写' not found in ''`（`brief_text` 返回空串） | 锚定 |
| REQ-S03-30 | 同文件 `test_req_s03_30_adoption_validates_the_whole_batch_before_writing`（新增） | 已采用一份后：新增坏时长分镜报错含文件名与「时长」，已采用份来源被删时新增合法份也整批报错含该文件名与「不存在或已迁移」，`_sync_plan` 未被调用，`adopted` 仍是原一份 → 「采用前对整批（已采用＋新增）逐份校验…任一份不过则整批拒绝，不改采用记录也不改资产计划，报错带文件名与具体问题」 | `AssertionError: ValueError not raised`（把 `source_script_error` 改成恒返回空串） | 锚定 |
| REQ-S03-31 | 同文件 `test_req_s03_31_syncs_assets_before_writing_adoption_and_falls_back`（新增） | `_sync_plan` 被调用时 `ui_settings.json` 尚无 `adopted_storyboards`（先同步资产再写清单）；写完含相对 posix 路径的 `adopted_storyboards` 与 `frame_json`；仅有 `frame_json` 时 `adopted()` 回退读它；项目外路径被拒 → 需求原文两句 | `AssertionError: + [WindowsPath(.../EP001_分镜.json)]`（把 `storyboard_selection._adopted` 改成恒返回空） | 锚定 |
| REQ-S03-32 | 同文件 `test_req_s03_32_auto_adopt_batches_new_files_and_syncs_plan_once`（新增） | 两份旧 JSON 同批采用、刚写入的进 `waiting`、坏文件只进 `failed`，`_sync_plan` 恰好 1 次；重复调用 `adopted` 为空且不再同步 → 「只处理新出现的分镜 JSON；刚写入不足 10 秒的文件记为 waiting 下轮再看；不合法的只跳过它…整批只同步一次资产计划；重复调用不重复采用」 | `AssertionError: + WindowsPath(.../EP002_分镜.json)`（把 `_validate` 改成恒通过，坏文件被一起采用） | 锚定 |
| REQ-S03-33 | 同文件 `test_req_s03_33_remove_only_updates_lists_and_focus_requires_adoption`（新增） | 未采用份 `focus` 抛 `ValueError`；`remove` 后剩余清单为第一份、`_sync_plan` 收到剩余清单、文件仍在磁盘、`frame_json` 指向剩余份；对已采用份 `focus` 生效 → 「取消采用只改采用清单与当前分镜指针，并按剩余清单重同步资产计划，不删分镜文件；当前分镜指针只能指向已采用的分镜」 | `AssertionError: ValueError not raised`（把 `focus` 改成不校验是否已采用） | 锚定 |
| REQ-S03-34 | 同文件 `test_req_s03_34_prune_invalid_adoptions_keeps_json_and_assets`（新增） | 删除第二份来源剧本后 `prune_invalid_adoptions` 只返回该份、其 JSON 仍在、采用清单只剩第一份、历史 `assets.json` 内容不变 → 「来源剧本已失效的 JSON 由 prune_invalid_adoptions 取消采用，保留 JSON 文件和历史资产」 | `AssertionError: + ('...EP002_分镜.json',)`（`source_script_error` 恒空，失效份未被取消） | 锚定 |
| REQ-S03-35 | 同文件 `test_req_s03_35_seed_storyboard_is_not_counted_as_produced`（新增） | 种子 JSON（`EP001`/`SH001`/`待编写`，含改名副本）经 `catalog` 返回空、`storyboard_produced_scripts` 为空集 → 「刚创建项目时的种子分镜不当作已制作的分镜」 | `AssertionError: - 'title': 'EP001 · 未命名（1镜） · 分镜工作稿'}]`（`_is_initial_storyboard` 恒 False） | 锚定 |
| REQ-S03-41 | 同文件 `test_req_s03_41_completion_needs_an_adopted_storyboard_with_shots`（新增） | 无采用时 `(False, '还没有已采用且含镜头的分镜 JSON')`；采用 `shots=[]` 的 JSON 同样 False 同句；采用含镜头 JSON 时 `(True, '')` → 「完成 = 至少有一份已采用且含镜头的分镜 JSON…没有已采用分镜时报『还没有已采用且含镜头的分镜 JSON』」 | `AssertionError: + (False, '还没有已采用且含镜头的分镜 JSON')`（把 `stage_parallel._adopted` 改成空镜头也返回哨兵） | 锚定 |

结论：12 条全部锚定，无一条需要降为 🟡；`docs/stages/S03_初步分镜.md` 未改。
已有测试无需加 docstring：本批 12 条在既有测试里都没有真正检验需求内容，全部新写在 `tests/test_req_s03_anchors.py`。

## 改动清单

- 新增 `tests/test_req_s03_anchors.py`（文件 docstring 含「REQ-S03 测试锚定」，12 个 `test_req_s03_xx_*`，不 import tkinter、不加 skip）。
- `维护记录/需求锚定基线.json`：从 `untested_done` 删除上述 12 个 S03 编号，其余编号不动；保持 `indent=2`、`ensure_ascii=False`、末尾换行。
- 未改任何生产代码；未改 `docs/stages/S03_初步分镜.md`；未新增 skip，`维护记录/skip台账.json` 未改。

## 验证命令与实际计数

1. `PYTHONPATH=.;tests python -B -m unittest tests.test_req_s03_anchors tests.architecture.test_requirement_traceability`
   → `Ran 17 tests ... OK`（12 条新锚点 + 5 条门禁），0 红。
2. 先红后绿自证：临时脚本逐条用 `unittest.mock.patch` 把实现改反（不落盘、不改生产代码；S03-03 的「唯一入口」一条另在 `tempfile` 里用改过的 `stage_handler_registry.py` 副本执行），12 条全部转红，输出见上表；恢复后 12 条全绿。
3. `python -B run_selftests.py -k test_req_s03` → 见下节。

## selftests 计数与需裁决事项

- `python -B run_selftests.py -k test_req_s03`：首次在跨树 GUI 令牌上等待（占用方 PID 39276 是另一条车道 `lane_spsplit` 的 `--serial` 全量，自 17:27 起持有），等待超过 5 分钟后按任务书停止，未反复重跑；该进程已终止。
- 重跑（后台，令牌已释放）实际输出：`定向：忽略增量台账，执行 1 个匹配测试文件` / `test_req_s03_anchors 12 条 0.9 秒` / `共 12 条用例，2.0 秒；0 个文件有红` / `实际跳过 0 条用例` / `ALL TESTS PASSED`，exit=0。
- 门禁查询：`python -B tests/architecture/test_requirement_traceability.py --find REQ-S03-30` → `tests/test_req_s03_anchors.py: ReqS03AnchorTests.test_req_s03_30_adoption_validates_the_whole_batch_before_writing`。
- 需裁决：任务书第 2 条验证写的是 `run_selftests.py -k <改过 docstring 的测试文件名关键词> test_req_s03`，但本轮没有给既有测试加 docstring——既有 S03 测试（`test_storyboard_scope`、`test_stage_parallel`、`test_workflow` 等）对这批 12 条需求都只是沾边，加注释会变成假锚点，所以 12 条全部新写在 `tests/test_req_s03_anchors.py`。若仍要求跑既有文件名关键词，可加跑 `-k test_storyboard_scope test_stage_parallel test_workflow test_req_s03`（这些文件本轮未改动）。
- 本轮未执行任何 git 写命令，未领号、未提交；工作树改动仅 3 个文件：新增 `tests/test_req_s03_anchors.py`、新增本结果文件、`维护记录/需求锚定基线.json` 删 12 行。

## 独立验收（Claude，主工作区）

- 车道 diff 应用到 R1735；`test_req_s03_anchors`＋`test_requirement_traceability` 17 条 OK。
- 抽查自证：mock `storyboard_contract.rules` 返回空串，锚点测试转红。
- 裁决：既有测试只沾边、不加假 docstring，全部新写——接受。
