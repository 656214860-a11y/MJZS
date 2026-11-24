# R4373 · 每晚审查修复：刷新正文回调 KeyError 与发布门禁升级用例探测落空

<!-- round-evidence: {"commit_base": "171c4cc61", "credential_hits": 0, "evidence_sha256": "a659d6edd1d5fc84", "exit": 0, "failed": 0, "passed": 223, "round": 4373, "tests": "run_selftests.py -k idea_chat dev_entry release"} -->

## 三问

- 本轮类型：§3.2 修复轮（每晚代码审查发现的两处高置信 BUG，各只改根因所在文件）。
- 测试跑了吗：跑了。改前定向红 2 条（原文见下）；改后 `run_selftests.py -k idea_chat dev_entry release` 12 个测试文件 223 条全绿（退出码 0）；`smoke_test.py` 默认 9/9 与 `smoke_test.py --affected desktop_script_pages release_gate`（10 项＋定向自检 14 个测试文件）全绿（退出码 0）。全量回归未跑（分支轮次不累计；`--architecture` 未触发：未动层级、跨层 import 与文件增删）。
- 欠账少了吗：消除 R4358 引入的用户可见 KeyError 与 release_gate 永久不可放行两项缺陷；未新增欠账。审查期其余发现只记录不进本轮，见日报 `工作流任务/simplify审查_2026-11-24.md`。

## 缺陷 1：刷新正文回复落库前 KeyError（R4358 引入）

`ui/desktop_script_pages.py` `refresh_script_workspace` 的 `received` 回调在 reply 非空时执行
`request_usage=request_model['settings']['request_usage']`——`workflow_settings.resolve_for_send`
产出的 settings 字典没有 `request_usage` 键（该键只存在于模型结果 dict 上），必抛 KeyError，
回调在 `idea_chat.append` 之前死亡：重发得到的正文不落库、`show_conversation`/自动保存全部跳过，
表现为「刷新正文后正文丢失」。同语句还把 `settings['skill_injection']`（dict，会被
`idea_transcript.append` 当作合法 `context_budget` 落库）错塞进 `context_budget`，污染用量显示。

根因：R4358（UX-S02-ONE-EDITOR）改写该行时把 `result.get('context_budget')`／
`result.get('request_usage')` 误改为读取请求设置。

修复：恢复按模型结果取值 `context_budget=result.get('context_budget')`、
`request_usage=result.get('request_usage')`；`skill_injection` 仍读请求设置（不变）。

## 缺陷 2：release_gate 升级保留用例探测落空 → releasable 恒假

`scripts/release_gate.py` `build_env` 以 `tests/test_*upgrade*.py` 文件名 glob 探测 REL-04
用例；但升级保留用例以方法形态内嵌在 `tests/test_distribution_build.py`
（`test_upgrade_preserves_*`），文件名不含 upgrade，`upgrade_modules` 恒为空 →
`check_upgrade_preserve` 恒 SKIP「REL-04 未落地」→ 阻断项非 PASS → `releasable` 恒假，
发布门禁永远无法放行。

修复：新增 `_upgrade_test_modules(tests_dir)`——文件名口径之外，再按
`def test_\w*upgrade` 用例名扫描 `test_*.py` 内容，`build_env` 改走该函数。

## 改前红（2 条，原文）

`tests/test_dev_entry.py::test_release_gate_detects_upgrade_cases_inside_other_test_files`：

```
AttributeError: module 'scripts.release_gate' has no attribute '_upgrade_test_modules'
```

`tests/test_idea_chat.py::SendMessageTests.test_refresh_retry_records_usage_fields_from_result`：

```
File ".../ui/desktop_idea_chat.py", line 620, in receive
    if current():received(result)
File ".../ui/desktop_script_pages.py", line 303, in received
    request_usage=request_model['settings']['request_usage'],
KeyError: 'request_usage'
```

## 改动（文件:行号）

- `程序/ui/desktop_script_pages.py:301-303`：`context_budget`／`request_usage` 恢复按结果取值。
- `程序/scripts/release_gate.py:306-320`：新增 `UPGRADE_TEST_RE` 与 `_upgrade_test_modules`。
- `程序/scripts/release_gate.py:341`：`env['upgrade_modules'] = _upgrade_test_modules(program / 'tests')`。
- `程序/tests/test_dev_entry.py`：新增升级用例内嵌探测回归一条。
- `程序/tests/test_idea_chat.py`：新增刷新重发用量字段回归一条（含 work 执行释放阶段槽位，防占用泄漏）。

## 验收命令与退出码

1. `run_selftests.py -k idea_chat dev_entry release` → 退出码 0（12 个测试文件 223 条，0 红）
2. `smoke_test.py` → 通过 9 项，失败 0
3. `smoke_test.py --affected desktop_script_pages release_gate` → 通过 10 项，定向自检 14 个测试文件 0 红

## 未运行

- `run_selftests.py --all --safe` 全量：分支轮次不累计，留待合入评估。
- `smoke_test.py --architecture`：本轮未动层级、跨层 import 与文件增删，未触发。

## 回滚

`git revert` 本轮提交。
