# R4298 结果：S11 文档五条目同步到 FIX-S11-E1／E1B 新口径（DOC-S11B）
<!-- round-evidence: {"commit_base": "755c7e9d", "credential_hits": 0, "evidence_sha256": "5bdfc41d07ded10b", "exit": 0, "failed": 0, "passed": 0, "round": 4298, "tests": "docs-only"} -->

## 开头三问

1. **本轮类型**：纯文档同步轮（任务卡 DOC-S11B，波次 W2，车道 `codex/doc-s11b`，基准 `755c7e9d`）。只改 `docs/stages/S11_配音与字幕.md` 的 IF-S11-22／IF-S11-49／IF-S11-60／UX-S11-03／UX-S11-68 五个条目，文档只描述已合入 master 的代码（FIX-S11-E1 R4217→合入 R4223；FIX-S11-E1B R4261 已在 master，IF-S11-60 按 E1B 最终口径写）。未改任何 `.py`、测试文件与守卫常量。
2. **测试与基线**：文档守卫四件套跑了两次（改前、改后），各 34 条用例全过、0 个文件有红、`ALL TESTS PASSED`、退出码 0；用例数与改前相同（本卡不新增测试）。`smoke_test.py --architecture` 跑了一次：701 条 OK、退出码 0。默认冒烟与全量未跑（文档轮，卡面未列）。
3. **欠账**：本轮无新欠账。卡面「先写测试复现缺陷必须看到红」按卡内约定处理：本卡是纯文档同步，守卫测不到口径差异，改前即绿，原因是守卫不覆盖这几条口径（见下「缺陷复现方式」）。

## 缺陷复现方式

本卡无代码缺陷可复现：允许清单内没有代码文件，接口契约的「先写测试复现缺陷、再改产品」不适用（卡面背景第 3 条明示）。按卡面约定，先原样跑第一条验收命令并记下输出尾部：

```
共 34 条用例，1.1 秒；0 个文件有红
最慢 4 路工作单元：
  architecture.test_requirement_traceability    0.4 秒 / 5 条
  architecture.test_agent_doc_budget    0.1 秒 / 11 条
  architecture.test_stage_doc_sections    0.1 秒 / 10 条
  architecture.test_design_coverage    0.0 秒 / 8 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：（路径略）
最近 5 轮自检中位基线：100.6 秒

ALL TESTS PASSED
```

**改前绿，原因是守卫不覆盖这几条口径**：`test_stage_doc_sections` 只查两节结构、编号唯一、状态记号与反引号；`test_agent_doc_budget` 只管预算文件清单；`test_requirement_traceability` 只管 REQ 锚定；`test_design_coverage` 只管 specs 覆盖映射。五个条目的口径文字差异不在任何断言范围内。

## 代码依据（每个条目引用的函数名均在 master 定位过）

- `程序/domain/tts_api.py`：`UNKNOWN_LINE_STATES = ('sending','uncertain','unsaved')`（23 行）；`TTSRejected(ValueError)`（26 行）；`_send_outcome`（540–562：重置／超时／IncompleteRead→uncertain，refused／gaierror／可证明未建立文案→failed，其余 URLError→uncertain）；`_line_outcome`（565–582：uncertain 最先判→unsaved（paid 且非 TTSRejected 的 OSError/ValueError）→failed＋not_submitted（_send_outcome failed／TTSRejected）→started→uncertain→否则 failed）；`synthesize`（674–720：HTTP 状态→ValueError，4xx→TTSRejected，超时→TimeoutError，其余→URLError）；`run_lines`（585–671：同身份 UNKNOWN 句跳过并报「上次配音结果未知，请核对请求 …，未重复发送」）；`batch_cost_preview`（507–532）；`unknown_line_indexes`（723–736）；`unknown_release_prompt`（739–765：sending／uncertain 与 unsaved 分组文案）；`release_unknown`（768–788：改 `failed`＋`released_at`＋`not_submitted`）。
- `程序/stage_execution_service.py`：`release_tts_unknown`（38–41，L3 包 `release_unknown`＋`tts_gateway()`）。
- `程序/ui/desktop_media_pages.py`：`_line_quote_gate`（93–110：无待付句但有待核实时弹「逐句配音（待核实）」dangerous 确认，取消不放开不提交，确认后 `release_tts_unknown` 再报价）；`generate_tts_per_line`（742–767）。
- `程序/desktop.py`：`confirm`→`ask_confirmation`→`ConfirmDialog`（68–70、ui_widgets.py:966–1015，dangerous 为危险样式确认框）。
- 口径出处：`tasks_round_4217_result.md`（FIX-S11-E1 目标）、`tasks_round_4223_result.md`（合入）、`tasks_round_4261_result.md`（FIX-S11-E1B 最终口径＋「待文档同步」建议）。

## 改了哪几处（文件:行号，均为单行表格行替换）

`程序/docs/stages/S11_配音与字幕.md`（+5/-5）：

- 136 行 IF-S11-22（写出）：不自动重发同身份句 `sending`／`uncertain` 扩为 `sending`／`uncertain`／`unsaved`；补 HTTP 4xx（`TTSRejected`）与可证明连接没建立记 `failed`＋`not_submitted` 下次自动重发；请求成功但写盘失败记 `unsaved`。
- 158 行 IF-S11-49（完成判定与交接）：不重发判定扩为三种状态；补人工放开入口——报价无待付句但有待核实时可放开，`release_unknown` 把指定句改 `failed` 并记 `released_at` 与 `not_submitted`（L3 `release_tts_unknown`）；依据列补 `unknown_line_indexes`／`unknown_release_prompt`／`release_unknown`／`release_tts_unknown`／`_line_quote_gate`。
- 165 行 IF-S11-60（对外调用，按 E1B 最终口径）：synthesize 面保留原错误分类并补 4xx→`TTSRejected`；逐句落账按 `_send_outcome`／`_line_outcome` 写全——4xx 与可证明连接没建立记 `failed`＋`not_submitted` 允许自动重发，超时／连接重置／读取中断与其余网络失败记 `uncertain` 不自动重发，已付费后写盘失败记 `unsaved`，不自动重发状态为 `sending`／`uncertain`／`unsaved`。
- 198 行 UX-S11-03（控件与操作）：补「逐句配音（待核实）」确认框——报价无待付句但有待核实时弹出（dangerous，列镜号、台词前 20 字、请求号，文案按状态分句：sending／uncertain「已核对服务商后台，这些请求没有扣费，重新发送」，unsaved「重新发送会再付一次」）；确认放开并继续走付费确认，取消不放开不提交；入口 `unknown_release_prompt`＋`release_unknown`（L3 `release_tts_unknown`）、界面 `_line_quote_gate`。
- 230 行 UX-S11-68（页面状态）：接续提示的待核实句扩为 `sending`／`uncertain`／`unsaved` 三种。

`程序/tasks_round/tasks_round_4298_result.md`：本文件。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git status --porcelain`（开工） | 0 | 无输出 |
| `git log -1 --format=%h` | 0 | `755c7e9d` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/doc-s11b` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（改前） | 0 | 34 条用例 0 红，`ALL TESTS PASSED`（尾部原文见上） |
| 同上（改后） | 0 | 34 条用例 0 红，`ALL TESTS PASSED`；尾部：「共 34 条用例，1.1 秒；0 个文件有红」「实际跳过 0 条用例：本机没有任何登记位被跳过」「ALL TESTS PASSED」 |
| `git diff --check` | 0 | 无输出 |
| `git diff --numstat` | 0 | `5	5	"程序/docs/stages/S11_配音与字幕.md"`（路径显示为八进制转义原文） |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 701 tests in 296.163s` `OK` `✅ 架构治理测试：tests/architecture` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 轮次 4298 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4298: DOC-S11B S11 文档同步 FIX-S11-E1 新口径" docs/stages/S11_配音与字幕.md tasks_round/tasks_round_4298_result.md` | 见提交输出 | 见下「提交」 |

## 未验证项

- 未在真实 Desktop／Tk 窗口里点过「逐句配音（待核实）」确认框；本卡只写文档，交互以 `desktop_media_pages._line_quote_gate`（93–110 行）与 `domain/tts_api.unknown_release_prompt`／`release_unknown`（739–788 行）源码为准。
- 未跑默认冒烟与全量 `run_selftests.py --all --safe`（文档轮，卡面未列）。
- IF-S11-60 里「其余网络失败→`URLError`」保留 synthesize 的抛出面描述；逐句落账的最终状态以 `_line_outcome` 为准，两层口径已在同一格内分开写明。

## 卡外发现（只记录不顺手修）

- `程序/docs/stages/S11_配音与字幕.md` 的 REQ-S11-12（22 行）与 DES-S11-12（81 行）仍写「状态为 sending／uncertain 的句子不自动重发」，未含 `unsaved`；本卡只许改五个 IF/UX 条目，REQ/DES 两行属卡外，建议后续文档卡一并同步。
- `synthesize_full_track`（`domain/tts_api.py:400-418`）的整段配音 `definite` 判定仍把 URLError 一律算 `failed`，与逐句 `_send_outcome` 口径不一致——R4261 结果文件已记为卡外发现（属 FIX-S11-E2 已定边界），本卡不动。

## 提交

- 车道 `codex/doc-s11b`，领号 R4298；提交命令与退出码见上表，commit hash 见交付报告。
