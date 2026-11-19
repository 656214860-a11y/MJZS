# R3812 结果：F 维阶段操作接入索引＋开发机走查轮（任务书执行轮）
<!-- round-evidence: {"commit_base": "a83298e1", "credential_hits": 0, "evidence_sha256": "5dccd55aafe9271c", "exit": 0, "failed": 0, "passed": 135, "round": 3812, "tests": "run_selftests.py -k s07 final shot_batches storyboard_final stage_completion final_bundle"} -->

- 轮次类型：任务书执行轮（F 项「现有制作阶段新增操作的接入索引」）。文档＋取证脚本轮，无产品代码改动。
- 是否跑测试：跑了。新增 `scripts/acceptance_stage_op_walkthrough.py` 隐藏桌面三态走查 3/3 通过（12.4s，`tasks_round/evidence/R3812/stage_op_walkthrough.json`）；定向自检 `run_selftests.py -k s07 final shot_batches storyboard_final stage_completion final_bundle` 结果见 §4。
- 积压是否下降：是——验收台账 F 项具备接入索引、真实调用链分层标注、三态走查证据与剩余缺口记录，可交用户裁决是否采纳为后续新增操作的模板。

## 1. 三问

1. **什么类型轮**：任务书 F 项——选一个已实现阶段操作，在阶段设计文档补接入索引；说明三种影响范围；开发机三态走查；推演任务书示例操作的复用/缺口。
2. **是否跑测试**：跑了——走查脚本 3/3、定向自检（结果以提交回执为准）。
3. **积压是否下降**：是——F 项从「待验」转「完成（待用户裁决采纳）」。

## 2. 选定操作与接入索引

- **操作**：S07 分镜定稿「手动同步资产」（`final` 阶段唯一手动入口，REQ-S07-30）。
- **索引落点**：`docs/stages/S07_分镜定稿.md` 新增「### 接入索引（R3812 F 维验收补登）」，含：可运行真实样例、界面入口（`ui/storyboard_files.py` 按钮→`desktop.make_final_storyboard`）、服务/编排入口（`storyboard_final_controller.finalize_stage_storyboard`→`storyboard_final.finalize`）、最小改动文件、旧项目兼容点、定向验收用例名、可定位代码符号。
- **三种影响范围**已按实际调用链写明：只查询显示（L4+L2 只读）、参与放行（L3 `stage_parallel.GATES`/`stage_completion_service.checks`，并注明与 REQ-S07-11「缺图不阻止定稿」口径的冲突需用户裁决）、写正式产物（L3 注入发布器＋L0 schema 双写＋旧版读回）。

## 3. 开发机三态走查（`scripts/acceptance_stage_op_walkthrough.py`，隐藏桌面真实 Desktop）

| 态 | 输入 | 结果 |
| --- | --- | --- |
| 正常输入 | 临时项目：资产清单＋已采用分镜（含 1 个未导入资产 CHAR_002）→ 定稿页选中 → 点「手动同步资产」 | `07分镜定稿/分镜/EP001_分镜定稿_*/` 产出 `episode.json`（sha256 记录）＋`assets.json`＋`产物来源关系.json`；每镜 `batch_id` 已回填；`CHAR_002` 记入 `missing_assets`、`assets_ready=false`；`stage_parallel.batches_ready` ok+started；工作稿经回收站退役（原路径消失，回收站留副本） |
| 缺失输入 | 无已采用分镜的项目 → 同一按钮 | 报「请先在列表中选择 JSON」落状态栏（`desktop.safe`→`notifier.error` 路径），零产出 |
| 旧项目 | 定稿产物预置于旧目录 `06分镜定稿/分镜/`（只读兼容位），工作稿仍被采用 | 同一操作签名复用命中旧目录：不新建 `07分镜定稿`、旧 `episode.json` 保留、`batches_ready` ok |

- 走查脚本本身作为「可运行真实样例」登记进索引；构造项目复用 `tests/test_req_s07_anchors.py::_project` 同构夹具。
- **任务书示例推演**：「分镜定稿前列出缺少已采用角色参考图的镜头」未实现、不作声称——索引中标注可复用件（`asset_bindings`/`reference_images`/`asset_status`/`missing_assets`、`asset_plan_gateway` 资产行、`FinalStoryboardController` 只读预览）与仍需改动件（新增只读查询函数、L4 列表区块；若要变门禁需用户裁决，因 REQ-S07-11 现行口径为「缺图不阻止定稿」）。

## 4. 测试与基线

- `smoke_test.py`：R3800 已跑 9/9；本轮未改产品代码。
- `run_selftests.py -k s07 final shot_batches storyboard_final stage_completion final_bundle`：结果以提交回执为准。
- 架构门禁：本轮只动 `docs/`、`scripts/`、`tasks_round/`，无 `.py` 产品代码变更；走查脚本本身经隐藏桌面真实运行验证。

## 5. 未测／限制（如实记录）

- 走查覆盖「手动同步资产」单操作；S07 自动定稿（`poll_auto_final`/`automatic_finalize_decision`）由 `test_final_service` 锚定，本轮未做界面级自动链走查。
- 旧项目态模拟的是「旧目录布局＋工作稿仍采用」的典型旧项目；更老的 schema 版本产物未构造（`artifact_schema` 版本容忍由单元测试覆盖）。
- 「缺参考图镜头列表」为推演，非已实现功能；若立项需先回填 REQ/DES 再按索引实施。
