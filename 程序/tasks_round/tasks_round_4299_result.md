# R4299 结果：FIX-S11-E5（整段配音只念台词：build_script 去掉「角色名：」前缀）
<!-- round-evidence: {"commit_base": "755c7e9d", "credential_hits": 0, "evidence_sha256": "57a4c4d253877bc1", "exit": 0, "failed": 0, "passed": 107, "round": 4299, "tests": "run_selftests.py -k tts ui_edges_autopilot"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。卡面 FIX-S11-E5（AUD-US05 E-5，需求设计卡面 `.agent-tmp/需求设计-card-FIX-S11-E5.md`）：点「生成配音（TTS）」得到的音频只念台词，不念角色名、角色编号，也不念「未注明角色」。只改 `domain/tts_api.py` 的 `build_script` 与 `tests/test_tts.py`。
- （二）测试跑了吗、三个基线：跑了。先红后绿——改前定向 4 条失败用例（原因原文见下）；改后 `run_selftests.py -k tts ui_edges_autopilot` 107 条 0 红、退出码 0；`smoke_test.py --architecture` 701 条 OK、退出码 0。默认冒烟与全量 `--all --safe` 本轮未跑（卡面禁止运行卡面未列的命令，且未列入验收）。
- （三）欠账少了吗：少了。AUD-US05 E-5（中）闭合：整段配音发去合成的文本不再含说话人信息。

## 缺陷复现方式

`domain/tts_api.py` `build_script`（改前 282–284 行）把每句拼成 `f'{line["name"]}：{line["text"]}'`：`name` 由 `build_lines` 解析——有角色资料取显示名，无资料退回说话人 ID，都没有时是「未注明角色」（tts_api.py:273）。`ui/desktop_media_pages.py:724` 把该返回值直接送 `synthesize`，角色名会被 TTS 念出来。

新增/改写 `TtsBuildScriptTests` 用例（`程序/tests/test_tts.py`）在未改产品代码前运行 `run_selftests.py -k tts ui_edges_autopilot`，4 条红，红的原因与卡面缺陷一致（拼接文本里出现角色名／角色编号／空文本句）。

## 改前红的条数与原因（原文）

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tts ui_edges_autopilot`（改前）：共 107 条用例，1 个文件有红，4 条失败用例（均在 test_tts）：

- `test_build_script`：`AssertionError: '卡梅隆：你好\n无脸女：再见' != '你好\n再见'`（脚本带「角色名：」前缀）
- `test_build_script_speaks_only_dialogue`：`AssertionError: Lists differ: ['卡梅隆：你好', '无脸女：再见'] != ['你好', '再见']`
- `test_build_script_without_character_assets`：`AssertionError: 'CHAR_009：只有台词' != '只有台词'`（无角色资料时念角色编号）
- `test_build_script_skips_empty_text`：`AssertionError: 'CHAR_001：你好\nCHAR_001：\nCHAR_001：   \nCHAR_002：再见' != '你好\n再见'`（空文本句未跳过，且带编号前缀）

改前即绿、本轮保持绿的相关用例：`test_build_script_empty`（空对白 → `""`）、`tests/architecture/test_tts_publication_boundary.py` 3 条、`test_ui_edges_autopilot.py` 全部（整段／逐句配音 UI 用例只数合成调用次数与状态文案，不断言脚本文本）。

## 改了哪几处

- `程序/domain/tts_api.py`（282–285 行）：`build_script` 改为只拼 `line["text"]`（`str()` 归一）、句间换行、`str(text or "").strip()` 为空的句子跳过；函数说明同步改为「只念台词（不念角色名／编号），句间换行，空文本的句子跳过」。公开签名 `build_script(entries, assets=None)` 不变，仍复用 `build_lines`。
- `程序/tests/test_tts.py`（174–210 行，`TtsBuildScriptTests`）：`test_build_script` 按契约有意变更改写（见下节）；新增 `test_build_script_speaks_only_dialogue`、`test_build_script_without_character_assets`、`test_build_script_skips_empty_text` 三条。
- `程序/tasks_round/tasks_round_4299_result.md`：本文件。

## 测试契约有意变更说明（§2.4，卡面明文授权）

- `test_build_script`：原断言 `self.assertEqual(script, "卡梅隆：你好" + "\n" + "无脸女：再见")`（旧「角色名：台词」拼接口径）→ 新断言 `self.assertEqual(script, "你好" + "\n" + "再见")`。依据：需求设计卡面 FIX-S11-E5『设计』第 1 条「只拼 line["text"]，句间换行；空文本的句子跳过」与『测试用例』「拼出的文字不含角色名、角色编号和『未注明角色』」。用例名、输入数据（entries／assets）原样未动。
- `test_build_script_empty`：原断言 `build_script([], {}) == ""` 两种口径下结果一致，原样保留未改。
- 未删除、未弱化、未 skip 任何既有断言；其余测试文件零改动。

## 用户可见变化（卡面要求写明）

- 「生成配音（TTS）」整段配音的合成文本从「角色名：台词」逐行改为只含台词、句间换行；生成的音频不再念角色名、角色编号，也不念「未注明角色」。
- `script_signature` 的输入文本随之变化，指纹必然变化：已有整段成品（`整段配音.json` 标记的 signature）不再匹配，**下次点击会重新付费合成一次**，不会沿用旧成品（`reusable_full_track` 按 signature 判定，机制未改）。
- 界面 4000 字上限用的是 `build_script` 返回值（`desktop_media_pages.py:725`），现在按纯台词文本计，界面代码未改。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git status --porcelain`（开工） | 0 | 无输出 |
| `git log -1 --format=%h` | 0 | `755c7e9d` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/fix-s11-e5` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tts ui_edges_autopilot`（改前） | 1 | 107 条中 4 条失败（见上） |
| 同命令（改后） | 0 | 107 条 0 红，`ALL TESTS PASSED` |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 701 tests`，`OK` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 轮次号 `4299` |
| `git diff --numstat` | 0 | `3\t2\t程序/domain/tts_api.py`、`29\t1\t程序/tests/test_tts.py`（结果文件为新增未跟踪，不计入 diff） |

改后定向输出尾部原文：

```
共 107 条用例，45.8 秒；0 个文件有红
最慢 10 路工作单元：
  test_ui_edges_autopilot#3    42.9 秒 / 13 条
  test_ui_edges_autopilot#2    41.9 秒 / 16 条
  test_ui_edges_autopilot#1    18.7 秒 / 6 条
  test_tts#4                    1.1 秒 / 15 条
  test_tts#2                    0.5 秒 / 15 条
  test_tts#1                    0.2 秒 / 6 条
  architecture.test_tts_publication_boundary    0.1 秒 / 3 条
  test_tts#3                    0.1 秒 / 15 条
  test_tts#5                    0.1 秒 / 14 条
  test_tts#6                    0.1 秒 / 4 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：3.8 秒

ALL TESTS PASSED
```

架构输出尾部原文：

```
----------------------------------------------------------------------
✅ 架构治理测试：tests/architecture
Ran 701 tests in 299.162s

OK
```

## 未验证项

- 未跑默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe`（卡面禁止运行卡面未列的命令；合并轮出口 CI 会跑）。
- 未真实调用付费 TTS 服务（卡面禁止）；音频「只念台词」以 `build_script` 返回文本为准，`synthesize` 收到的 `input` 即该文本。
- 未建真实 Desktop/Tk 窗口验证听感；UI 层用例（`test_ui_edges_autopilot`）已随定向命令在隐藏桌面跑过且全绿。
- 运行输出中的 `invalid command name "…start_account_renewal"／"…start_update_check"／"…speak"` 为隐藏桌面 Tk after 回调噪音，改前红跑与改后绿跑均出现，与本次改动无关（未核实根因，属既有现象）。

## 待文档同步（DOC-S11 在别的车道改，本卡不动文档）

`程序/docs/stages/S11_配音与字幕.md` 建议同步点：

- REQ-S11-12（约 22 行）：「整段按台词＋设置签名复用已有成品，不重复扣费」——「台词」口径变为只含对白文本（不含「角色名：」前缀）；且本次改动使既有整段成品指纹全部失效一次，下次点击重新付费合成。
- IF-S11-21（约 135 行）：「签名＝台词＋模型＋音色＋端点 sha256，变了才重新合成」——「台词」同上指新口径纯对白文本。
- UX-S11-02（约 197 行）：流程描述 `generate_tts→build_script→script_signature→synthesize` 仍准确；「生成配音（TTS）」产出音频内容从念「角色名：台词」变为只念台词，如需可在验收列补一句。

## 待用户确认的口径

无遗留。卡面口径「整段配音只念台词」、空文本句跳过、句间换行均已按需求设计卡面执行；`build_script` 不再使用 `name` 字段，但 `build_lines` 仍照常解析 name（逐句配音 `line_name` 文件名与音色映射仍需要），未做额外裁剪。

## 卡外发现（只记录）

- `build_script` 的 `assets` 参数在新口径下不影响返回文本（只剩签名兼容），保留参数是为不改公开签名；若后续确认无消费者依赖可再议是否精简，本卡不动。

## 提交

- 轮次号 R4299（`scripts\dev.py claim` 领得）；本文件随 `dev.py commit` 同批提交，证据 `tasks_round/evidence/R4299.json` 由提交工具生成；commit hash 见完成报告。
