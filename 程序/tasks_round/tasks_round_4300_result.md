# R4300 结果：FIX-S11-E7 字幕时间轴——同镜极短句不再重叠，导出路径非法作者时间直接报错
<!-- round-evidence: {"commit_base": "755c7e9d", "credential_hits": 0, "evidence_sha256": "b6c8e1379669adbb", "exit": 0, "failed": 0, "passed": 96, "round": 4300, "tests": "run_selftests.py -k subtitle"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮。任务卡 FIX-S11-E7（波次 W2，执行者 devin），权威规格是需求设计卡面 `.agent-tmp/需求设计-card-FIX-S11-E7.md`（AUD-US05 E-7/E-8；总控代需求设计入队）。车道工作树 `.agents/worktrees/fix-s11-e7`，分支 `codex/fix-s11-e7`，基准 `755c7e9d`。缺陷一（E-7）：台词密的镜头里夹一句极短语气词时，`calibrate_entries` 按句长权重分余量，短句分到的时长小于 `_clamp` 保底的 0.2 秒，`_clamp` 又把它顶回 0.2 秒，结果与前一句重叠，`validate_entries` 只能报一句「字幕时间与上一句重叠」而不是说清缺多少时长。缺陷二（E-8）：分镜里作者标错的时间（负数、结束不大于开始、非数字、非有限值）在导出路径上被 `_clamp` 悄悄改正，不报错也不指出是哪一镜哪一句。
- （二）测试跑了吗、三个基线各是什么结果：定向——跑了。验收命令一 `run_selftests.py -k subtitle`：改产品之前退出码 1（96 条用例，13 条红，原因见「改前红」）；改产品之后退出码 0（96 条用例，0 个文件有红，「ALL TESTS PASSED」）。架构门禁 `smoke_test.py --architecture`：改完全部代码和测试之后整套跑过，「Ran 701 tests in 229.603s」「OK」「✅ 架构治理测试：tests/architecture」，退出码 0。默认冒烟和全量自测——没跑（卡面只要求这两条验收命令）。
- （三）欠账少了吗：少了卡面点名的两条缺陷（E-7 重叠、E-8 静默改正）。新增一条口径说明：镜头内待估算句数 × 0.2 秒大于剩余预算时导出直接报错，这是卡面要求的「放不下时报明确的错」；旧项目里靠静默改正或挤压才能导出的分镜改后会开始报错，属卡面明文的有意契约变更。

## 缺陷复现方式（先红）

先在三个允许的测试文件里写/改用例，产品代码未动时跑 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k subtitle`（工作目录 `程序`），退出码 1：

```
共 96 条用例，1.9 秒；4 个文件有红

### test_subtitle_calibration（6 条红）
test_invalid_author_times_raise_with_shot_and_line (bad={'start': 8, 'end': 6})   AssertionError: ValueError not raised
test_invalid_author_times_raise_with_shot_and_line (bad={'start': -1, 'end': 3})  AssertionError: ValueError not raised
test_invalid_author_times_raise_with_shot_and_line (bad={'start': 'x', 'end': 3}) AssertionError: ValueError not raised
test_invalid_author_times_raise_with_shot_and_line (bad={'start': nan, 'end': 3}) AssertionError: ValueError not raised
test_short_line_keeps_minimum_without_overlap  AssertionError: 4.8 not greater than or equal to 4.95049504850495
test_shot_too_short_for_lines_raises_with_shot_and_count  AssertionError: ValueError not raised

### test_subtitles（3 条红）
test_dense_dialogue_exports_without_overlap  AssertionError: 4.8 not greater than or equal to 4.95049504850495
test_nan_start_rejected      AssertionError: ValueError not raised
test_negative_start_rejected AssertionError: ValueError not raised

### test_subtitles（3 条红）
test_non_numeric_author_time_rejected  AssertionError: ValueError not raised
test_reversed_times_rejected           AssertionError: ValueError not raised
test_shot_too_short_for_lines_raises_clear_error
  ValueError: SH001 字幕时间与上一句重叠：0.125 < 0.2
  AssertionError: "SH001.*4 句.*0\.8 秒" does not match "SH001 字幕时间与上一句重叠：0.125 < 0.2"

### test_subtitle_export_service（1 条红）
test_export_srt_rejects_invalid_author_times  AssertionError: ValueError not raised
```

共 13 条红，全部对应卡面缺陷：4 条「非法作者时间被静默接受」（反向、负数、非数字 `'x'`、`nan`，分布在 calibrate 与 srt_rows 两个入口）、2 条「短句被压出重叠」（`4.8 < 4.9505`，即长句占 4.95 秒、短句被顶到 0.2 秒后起点 4.8 落在长句区间内）、2 条「镜头放不下时不报错」、1 条「放不下时报的是重叠错而不是『至少需要 0.8 秒』」、1 条「导出服务层同样静默放行」、1 条为首轮我测试代码自身的 `AttributeError`（误用了另一个测试类的 `publisher` 辅助方法，已改成 `Mock` 后复跑，上面这份输出是修正后的干净红态）。

## 改了哪些文件

- `domain/subtitle_timing.py`（+52/-16 行左右）：
  - 新增 `_author_times(sid, index, a, b)`（46–57 行）：作者标注的镜内起止逐项校验——非数字（含 bool）报「第 N 句对白的 start/end 不是数字」、非有限值报「不是有限值」、负数报「出现负数」、结束不大于开始报「结束时间不大于开始时间」，均带镜头号与句序号。
  - `_dialogue_rows(shot, strict=False)`（60–87 行）：新增 `strict` 参数；`strict=True` 且 start/end 同时非 None 时走 `_author_times` 校验，只标一半或没标的仍按未标注处理。`timed_entries` 仍调非 strict 版本，行为不变。
  - 新增 `_floor_shares(weights, budget, floor)`（171–191 行）：预算按权重分配、每份保底 `floor` 秒的水位分配；放不下保底返回 None。
  - `_distribute(rows, dur, known, sid="")`（194–230 行）：待估算句改由 `_floor_shares` 分配（先保底 0.2 秒/句再分余量）；放不下时抛 `ValueError("{镜头} 共 N 句对白，估算部分至少需要 X 秒")`。
  - `calibrate_entries`（257、272 行）：`_dialogue_rows(shot, strict=True)`、`_distribute(..., sid)`。
- `tests/test_subtitles.py`：导入加 `calibrate_entries`（9 行）；改写 3 条旧用例、新增 4 条（明细见下节）。
- `tests/test_subtitle_calibration.py`：`CalibrateTests` 新增 3 条（99–119 行）。
- `tests/test_subtitle_export_service.py`：新增 1 条（84–89 行）。
- `tasks_round/tasks_round_4300_result.md` 是本文件；`tasks_round/evidence/R4300.json` 由提交工具生成。

`_clamp` 未改：它仍负责把越出镜头范围的合法时间夹进镜头内（卡面要求保持现状），也不再承担「修复」非法值——非法值在 `_author_times` 阶段就已报错，到不了 `_clamp`。公开函数签名未变（`_dialogue_rows`/`_distribute` 是私有函数）。

## 契约有意变更：改写用例逐条对照（卡面明文授权）

以下 3 条旧用例断言的是「悄悄改正非法时间」，按需求设计卡面改写为「导出路径报错并指出镜头与句子」。改写后三条都走 `srt_rows`（即 `calibrate_entries`+`validate_entries` 的导出路径）；`timed_entries` 的旧行为按卡面保持不变。

1. `test_nan_start_does_not_crash` → `test_nan_start_rejected`
   - 原断言：`timed_entries(ep)` 不抛错，`len(entries)==1` 且 `entries[0][3] <= entries[0][4]`（nan 被当合法时间收下）。
   - 新断言：`srt_rows(ep)` 抛 `ValueError`，匹配 `SH001 第 1 句.*不是有限值`。
2. `test_reversed_times_fixed` → `test_reversed_times_rejected`
   - 原断言：`timed_entries(ep)` 把 start=8/end=6「修」成 `start < end` 且时长 >0.19（`_clamp` 静默改正）。
   - 新断言：`srt_rows(ep)` 抛 `ValueError`，匹配 `SH001 第 1 句.*不大于开始时间`。
3. `test_negative_start_clamped` → `test_negative_start_rejected`
   - 原断言：`timed_entries(ep)` 把 start=-2 夹成 `entries[0][3] == 0.0`。
   - 新断言：`srt_rows(ep)` 抛 `ValueError`，匹配 `SH001 第 1 句.*负数`。

其余既有断言逐字未动；`test_explicit_end_beyond_shot_clamped`（timed_entries 越界夹取）与新增的 `test_explicit_out_of_range_still_clamped_on_export`（srt_rows 越界仍夹成 `00:00:09,800 --> 00:00:10,000`）共同钉住「越界仍夹」这条不变口径。

新增用例（8 条）：`test_non_numeric_author_time_rejected`（start="abc" →「不是数字」）、`test_dense_dialogue_exports_without_overlap`（100 字+1 字、5 秒镜：不重叠、短句 ≥0.19 秒）、`test_shot_too_short_for_lines_raises_clear_error`（0.5 秒镜 4 句 →「SH001 共 4 句…至少需要 0.8 秒」）、`test_explicit_out_of_range_still_clamped_on_export`（越界仍夹）、`test_short_line_keeps_minimum_without_overlap`（calibrate_entries 侧同断言）、`test_shot_too_short_for_lines_raises_with_shot_and_count`、`test_invalid_author_times_raise_with_shot_and_line`（反向/负数/非数字/nan 四个子用例）、`test_export_srt_rejects_invalid_author_times`（export_srt 入口同样报错）。

## 改后命令输出尾部原文

验收命令一 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k subtitle`（改产品之后，退出码 0）：

```
共 96 条用例，1.9 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json

ALL TESTS PASSED
```

验收命令二 `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：

```
----------------------------------------------------------------------
Ran 701 tests in 229.603s

✅ 架构治理测试：tests/architecture
OK
```

条数核对：改前（仅测试改动、产品未改）96 条用例 13 红；改后同一命令 96 条用例 0 红——96 = 改前 88 条既有 + 新增/改写后净增 8 条（test_subtitles 净 +4：改写 3 条不计新增、净新增 4 条；test_subtitle_calibration +3；test_subtitle_export_service +1；改写的 3 条与原 3 条一一对应）。

## 命令与退出码

都在车道 `程序` 目录下跑，解释器 `..\..\..\..\运行环境\Python\python.exe -B`。

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `run_selftests.py -k subtitle`（改产品前） | 1 | 96 条用例，13 红（见「改前红」） |
| `run_selftests.py -k subtitle`（改产品后） | 0 | 96 条用例，0 红，ALL TESTS PASSED |
| `smoke_test.py --architecture` | 0 | Ran 701 tests，OK |
| `scripts\dev.py claim` | 0 | 轮次 4300 |

## 待文档同步

`程序/docs/stages/S11_配音与字幕.md` 正由文档卡 DOC-S11 在别的车道修改，本卡未动它。合入后需同步的句子（供文档卡参考）：

- DES-S11-20 现写「`_distribute` 先扣已知真实时长，剩余按 `line_weight`（可见字符数）分配」——应补「待估算句每句保底 0.2 秒（`DEFAULT_LINE_SECONDS`），镜头放不下保底时报 `ValueError` 指明镜头号、句数与所需最短时长」。
- 需补一条导出契约：「作者同时标注 start/end 的句子，负数、结束不大于开始、非数字、非有限值在 `calibrate_entries`（导出路径）直接 `ValueError` 并指出镜头与句序号；越出镜头范围的合法时间仍由 `_clamp` 夹入镜头内；`timed_entries`（配音分句估算）行为不变」。
- REQ-S11-21/22 相关描述可在文档卡里一并核对。

## 待用户确认的口径

- 报错「共 N 句对白」的 N 取镜头内总句数（含已有真实音频时长的句）；「至少需要 X 秒」只按待估算句数 × 0.2 秒算。纯估算场景两者相等；混合音频场景若触发，措辞以「估算部分」限定。
- 只标一半时间（如只有 start 没有 end）的句子仍按未标注处理，与旧口径一致；整镜混合标注仍走既有的「请统一后再导出字幕」报错。
- `timed_entries`（配音分句/提示词侧的镜内等分）对非法作者时间仍是旧的静默夹取行为——卡面第 3 条明确「保持它的行为不变，除非它就是重叠的来源」；重叠来源是 `calibrate_entries` 的按权重分配，已由红测试定位并修复，故未动 `timed_entries`。
- bool 型的 start/end 在严格路径按「不是数字」报错（`True`/`False` 不放行）；非严格路径维持旧的 `isinstance(int)` 口径不变。

## 未覆盖项与卡外发现

- 未跑全量自测、默认冒烟（卡面只要求两条验收命令）；未在真实界面上点过导出——错误从 domain 抛 `ValueError`，经 `subtitle_export_service._calibrated`（domain/subtitle_export_service.py:37-41，不捕获）原样上抛，由既有调用链呈现，界面文件未动。
- `test_golden_outputs.py` 不在 `-k subtitle` 范围内、未实跑；按代码推演其输入不受影响：SUBTITLE_EPISODE 全部未标注对白，估算份额均大于 0.2 秒保底（`_floor_shares` 与旧按比例分配结果一致），音频路径三句全部有真实时长、不进 `_floor_shares`，黄金文件预期不变——未实测，合入前全量若红需按 GOLDEN_UPDATE 流程处理。
- `tests/test_audio_manifest_scope.py`（不在 `-k subtitle`）其 EPISODE 作者时间全部合法（0→2.5、2.5→3.75），推演不受影响，未实跑。
- 卡外发现（只记录）：`pending_calibration`（domain/subtitle_export_service.py:31）无产品调用方，仅测试引用；`DEFAULT_LINE_SECONDS = 0.2`（subtitle_timing.py:142）改动前已定义，本次起才被 `_distribute` 引用；`timed_entries` 对非法作者时间的静默夹取仍在（见上节口径）。
- 被拒绝的命令：`Get-ChildItem scripts`、`Get-ChildItem tasks_round -Filter ...`、`git show HEAD:程序/tests/test_subtitles.py` 各一次（均为查看格式/原断言的只读命令，改用文件工具完成同等核实，未影响验收）。

## 提交

用 `scripts\dev.py commit` 提交，只提交本轮允许清单内的文件。提交号不写在本文件里，以 git log 为准。
