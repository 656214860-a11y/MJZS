# R4346 结果：FIX-S11-E3 逐句配音改一句只重做变了的句子
<!-- round-evidence: {"commit_base": "82e396a27", "credential_hits": 0, "evidence_sha256": "b1b9fda463b76655", "exit": 0, "failed": 0, "passed": 95, "round": 4346, "tests": "run_selftests.py -k tts audio_role_binding"} -->

## 开头三问

1. **本轮类型**：修复轮（§3.2），任务卡 FIX-S11-E3，波次 W2，车道 `codex/fix-s11-e3`，基准 `82e396a2`。只改 `domain/tts_api.py` 与两个允许测试文件；`ui/desktop_media_pages.py` 未改（episode 早已端到端透传，本卡无需新增传参，净增量 0）。
2. **测试与基线**：定向命令改前 95 条用例 5 条红（全部是新增复现测试，红因即缺陷本身）；改后 95 条 0 红、`ALL TESTS PASSED`、退出码 0（条数 = 改前 90 + 新增 5）。`smoke_test.py --architecture`：702 条 OK、退出码 0。默认冒烟与全量未跑（卡面未列）。
3. **欠账**：本轮无新欠账。改前红的 5 条全部转绿，既有断言未动。

## 缺陷复现方式

一集逐句配完后改一句台词、插入一句或只调镜头时长，再点「逐句配音（分句）」：`resume_folder` 只认整批指纹（`批次.json` 的 `signature`），指纹失配返回 `None`，UI 落到全新 `配音批次_日期` 目录，`pending_lines`／`batch_cost_preview` 因空清单把全部句子报成待付——重复付费重做已有成品（REQ-S11-12「每句按身份沿用」未落实）。

新增 5 条测试在未改产品的状态下变红，红因一致（`resume_folder` 返回 `None` 而非该集旧批目录）：

- `test_tts.TtsBatchResumeTests.test_changing_one_line_reuses_the_rest`：`AssertionError: None != WindowsPath('...配音批次_20260101') : 整批指纹失配应按集标识找回该集最近的批次`
- `test_tts.TtsBatchResumeTests.test_inserted_line_reuses_surrounding_lines`：`AssertionError: None != WindowsPath('...101')`
- `test_tts.TtsBatchResumeTests.test_changed_shot_timing_reuses_everything`：`AssertionError: None != WindowsPath('...101')`
- `test_tts.TtsBatchResumeTests.test_same_shot_same_text_pairs_in_order`：`AssertionError: None != WindowsPath('...101')`
- `test_audio_role_binding.EpisodeBindingTests.test_episode_fallback_stays_within_its_episode`：`AssertionError: None != WindowsPath('...批一') : 同一集最近的批次按集标识回退`

改前红共 5 条（test_tts 4 条、test_audio_role_binding 1 条），均断言 `resume_folder(改动后的台词, 集标识)` 应回退到该集最近的批次目录。

## 改了哪几处（文件:行号）

`程序/domain/tts_api.py`：

- `resume_folder`（438–457）：整批指纹匹配仍最先判定；全目录扫完无指纹命中且调用方给了 episode 时，退回该集 `批次.json` 里 `episode` 相同的最近批次目录；没有 `episode` 的旧批次（含本卡之前写的批次）保持现状只认指纹，不跨集匹配。
- 新增 `_line_file_path`（467–473）：清单 `file` 相对本批目录定位；指向旧批次的相对路径（相对「配音分句」目录）退回父目录解析。
- 新增 `_identity`（476–479）：句子身份＝`LINE_IDENTITY_FIELDS`（`shot_id`、`text`、`voice`、`speed`、`model`、`endpoint`，219 行）逐项相同，不含位置与起止时间。
- `line_done`（482–502）：签名由「按序号查清单比对」改为「判一份旧清单条目是不是可沿用成品」，文件核验（sha256／非空兜底）原样保留。
- 新增 `_line_verdicts`（505–533）：逐句续跑判定，沿用 `{新句序号: 旧条目}` 与待核实 `{新句序号: 旧条目清单序号}`；同身份句按出现次序一一配对（第一处对第一处）；沿用优先于待核实。
- `pending_lines`（552–557）、`batch_cost_preview`（560–571）、`run_lines`（659–685）：三处共用 `_line_verdicts` 同一口径（卡面设计第 5 条「续跑与付费预览共用」）。
- `run_lines`（659–685）：批次指纹照旧写入（`episode` 字段随指纹一并落 `批次.json`）；判定后整批先按新句序号落盘——沿用条 `{**旧条目, **当前句}`（起止时间更新为当前值，`file`/`sha256`/`request_id` 沿用）、待核实条 `{**旧条目, **当前句}`（状态与 `request_id` 保留）、新句 `failed` 占位；中断后再跑这份清单仍记得沿用与待核实。循环内沿用／待核实判定改查 `done`／`blocked`。
- `unknown_line_indexes`（779–784）：改用 `_line_verdicts`；返回值语义为**清单序号**（待核实旧条目在时间轴里的位置），与既有消费者 `release_unknown`（按 `manifest[index - 1]` 定位，`desktop_media_pages._line_quote_gate` 105 行原样透传 `release['indexes']`）口径一致；位置对齐的旧场景序号值不变。
- `unknown_release_prompt`（798–806）：`lines[index - 1]` 加越界与非 dict 保护（清单序号错位时可能超过当前句数），文案分组与字段原样。

`程序/tests/test_tts.py`（+4 条，494–589）：改一句台词只重做该句（含 `batch_cost_preview` 只报 1 句待付）；中间插入一句只报 1 句；只改起止时间报 0 句且沿用句起止更新为当前值；同镜同文本两句按序配对不共用文件。

`程序/tests/test_audio_role_binding.py`（+1 条，114–130）：无 `episode` 旧批次不被按集回退认领；同集最近批次回退；别集批次不回退。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git status --porcelain`（开工） | 0 | 无输出 |
| `git log -1 --format=%h` | 0 | `82e396a2` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/fix-s11-e3` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tts audio_role_binding`（改前） | 1 | 95 条用例 5 条红（原因原文见上节） |
| 同上（改后） | 0 | 「共 95 条用例，3.1 秒；0 个文件有红」「实际跳过 0 条用例」「ALL TESTS PASSED」 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 702 tests in 276.908s` `OK` `✅ 架构治理测试：tests/architecture` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 轮次 4346 |

## 未验证项

- 未在真实 Desktop／Tk 窗口里点「逐句配音（分句）」；UI 链路未改（`desktop_audio_direct.run_tts_per_line` 把 `resume_folder` 返回值当续跑目录传给报价闸与 `run_tts_lines`，49–66 行原样）。
- 跨批次相对路径 `file`（`_line_file_path` 父目录兜底）是防御分支：现有流程原地续跑，`file` 恒为本批目录内文件名，没有测试触发父目录解析。
- 未跑默认冒烟与全量 `run_selftests.py --all --safe`（卡面未列）。

## 待文档同步（DOC-S11 车道）

- `docs/stages/S11_配音与字幕.md` 的 IF-S11-49／UX-S11-03 等条目如需描述续跑口径，应记为：续跑目录＝同集最近批次（整批指纹失配时按集标识回退）；句子沿用按「镜头、文本、音色、语速、模型、端点」身份在旧清单查，不要求位置与起止时间相同；同身份句按出现次序配对。

## 卡外发现（只记录不顺手修）

- 无新增；`unknown_release_prompt` 的 `indexes` 语义由句序号收紧为清单序号属本卡契约内变更（消费者链路端到端一致，见上）。

## 被拒绝的命令

- `Get-ChildItem tasks_round -Filter "tasks_round_43*_result.md" ...`（枚举近期结果文件，非卡面命令）：用户拒绝一次，未重试，改用直接读已知结果文件。
- 会话早期在 bash 会话里执行定向命令因中文路径被 shell 吞掉报 `command not found`（退出码 127），改按卡面用 PowerShell 原样执行成功。

## 提交

- 车道 `codex/fix-s11-e3`，领号 R4346；提交命令与哈希见交付报告。
