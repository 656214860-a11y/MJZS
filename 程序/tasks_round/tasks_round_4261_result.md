# R4261 结果：FIX-S11-E1B（run_lines 结果未知误标 failed／放开文案按状态分句）
<!-- round-evidence: {"commit_base": "79fa309b", "credential_hits": 0, "evidence_sha256": "523d26b4cf698dd0", "exit": 0, "failed": 0, "passed": 86, "round": 4261, "tests": "run_selftests.py -k tts request_recording"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。只修卡面两处缺陷：R4223 已合入代码里 `run_lines` 把 connection reset／URLError 超时／响应读取中断标为确定失败并允许自动重发（重复扣费风险）；`unknown_release_prompt` 固定文案对 unsaved 句与事实不符（N137＋N143＋N146 合并，E2 已验收合入，本卡独立修复）。
- （二）测试跑了吗、三个基线：跑了。先红后绿——改前定向 8 条失败用例（原因原文见下）；改后 `run_selftests.py -k tts request_recording` 86 条 0 红、退出码 0；`smoke_test.py --architecture` 700 条 OK、退出码 0（首跑曾因新增 elif 链把 `run_lines` 嵌套抬到 6 层红 1 条，按棘轮提示改辅助函数＋提前返回后复跑全绿）。默认冒烟 8/8 本轮未跑（卡面未列）。
- （三）欠账少了吗：少了。P1 计费安全缺口闭合：结果未知的网络失败不再被自动重发；unsaved 句放开文案不再对用户说假话。

## 缺陷复现方式

新增 `TtsRejectAndReleaseTests` 用例（`程序/tests/test_tts.py`）在未改产品代码前运行：

- `Mock(side_effect=urllib.error.URLError(TimeoutError("timed out")))` 注入 `run_lines(generate=…, project=…)` → 时间轴记 `failed`＋`not_submitted`，第二次运行会重发（探针 `.agent-tmp/accept-s11-urlerror-probe.py` 的同一缺陷，本工作树无 `.agent-tmp`，未读探针文件，按卡面规格复现）。
- `URLError` 底层为 `ConnectionResetError`（类型化／`<urlopen error [WinError 10054]…>` 文案／`connection reset by peer` 三种形态）→ 同样记 `failed`。
- `publish_bytes` 抛 `ConnectionResetError`（已付费后落盘阶段）→ 落 `paid and isinstance(exc, OSError)` 分支误标 `unsaved`。
- `unknown_release_prompt` 对 unsaved 批输出固定句「已核对服务商后台，这些请求没有扣费，重新发送」，与「已付费未保存」事实不符。

## 改前红的条数与原因（原文）

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tts request_recording`：共 86 条用例，2 个文件有红，8 条失败用例（test_tts 7、test_request_recording 1）：

- `test_urlerror_wrapped_timeout_is_uncertain_and_never_resent`：`AssertionError: 'failed' != 'uncertain'`
- `test_urlerror_wrapped_reset_is_uncertain_and_never_resent`（3 个 subTest：类型化 ConnectionResetError／WinError 10054 文案／reset by peer 文案）：`AssertionError: 'failed' != 'uncertain'`
- `test_reset_after_payment_is_uncertain_not_unsaved`：`AssertionError: 'unsaved' != 'uncertain'`
- `test_release_prompt_unsaved_lines_tell_repaid_truth`：`'这些句子上次已付费但没有保存成功，重新发送会再付一次' not found in '下列句子上次结果未知，不会自动重发：\nS1 · 第一句 · 请求 rid-1\n\n已核对服务商后台，这些请求没有扣费，重新发送'`
- `test_release_prompt_mixed_batch_groups_each_state`：同上句未找到（混合批无 unsaved 分组文案）
- `test_quote_and_release_cover_unsaved_via_l3`（契约有意变更后断言）：同上句未找到

改前即绿的边界用例（保持口径不变）：refused→failed＋重发、TimeoutError→uncertain 不重发、直连 `ConnectionResetError`／`IncompleteRead`→uncertain、纯 uncertain 批沿用旧句。

## 改了哪几处

- `程序/domain/tts_api.py`（+68/-17）：
  - 535–537 行新增 `_PROVEN_UNREACHABLE_MARKERS`：「连接根本没建立」的可证明文案（refused／10061／econnrefused／getaddrinfo／name resolution／name or service／11001／11004）。
  - 540–562 行新增 `_send_outcome(exc)`（L1 边界识别）：`reason`（URLError 取 `.reason`）属 `ConnectionResetError／ConnectionAbortedError／BrokenPipeError／TimeoutError／http.client.IncompleteRead` → `'uncertain'`；`ConnectionRefusedError／socket.gaierror` → `'failed'`；URLError 其余 OSError reason → `'uncertain'`；字符串 reason 命中可证明标记 → `'failed'`，否则 `'uncertain'`；非网络异常 → `None`。
  - 565–582 行新增 `_line_outcome(exc, started, paid, project)`（L2 状态迁移）：`uncertain` 最先判（网络层 OSError 先于「已付费写盘失败」分支）；`paid` 且非网络 OSError/ValueError → `unsaved`；`failed` 或 TTSRejected 或（URLError 且 started）→ `failed`＋`not_submitted`；project 且 started → `uncertain`；否则 `failed`。
  - 657–658 行 `run_lines` except 分支改为单行调用 `_line_outcome`（elif 链是 AST 嵌套，新链会把函数嵌套抬到 6 层触发棘轮，故按「辅助函数＋提前返回」压平）。
  - 730–756 行 `unknown_release_prompt` 按句子状态分组：sending／uncertain 组沿用「下列句子上次结果未知，不会自动重发：…已核对服务商后台，这些请求没有扣费，重新发送」；unsaved 组「下列句子上次已付费但没有保存成功，不会自动重发：…这些句子上次已付费但没有保存成功，重新发送会再付一次」；混合批两段以空行分隔各自列出；`indexes` 与 `release_unknown` 口径不变。
- `程序/tests/test_tts.py`（+143/-0）：`TtsRejectAndReleaseTests` 新增 8 条用例＋`_manifest_with_states` 夹具。
- `程序/tests/test_request_recording.py`（+3/-1）：`test_quote_and_release_cover_unsaved_via_l3` 第 209–213 行断言更新——unsaved 句断言新文案并 `assertNotIn('这些请求没有扣费')`。
- `程序/tasks_round/tasks_round_4261_result.md`：本文件。

## 测试契约有意变更说明（§2.4）

- `test_quote_and_release_cover_unsaved_via_l3` 原断言 `assertIn('已核对服务商后台，这些请求没有扣费，重新发送', tip['text'])` 针对 **unsaved** 句，与卡面 N137（固定文案对 unsaved 与事实不符）直接冲突；按「契约有意变更可同步断言」改为断言 unsaved 新文案＋不含「没有扣费」句，其余断言与流程（release→pending）保持原样。判断依据：卡面『设计』第 2 条明确 unsaved 句文案为「这些句子上次已付费但没有保存成功，重新发送会再付一次」。
- 未删除、未弱化、未 skip 任何既有断言；既有 `test_tts_budget_blocks_then_timeout_survives_resume`、`test_direct_tts_stable_id_prevents_resend_after_timeout` 原样通过。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `git status --porcelain`（开工） | 无输出，退出码 0 |
| `git log -1 --format=%h` | `79fa309b`，退出码 0 |
| `git rev-parse --abbrev-ref HEAD` | `codex/fix-s11-e1b`，退出码 0 |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tts request_recording`（改前） | 86 条中 8 条失败用例（见上），退出码 1 |
| 同命令（改后） | 86 条 0 红，`ALL TESTS PASSED`，退出码 0 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（第 1 次） | `FAILED (failures=1)`：`test_nesting_does_not_grow`——`'tts_api.py::run_lines 6 层 > 上限 5'`，退出码 1 |
| 同命令（第 2 次，压平后原样重跑） | `Ran 700 tests in 352.706s`，`OK`，退出码 0 |
| `git diff --numstat` | `68 17 程序/domain/tts_api.py`、`3 1 程序/tests/test_request_recording.py`、`143 0 程序/tests/test_tts.py`，退出码 0 |

改后定向输出尾部原文：

```
共 86 条用例，3.0 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

架构输出尾部原文：

```
----------------------------------------------------------------------
Ran 700 tests in 352.706s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证项

- 未跑默认冒烟与全量 `run_selftests.py --all --safe`（卡面未列；合并轮出口会跑）。
- 未建真实 Desktop/Tk 窗口；UI 确认框只消费 `unknown_release_prompt` 返回的 `text`，分组文案对界面调用无签名变化（本卡不改 UI）。
- 真实网络路径的 URLError 文案匹配依赖 `_PROVEN_UNREACHABLE_MARKERS` 关键词；Linux 中文版之外的小众文案形态未逐一实测，识别不出的 URLError 一律按 `uncertain`（人工核对）处理，方向安全。
- `.agent-tmp/accept-s11-urlerror-probe.py` 位于主工作区、不在本工作树内，读取被拒后未重试；缺陷按卡面规格以新测试独立复现。

## 待文档同步（DOC-S11B 在改，本卡不动文档）

`程序/docs/stages/S11_配音与字幕.md` 建议同步点：

- IF-S11-60（约 165 行）：「网络失败→URLError」宜补「URLError 内 refused／DNS 失败一类记 failed 可重发；超时、连接重置、读取中断记 uncertain 不自动重发；付费后写盘 OSError/ValueError 记 unsaved」。
- IF-S11-49（约 158 行）：「不确定不自动重发」的适用面宜补「含付费后网络层 OSError（不再落 unsaved）」。
- REQ/DES 待核实放开交互：人工放开确认文案按句子状态分组——unsaved 句文案为「这些句子上次已付费但没有保存成功，重新发送会再付一次」。

## 卡外发现（只记录）

- `synthesize_full_track`（tts_api.py:400–418）的 `definite` 判定仍把 URLError 一律算 `failed`：整段配音路径与逐句口径不一致，属 FIX-S11-E2 已定边界，本卡不动，建议后续评估是否对齐 `_send_outcome`。

## 提交

- 本车道已领取 R4261，未重复 claim；本文件随 `dev.py commit` 同批提交，证据 `tasks_round/evidence/R4261.json` 由提交工具生成，commit hash 见交付报告。
