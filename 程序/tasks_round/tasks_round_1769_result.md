# R1769：功能轮——后期剪辑成果确认须对上 edit_bundle.json 的成片摘要（S12-24，C6）

## 轮次类型与三问

- **轮次类型**：功能轮（`AGENTS.md` §3.1）。已按 §2.7 先改 S12 需求与设计，再先写失败用例，最后实现。
- **测试跑了吗**：已按任务书窄范围运行。新增用例 2/2 通过；任务书列出的 8 组命令全部通过；默认冒烟 8 passed、0 failed。未运行任务书禁止的 `run_selftests.py`、`--architecture`、全量和 `--affected`。
- **三个基线过了吗**：默认冒烟 8/8 通过；架构门禁的全量计数未测（任务书禁止 `--architecture`），任务书指定的 `test_requirement_traceability` 5/5、`test_layers` 5/5 通过；全量安全回归未运行，不声称有全量绿凭据。
- **欠账少了吗**：没有。本轮未运行全量安全回归、未产生全量凭据、未领号或提交，不能声称全量欠账减少；`维护记录/需求锚定基线.json` 的 `untested_done` 仍为 `[]`。

## 根因与改动

- **根因**：`stage_completion_service.prepare_media_completion` 对 `edit` 阶段只做路径、后缀和 FFprobe 技术校验；`_validate_media_completion` 只复核待审清单中的摘要。因此同目录的任一单镜视频也能通过成果确认。
- **生产改动**：`stage_completion_service.py`
  - `_edit_bundle_status(path, digest)`：读取所选文件同目录的 `edit_bundle.json`，要求 `master_sha256 == digest`（不比较文件名），且 `qc.errors` 为非空列表时拒绝；清单不是字典、缺字段或格式错误时抛 `ValueError`；无清单时返回“无来源清单，须人工核对”警告。
  - `prepare_media_completion`：`edit` 准备阶段调用该判据，并把无清单警告写入待审清单。
  - `_validate_media_completion`：`edit` 最终确认及完成证据复核时再次调用该判据，防止冻结后清单或质检结论变化。
- **文档改动**：`docs/stages/S12_后期剪辑.md`
  - `REQ-S12-24` 改为 ✅，写入准备、确认、完成证据复核三处判据及用户文案。
  - 新增 `DES-S12-24`，测试锚定表改为实际测试名。
- **测试改动**：`tests/test_stage_completion_service.py`
  - 追加 `test_req_s12_24_edit_completion_bundle_must_match_selected_master`。
  - 追加 `test_req_s12_24_edit_completion_rechecks_bundle_before_final_confirmation`。
  - 选择该文件是因为它已有 `MediaCompletionTests` 的项目夹具、FFprobe 替身和确认流程夹具；复用可避免在 `test_editing_scope.py` 复制第二套夹具。

## V1-V7 实测命令与计数

命令均在 `D:\漫剧制作助手\.wt\lane_c6\程序` 下执行，解释器为 `D:\漫剧制作助手\运行环境\Python\python.exe -B`，并设置 `PYTHONPATH=tests`。

| 验收 | 命令 | 实测结果 |
| --- | --- | --- |
| V1/V2/V3 新用例 | `python -B -m unittest tests.test_stage_completion_service.MediaCompletionTests.test_req_s12_24_edit_completion_bundle_must_match_selected_master tests.test_stage_completion_service.MediaCompletionTests.test_req_s12_24_edit_completion_rechecks_bundle_before_final_confirmation` | 2/2 OK |
| V4 剪辑范围 | `python -B -m unittest tests.test_editing_scope` | 15/15 OK |
| V4 完成服务全文件 | `python -B -m unittest tests.test_stage_completion_service` | 34/34 OK |
| V4 交付范围 | `python -B -m unittest tests.test_delivery_scope` | 18/18 OK |
| V4 媒体导入 | `python -B -m unittest tests.test_media_import_validation` | 12/12 OK |
| V4 交付锚点 | `python -B -m unittest tests.test_req_s13_anchors` | 23/23 OK |
| V7 需求追踪 | `python -B -m unittest tests.architecture.test_requirement_traceability` | 5/5 OK |
| V7 分层门禁 | `python -B -m unittest tests.architecture.test_layers` | 5/5 OK |
| 默认冒烟 | `python -B smoke_test.py` | 8 passed, 0 failed |

- 需求追踪查询确认 `REQ-S12-24` 正好命中两个新测试。
- `git diff --check` 通过。
- PowerShell 会把 unittest 的原生 stderr 包装成退出码 1；上述每组均以 `OK` 结束，计数以 unittest 汇总为准，未出现失败或错误。
- 任务书禁止的命令均未运行；本表不把窄门禁结果冒充完整架构门禁。

## V1-V3 覆盖情况

- **V1**：同一导出目录有 `edit_bundle.json`、`MASTER.mp4` 和两个单镜文件。`MASTER.mp4` 准备并确认通过；`S01.mp4`、`S02.mp4` 均被拒；把 `MASTER.mp4` 字节复制为 `final_cut.mp4` 后通过，证明不绑定文件名。
- **V2**：`master_sha256` 被改成不匹配值时拒绝；`qc.errors` 非空时拒绝；清单为列表或缺字段时均抛 `ValueError`，未出现未处理异常。
- **V3**：删除 `edit_bundle.json` 后，外部／旧项目成片仍可准备和确认；待审清单包含“无来源清单，须人工核对”。

## 先红与变异证据

- **先红**：实现前运行两个新增用例，结果为 `failures=4`；两个单镜文件都被接受，证明旧逻辑没有区分成片与单镜。
- **变异**：在 `_edit_bundle_status` 临时加入提前 `return ''`，绕过新增判据；只跑 V1 新用例，结果为 `Ran 1 test`、`FAILED (failures=3)`，其中 `S01.mp4`、`S02.mp4` 均报 `AssertionError: ValueError not raised`。
- **还原核验**：变异文件还原后 `stage_completion_service.py` 的 SHA256 为 `7FABDD587C2157FDF7045C9968C5DAE2A2E933F3AA11A8649CD1639977508D5F`，与变异前一致。

## 断言声明

**断言未动。** 未修改、弱化、删除或跳过任何既有测试断言；只在 `tests/test_stage_completion_service.py` 追加两个新测试。

## 改动范围与数据安全

- 实际修改仅三处：`stage_completion_service.py`、`docs/stages/S12_后期剪辑.md`、`tests/test_stage_completion_service.py`。
- 未执行 git 写命令、未领号、未提交、未改 `project_status.md` 或 `AGENTS.md`。
- 未读取 `private\`、`.env`，未触碰用户真实项目数据；测试仅使用临时目录。

## 需裁决事项与风险

1. **无 bundle 的放行已实现警告**：不只写在文档里；警告进入待审清单 `warnings`。最终确认和完成证据复核不因警告阻断，符合任务书“外部成片／旧项目保持放行”。
2. **同目录存在过期或损坏 bundle 的合法成片会被拦**：这是任务书“有清单就必须一致且格式有效”的直接结果；如果外部剪辑软件把新成片放进旧批次目录并留下旧清单，需要重新导出或清理该清单。字节完全相同、仅改名的成片可通过。
3. **`delivery` 未改**：其 `build_delivery_qc` 仍保留既有更严格的成片文件名比较；本轮只改 `edit`，没有触碰 `audio`／`delivery` 行为。后续若要统一“只比摘要不比文件名”，应另立契约轮。
4. **未发现**收窄允许目录、后缀集合或影响无 bundle 外部导入的路径；全量架构与全量安全回归未跑，最终合并前仍由调度方按任务书验收。

## 独立验收（advisor，lane_c6 真实环境直接运行，已补修复后 engine.py）

- 范围：stage_completion_service.py、docs/stages/S12_后期剪辑.md、tests/test_stage_completion_service.py（3 文件）。
- diff 审查：`_edit_bundle_status` 无清单返回「无来源清单，须人工核对」警告并放行；有清单要求 `master_sha256==digest` 且 `qc.errors` 为空，否则抛 ValueError；prepare 写入 warnings、validate 复核，逻辑符合 S12-24。
- 测试（lane_c6，engine.py 已换修复版）：test_edit_adoption＋test_integration＋test_req_s12_anchors＋test_req_s10_anchors＋test_editing_scope＋test_stage_completion_service 共 101 用例 OK（此前因 engine.py 回退红的 3 文件已转绿）；smoke_test.py 8/8。
- 真实项目只读核验：D:\漫剧下载\项目 下 3 个项目的「11后期剪辑」目录均无 edit_bundle.json → 走「无清单放行」路径，不误拦；bundle 路径由构造夹具（V1/V2）覆盖。
- 全量架构与完整安全全量：未跑（C6 任务书禁止 run_selftests/--architecture/全量）。
- 断言未动：只追加 2 条测试，既有断言未改。
