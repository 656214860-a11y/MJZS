# R4356 · FIX-S11-E11 音轨清单纳入配音分句子目录
<!-- round-evidence: {"commit_base": "6d0eab990", "credential_hits": 0, "evidence_sha256": "631086224427c38c", "exit": 0, "failed": 0, "passed": 7, "round": 4356, "tests": "run_selftests.py -k audio_import"} -->

## 三问

- 本轮类型：§3.2 修复轮（先定位根因，只改根因所在模块 `domain/audio_import_service.py`）。
- 测试跑了吗：跑了。改前定向红 2 条（原文见下）；改后 `run_selftests.py -k audio_manifest audio_import` 16 条全绿（退出码 0）；`smoke_test.py --architecture` 702 条全绿（退出码 0，失败集合为空）。默认冒烟基线 8/8 与全量回归未跑（卡面验收未列，未运行；车道分支不累计全量轮次）。
- 欠账少了吗：消除 AUD-US05 E-11 缺陷；未新增欠账。卡外发现记录于文末。

## 缺陷复现方式

`domain/audio_import_service.py` 的 `_listing` 只用 `folder.iterdir()` 列音频目录顶层文件（改前 62 行），`audio_manifests` 的 tracks 因此只有顶层条目。逐句配音成品写到 `音频/配音分句/<批次>/`（`ui/desktop_audio_direct.py:61` 指定目录、`domain/tts_api.py:483-496` `publish_line` 逐句落盘），voice.json 永远看不到分句音频——下游按清单取音轨时缺整批对白。

复现：新增 `tests/test_audio_manifest_scope.py::AudioManifestTests` 三条——分句批次入清单带批次名且用途对白、批次内 `历史版本/` 与 `回收站/` 不列、无分句目录时输出逐字不变。改前 2 条红，红因即缺陷本身。

## 改前红（2 条，原文）

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k audio_manifest audio_import`（退出码 1；共 16 条，2 红）

```
### test_audio_manifest_scope（2 条红）

===== test_req_s11_40_sentence_dub_batches_listed_as_dialogue (test_audio_manifest_scope.AudioManifestTests.test_req_s11_40_sentence_dub_batches_listed_as_dialogue) =====
AssertionError: '11配音与字幕/音频/配音分句/批次A/001_SH001_你好_0.0s.mp3' not found in {'11配音与字幕/音频/整轨_x.wav': {'file': '11配音与字幕/音频/整轨_x.wav', 'kind': 'full', 'bytes': 3}}

===== test_req_s11_40_sentence_dub_skips_history_and_recycle_dirs (test_audio_manifest_scope.AudioManifestTests.test_req_s11_40_sentence_dub_skips_history_and_recycle_dirs) =====
AssertionError: '11配音与字幕/音频/配音分句/批次A/001_SH001_你好_0.0s.mp3' not found in []
```

## 改动（文件:行号）

- `程序/domain/audio_import_service.py:58-59`：新增常量 `_SENTENCE_DIR='配音分句'`、`_EXCLUDED_DIRS={'历史版本','回收站'}`。
- `程序/domain/audio_import_service.py:72-78`：新增 `_sentence_walk`，递归遍历批次目录，跳过 `_EXCLUDED_DIRS` 目录，只产出音频后缀文件（沿用 `_SUFFIXES`）。
- `程序/domain/audio_import_service.py:81-90`：新增 `_sentence_listing`，`配音分句/` 第一层目录即批次名（与 `domain/tts_api.py:444` `resume_folder` 的 `*/批次.json` 层级口径一致），返回 `(path, 相对路径, 字节数, 批次名)`。
- `程序/domain/audio_import_service.py:112-114`：`audio_manifests` 在顶层条目后追加分句条目 `{'file','kind':'dialogue','bytes','batch'}`；顶层条目字段与顺序逐字不变（`_listing` 未动）。
- `程序/tests/test_audio_manifest_scope.py:86-145`：新增三条测试；既有断言零改动。

## 验收命令与退出码

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k audio_manifest audio_import` → 退出码 0

```
共 16 条用例，1.4 秒；0 个文件有红
最慢 3 路工作单元：
  test_audio_manifest_scope     0.7 秒 / 9 条
  test_audio_import_service     0.6 秒 / 6 条
  architecture.test_audio_import_boundary    0.1 秒 / 1 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：290.8 秒

ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0

```
----------------------------------------------------------------------
Ran 702 tests in 323.555s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证

- 第 12 阶段如何消费 voice.json 未核实（卡面明示只加清单条目、不改读取方）；分句条目新增 `batch` 字段，读取方对未知字段的容忍度未验证。
- `配音分句/` 根下直接散放、不属任何批次目录的音频按卡面 `配音分句/<批次>/` 口径不入清单；运行态是否存在该形态未核实。
- 默认冒烟 `python smoke_test.py` 未单独跑（卡面未列）。
- `git status` 收尾核对在提交后记录。

## 待文档同步

- `程序/docs/stages/S11_配音与字幕.md` 由 DOC-S11 在他车道修改，本卡不动。建议同步句：voice.json `tracks` 现含 `音频/配音分句/<批次>/` 逐句音频，条目带 `batch`（批次目录名）、`kind` 固定 `dialogue`；`历史版本/` 与 `回收站/` 目录不入清单。

## 卡外发现（只记录，不修）

- `配音分句/` 根目录直属文件（不属任何批次目录）不进清单，与卡面 `配音分句/<批次>/` 边界一致；若运行态存在该形态需另行裁决。

## 回滚

`git revert` 本轮提交。
