# R4301 FIX-S11-E15：直连字幕同一集只留最新一份（修复轮）
<!-- round-evidence: {"commit_base": "755c7e9d", "credential_hits": 0, "evidence_sha256": "d023df64d9b1fd49", "exit": 0, "failed": 0, "passed": 8, "round": 4301, "tests": "run_selftests.py -k audio_direct"} -->

## 三问
- 轮次类型：§3.2 修复轮（卡面 FIX-S11-E15，波次 W2，车道 `codex/fix-s11-e15`，基准 `755c7e9d`；需求设计卡 AUD-US05 E-15，总控代需求设计入队）。
- 测试跑了吗、三个基线过了吗：跑了卡面两条验收。定向 `run_selftests.py -k audio_direct` 改前 1 条红、改后 8 条全绿退出码 0；`smoke_test.py --architecture` 701 条全绿退出码 0。默认冒烟与全量 `--all --safe` 未跑（卡面验收未要求，且禁止运行卡面未写的命令）。
- 欠账少了吗：少了「同一集直连字幕越积越多、subtitles.json 列多份」这条审查欠账（AUD-US05 E-15）；无新增欠账。

## 范围与缺陷
- 开工三查：`git status --porcelain` 无输出、`git log -1 --format=%h` 输出 `755c7e9d`、分支 `codex/fix-s11-e15`。
- 缺陷：`orchestrator/audio_direct_api.py::_publish` 每次成功都写一份带 uuid 后缀的 `字幕/配音_<集号>_<6位>.srt`，从不清理同集旧直连字幕；配音脚本历史版本有 `HISTORY_KEEP=2` 上限走 `recycle_paths`，字幕没有对应逻辑。`domain/audio_import_service.audio_manifests` 按目录全量列 `.srt` 进 `subtitles.json`，同一集多次直连后下游分不清哪份是当前（审查 AUD-US05 E-15，卡面已核实行号以函数名为准）。

## 缺陷复现
新增测试 `tests/test_audio_direct_api.py::AudioDirectTests.test_fix_s11_e15_same_episode_keeps_only_latest_direct_subtitle`：临时目录项目，EP001 连续直连成功 3 次、EP002 成功 1 次（交错在 EP001 两次之间），全部走 `FakeAdapter` 不调用真实模型。断言：字幕目录 EP001 直连字幕只剩 1 份且是最后一次发布的；EP002 仍是 1 份且未被回收；回收站里正好是前两次 EP001 旧字幕；`音频/历史版本/配音脚本_*.md` 不超过 2 份；`subtitles.json` 的 `files` 只有 2 条且含最新 EP001 字幕。

## 改前红（退出码 1，1 条红 / 共 8 条）
命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k audio_direct`（工作目录 `程序`，改产品前）

```text
  test_audio_direct_api          8 条     2.3 秒  ✗ 1
共 8 条用例，3.0 秒；1 个文件有红
```

红因原文（与缺陷一致）：

```text
===== test_fix_s11_e15_same_episode_keeps_only_latest_direct_subtitle (test_audio_direct_api.AudioDirectTests.test_fix_s11_e15_same_episode_keeps_only_latest_direct_subtitle) =====
Traceback (most recent call last):
  File "D:\漫剧制作助手\.agents\worktrees\fix-s11-e15\程序\tests\test_audio_direct_api.py", line 132, in test_fix_s11_e15_same_episode_keeps_only_latest_direct_subtitle
    self.assertEqual(1, len(remaining))
AssertionError: 1 != 3
```

EP001 三次成功后字幕目录里留 3 份 `配音_EP001_*.srt`，即缺陷本体现。其余 7 条既有用例当时全绿。

## 改动内容（文件:行号）
- `orchestrator/audio_direct_api.py:148-151`：`_publish` 在配音脚本历史版本回收之后、`return` 之前新增 4 行——`srt_path.parent.glob('配音_%s_*.srt' % code)` 找同目录同集旧直连字幕，排除刚写的 `srt_path`，非空则 `recycle_paths(batch.project, stale, '直连字幕历史版本超过 1 份')`，与配音脚本历史版本同一做法。文件名规则、`HISTORY_KEEP`、公开签名均未动。
- `tests/test_audio_direct_api.py:52-55`：`run_batch` 帮助函数加可选 `source=None`（默认仍 `self.source`，既有调用点不受影响）。
- `tests/test_audio_direct_api.py:113-147`：新增上述回归测试（临时目录夹具，无 Tk、不触用户项目库与真实模型）。
- 既有断言逐字未动。

## 验证命令与结果
Python 命令工作目录均为 `程序`，逐条单独执行。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k audio_direct`（改前）：退出码 1（1 条红，见上）。
2. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k audio_direct`（改后）：退出码 0，尾部原文：
   ```text
   共 8 条用例，3.0 秒；0 个文件有红
   最慢 1 路工作单元：
     test_audio_direct_api         2.3 秒 / 8 条
   实际跳过 0 条用例：本机没有任何登记位被跳过
   增量台账已刷新：（路径略）
   最近 5 轮自检中位基线：63.0 秒

   ALL TESTS PASSED
   ```
3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（改后）：退出码 0，尾部原文：
   ```text
   ----------------------------------------------------------------------
   Ran 701 tests in 221.279s

   OK
   ✅ 架构治理测试：tests/architecture
   ```
4. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`：退出码 0，输出 `4301`。

改后定向测试在落绿前曾因本测试自身两处写法问题各红一次（断言错把「倒数第二次」当最新份、`subtitles.json` 路径误写成 `音频/output` 而非阶段根 `output`），均为测试代码修正，与产品实现无关；最终态 8 条全绿。

## 待文档同步
`docs/stages/S11_配音与字幕.md` 正由 DOC-S11 在别的车道修改，本卡不改它。需同步的句子：

1. REQ-S11-50（该文件第 36 行）写「合格经 L3 发布器写入 `音频/配音脚本.md` 与 `字幕/配音_<集号>.srt`」；代码实际文件名为 `配音_<集号code>_<6位hex>.srt`（`orchestrator/audio_direct_api.py:137`），建议把 `配音_<集号>.srt` 改为 `配音_<集号>_<6位>.srt`。
2. 同条「已有配音脚本先备份到 `音频/历史版本/` 且只留 2 份」只覆盖配音脚本；本轮起同集直连字幕也只留最新 1 份、旧版进回收站（理由「直连字幕历史版本超过 1 份」），建议补一句对应描述。

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4301: FIX-S11-E15 修复" orchestrator/audio_direct_api.py tests/test_audio_direct_api.py tasks_round/tasks_round_4301_result.md --tests audio_direct`（文件参数按 `程序` 相对路径给出；`--tests` 为 `nargs='*'` 须放在文件参数之后；改了 `.py` 须带 `--tests` 生成 `tasks_round/evidence/R4301.json`）。
- 提交哈希以完成报告与证据回执为准，不在本文件自引用。

## 未验证项 / 未核实
- 全量 `run_selftests.py --all --safe` 与默认冒烟未跑（卡面验收未要求且禁止运行卡面未写的命令）。
- 真实模型直连链路未验证（卡面禁止真实调用付费模型；测试全部用 `FakeAdapter`）。
- 存量项目里已积累的多份旧直连字幕不会被本轮 retroactively 清理——只在下一次同集成功发布时回收；是否需要一次性清理属总控口径，未动。
- 未合入、未 push；合入由合并车道按正式流程处理。

## 卡外发现（只记录不顺手修）
- `音频/历史版本/配音脚本_<时间戳>.md` 的时间戳精度到秒（`time.strftime('%Y%m%d_%H%M%S')`）：同一秒内两次发布会写同名备份，前一份被覆盖而非累积。真实使用中两次发布间隔通常远大于 1 秒，测试里同秒运行即触发；如需精确留档可后续把后缀加长，本轮未动。
- `配音脚本.md` 是全项目单文件、不分集（`_publish` 的 `target` 不含集号）；同一项目先后直连不同集时脚本互相覆盖、历史版本混集。本轮按卡面只处理字幕侧，未动。

## 被拒绝的命令（原文，均未重试，改用文件工具完成同等查看）
- `Get-ChildItem -Name`（列工作树根目录）
- `Get-ChildItem tasks_round -Name -Filter "tasks_round_*_result.md" | Sort-Object ...`（找最近结果文件模板）
