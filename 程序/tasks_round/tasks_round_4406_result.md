# R4406 FIX-S11-LOW-COPY-LEN：缺 FFprobe 提示语压进弹窗字数上限（修复轮）
<!-- round-evidence: {"commit_base": "1b639a193", "credential_hits": 0, "evidence_sha256": "3ad4ae18d6db10bd", "exit": 0, "failed": 0, "passed": 55, "round": 4406, "tests": "run_selftests.py -k copy_rules stage_completion_service"} -->

## 来源

任务卡 FIX-S11-LOW-COPY-LEN（波次 W2），车道 `codex/fix-s11-low`，基准 `1b639a193`。出口 CI 静态门禁仅 1 处失败：`test_copy_rules.PopupCopyTests.test_no_popup_goes_over_the_limit` 报 `orchestrator/stage_completion_service.py:105`（1 行 65 字）超过 45 字上限。

## 轮次类型／三套基线／债务

修复轮（§3.2）：文案超长是 R4391（E-12）为补配置入口引导把提示语写长所致，属同一字符串的最小压缩，不改行为。测试已跑：定向 55/55 绿（改前 1 红即本缺陷），架构门禁 708/708 绿。默认冒烟与全量未跑（卡面验收只列两条命令，未运行项如实标注）。无新增债务。

## 缺陷复现与改前红（原文）

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k copy_rules stage_completion_service`，改前退出码 1，共 55 条用例、1 个文件有红：

```
test_no_popup_goes_over_the_limit (test_copy_rules.PopupCopyTests.test_no_popup_goes_over_the_limit)
AssertionError: Lists differ: ['orchestrator/stage_completion_service.py:105（1 行 65 字）请先配置 FFprobe，再校验媒体成果；在项目 config.json 填写「ffprobe」路径，「设置 → 开发信息 → 环境自检」可核对'] != []
这些弹窗太长，压到 3 行／45 字以内
```

`test_copy_rules.py:189-191` 的 `fixed_chars` 统计拼接后整条文案的非空白字符数（隐式拼接在 AST 里是一个 Constant，故报在 105 行），阈值 `POPUP_CHARS = 45`（:36）。

## 改动

- `程序/orchestrator/stage_completion_service.py:105`：`ValueError` 文案由 3 行隐式拼接（65 字）压成 1 行「请先配置 FFprobe，再校验媒体成果；在 config.json 设路径，见环境自检」（非空白 41 字 ≤45）。保留断言关键词「请先配置 FFprobe」「config.json」「环境自检」（`tests/test_stage_completion_service.py:579-581`），并保留原前半句「请先配置 FFprobe，再校验媒体成果」与 `docs/stages/S11_配音与字幕.md:168`、`S12_后期剪辑.md:175`、`S13_质检与交付.md:174` 的引文一致。diff 为 -3/+1。

## 测试契约

无契约变更：未改 `test_copy_rules.py` 阈值，未动 `test_stage_completion_service.py` 任何断言。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git status --porcelain`（开工） | 0 | 无输出 |
| `git log -1 --format=%h` | 0 | `1b639a193` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/fix-s11-low` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k copy_rules stage_completion_service`（改前） | 1 | 55 条用例，`test_no_popup_goes_over_the_limit` 红（原文见上） |
| 同上（改后） | 0 | 「共 55 条用例，10.0 秒；0 个文件有红」「ALL TESTS PASSED」 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 708 tests` `OK` `✅ 架构治理测试：tests/architecture` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 轮次 4406 |

## 未验证项

- 未跑默认冒烟与全量 `run_selftests.py --all --safe`（卡面未列）。
- 弹窗真实观感未人工查看（本轮只改异常文案字符串，UI 透传链路未动）。

## 卡外发现（只记录不顺手修）

- `docs/stages/S11_配音与字幕.md:168`、`S12_后期剪辑.md:175`、`S13_质检与交付.md:174` 引用的提示语为旧长版后半句「在项目 config.json 填写「ffprobe」路径，「设置 → 开发信息 → 环境自检」可核对」；本卡不改文档，待文档同步轮按新文案「在 config.json 设路径，见环境自检」更新引文。

## 提交

- 车道 `codex/fix-s11-low`，领号 R4406；提交命令与哈希见交付报告。
