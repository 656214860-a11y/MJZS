# R4411 结果：FIX-S04-SKETCH-COPY 压缩 Comfy 客户端异常文案过 copy_rules
<!-- round-evidence: {"commit_base": "a82bda591", "credential_hits": 0, "evidence_sha256": "d72a625ed2be637a", "exit": 0, "failed": 0, "passed": 36, "round": 4411, "tests": "run_selftests.py -k animatic_sketch_backends copy_rules"} -->

- 轮次类型（§3）：3.2 修复轮（出口静态门禁 `test_copy_rules` 唯一红灯的文案压缩）。
- 测试跑了吗：跑了，定向 `run_selftests.py -k animatic_sketch_backends copy_rules` 改前红 1 条、改后 36 条全绿（退出码 0）。三个基线——默认冒烟与全量未跑（任务卡明确禁止 `smoke_test.py --architecture`，合入出口 CI 重跑全套）；本轮仅 1 行文案，无逻辑变更。
- 欠账少了吗：消除出口 CI [CI] 2/3 静态门禁唯一失败项；零新增欠账。

## 缺陷复现方式（先红）

`tests/test_copy_rules.py` 的 `PopupCopyTests.test_no_popup_goes_over_the_limit`（POPUP_LINES=3／POPUP_CHARS=45，test_copy_rules.py:35-36）扫描全部弹窗文案，`domain/animatic_sketch_backends.py:50` 的 `ValueError` 单行 53 字超限。

改前跑 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_sketch_backends copy_rules`（目录 程序，退出码 1）：

```
### test_copy_rules（1 条红）

===== test_no_popup_goes_over_the_limit (test_copy_rules.PopupCopyTests.test_no_popup_goes_over_the_limit) =====
AssertionError: Lists differ: ['domain/animatic_sketch_backends.py:50（1 行 53 字）缺少本地 ComfyUI 客户端：请由编排层注入 client 参数或 settings 的 comfy_client 键'] != []
```

## 改动位置（文件:行号）

- `domain/animatic_sketch_backends.py:50`：`ValueError` 文案由 53 字压为 40 字——
  旧：`缺少本地 ComfyUI 客户端：请由编排层注入 client 参数或 settings 的 comfy_client 键`
  新：`缺少本地 ComfyUI 客户端，请注入 client 参数或 comfy_client 设置`
  两条注入路径（`client` 参数／`settings['comfy_client']`）语义保留；逻辑零改动。
  全文件其余 `ValueError` 文案逐条核对均 ≤45 字（最长为 L92 替换图格式提示约 28 字），无第二处超限。
- `tests/test_animatic_sketch_backends.py` 未改：该文件仅以 `assertRaisesRegex(ValueError, 'ComfyUI 客户端')` 断言子串（:208），新文案保留该子串，断言原样通过。

## 验收命令输出尾部（原文）

命令 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_sketch_backends copy_rules`（目录 程序，退出码 0）：

```
跑 2 个测试文件 / 2 路工作单元（8 路并行）
  test_animatic_sketch_backends    18 条     0.1 秒
  test_copy_rules               18 条     3.8 秒

共 36 条用例，6.4 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过

ALL TESTS PASSED
```

## 没有验证的地方

- 未跑默认冒烟 `smoke_test.py` 与 `--architecture` 全量门禁（任务卡禁止项；合入出口 CI 会重跑）。
- 异常文案的真实用户可见路径未做 UI 验证（本模块为 L2，错误经 `safe()` 弹窗由上层呈现，文案规则已由静态门禁覆盖）。

## 卡外发现（只记录，不顺手修）

- 无。
