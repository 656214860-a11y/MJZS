# tasks_round_4330_result — FIX-S03-DIRECT-ERROR 初步分镜直连「失败 1 集」无原因无错误码
<!-- round-evidence: {"commit_base": "930a05fc4", "credential_hits": 0, "evidence_sha256": "a626601707b116b0", "exit": 0, "failed": 0, "passed": 13, "round": 4330, "tests": "run_selftests.py -k storyboard_direct_api"} -->

## 三问

- 本轮类型：§3.2 修复轮（先定位根因，只改根因所在模块）。
- 测试跑了吗：跑了。定向 `run_selftests.py -k storyboard_direct_api` 13 条全绿（改前 7 条新用例红）；`smoke_test.py --affected storyboard_direct_api desktop_storyboard_direct` 10/10 项通过、定向 13 条全绿；`smoke_test.py --architecture` 702 条全绿。默认冒烟基线 8/8 未跑（卡面验收未列，未运行）。架构门禁当轮实际 702 条、失败集合为空、与改前比较无新增红（改前未跑全量架构，以本轮实测为准）。全量回归未跑（非 master 提交点）。
- 欠账少了吗：本轮无新增欠账；卡外发现记录在末尾「卡外发现」。

## 缺陷复现方式

初步分镜页选模型池 API 模型（DeepSeek V4.1 Flash 1017）点发送 → 手动路径 `adapter=None` 进 `_Batch.__init__`，`orchestrator/storyboard_direct_api.py` 两处 `from infra.model_pool import PoolAdapter` 抛 `ImportError`（`PoolAdapter` 实住 `infra/model_router.py:500`）；`Job.run` 收进 `results[0]['error']`，`ui/desktop_storyboard_direct.py` 的 `finish()` 只写「成功 N 集，失败 N 集」，状态栏只见「失败 1 集」无原因、无错误码，app.log 无记录。

复现测试：`tests/test_storyboard_direct_api.py` 新增 `StoryboardDirectProductionPathTests` 7 条（不注入 adapter、patch 池记录与 `PoolAdapter.stream`，临时目录、不联网）。

## 改前红（7 条，原文摘录）

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k storyboard_direct_api`（退出码 1；共 13 条，7 红，既有 6 条绿）

```
AssertionError: Lists differ: [] != ['orchestrator/storyboard_direct_api.py:13[125 chars]ter']
  + 'orchestrator/storyboard_direct_api.py:136 from infra.model_pool import PoolAdapter',
  + 'orchestrator/storyboard_direct_api.py:253 from infra.model_pool import PoolAdapter'
    — test_adapter_classes_come_from_model_router

KeyError: 'code'   — test_batch_level_failure_keeps_reason

ImportError: cannot import name 'PoolAdapter' from 'infra.model_pool'
  (orchestrator/storyboard_direct_api.py:253, _Batch.__init__)
    — test_real_path_without_injected_adapter_publishes
    — test_request_failure_carries_code_and_reason
    — test_validation_failure_is_contract_violation

ImportError: cannot import name 'summary_text' from 'ui.desktop_storyboard_direct'
    — test_summary_text_shows_reasons
    — test_summary_text_and_log_leave_no_absolute_path
```

红的原因与卡面缺陷一致：两处导入名字不存在、结果没有 `code` 键、界面没有 `summary_text`。另注意输出尾部有 `[SUSPECT_CONCURRENCY]` 提示（他 PID 持 GUI 令牌）；7 条红均为逻辑失败，非并发误报。

## 改动（文件：行号）

- `orchestrator/storyboard_direct_api.py`
  - 14/16/20 行：新增 `import contract.error_codes as error_codes`、`import infra.business_log as business_log`、模块级 `logger = logging.getLogger(__name__)`（写法照 `orchestrator/stage_publication.py`）。
  - 116–134 行：新增 `_DirectError`（带 `code` 的小异常类）与 `_failure(error, default_code)`：`code` 取异常已登记 `code` 属性否则默认码（`FileNotFoundError` 归 `E-FILE-NOT-FOUND`）；`text = error_codes.user_text(error, fallback=code)`，不返 `[E-` 开头时前补 `describe(code)＋全角冒号`，不显示英文程序异常原文。
  - 162 行、282 行：`from infra.model_pool import PoolAdapter` → `from infra.model_router import PoolAdapter`（根因两行，延迟导入位置不变）。
  - 抛出处标码：48（`E-CONTRACT-VIOLATION`）、184–185/192（截断，`E-CONTRACT-VIOLATION`）、189–190（`from_http_result(result)` 空串回退 `E-NET-CLIENT`）、225–226（`E-FILE-NOT-FOUND`）、239（`E-CONTRACT-VIOLATION`）、246（`E-IO-WRITE`）、290/292–293（准入与暂停，`E-CONFIG-INVALID`）、337（`E-FILE-NOT-FOUND`）。
  - 325–347 行：`run_batch` 每条结果加 `code` 键（成功／停止为 `''`，失败为登记码），逐集 `except` 经 `_failure` 生成文字、`logger.error('初步分镜直连失败 code=%s source=%s', code, 文件名, exc_info=True)`、`report(...)` 用同一句 `[E-…]` 文字；`record()` 统一落 `business_log.log_event('storyboard_direct.episode', stage='storyboard', outcome='ok'/'failed')`。
  - 400–404 行：`Job.run` 整批 `except` 同口径（默认 `E-CONFIG-INVALID`），记日志与业务事件，结果带 `code`。
- `ui/desktop_storyboard_direct.py`
  - 4 行：`from pathlib import Path`。
  - 7–27 行：模块级 `_reason_text`（「文件名：原因」各截 160 字，整批条不写文件名）与 `summary_text(results)`：有成功→「成功 N 集，失败 M 集。」接原因；整批未启动→「初步分镜直连没有启动：原因」；原因超两条只列前两条＋「等 N 条失败，详见通知和 logs\app.log」。
  - 51–54 行：`finish()` 改调 `summary_text`；有失败且 `host.notifier` 存在时 `notifier.error(全部原因, title='初步分镜未完成')`（照 `desktop_async_tasks._async_failed`）；停止分支与 `stage.failed` 不动。
- `tests/test_storyboard_direct_api.py` 149–283 行：新增 `StoryboardDirectProductionPathTests` 7 条（既有 6 条原样未动）。
- `docs/stages/S03_初步分镜.md` 55 行：REQ-S03-53 末尾补失败口径句；映射表 136 行已列 `test_storyboard_direct_api`（核实，未改）。
- `governance/structure.json`：未改（按 N856 修订不新增测试文件）。

## 验收命令与退出码

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k storyboard_direct_api` → 退出码 0

```
共 13 条用例，3.9 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --affected storyboard_direct_api desktop_storyboard_direct` → 退出码 0

```
✅ 门禁 run_selftests.py（定向：storyboard_direct_api、desktop_storyboard_direct）：5 秒 → 0 个文件有红
==================================================
通过：10 项
失败：0 项
==================================================
✅ 冒烟测试通过，可以进入下一轮
```

3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0

```
----------------------------------------------------------------------
Ran 702 tests in 302.809s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证／留给用户

- 真机点击 DeepSeek V4.1 Flash 1017 发送一次（真请求花额度，验收不代发）：预期状态栏给「文件名：[E-…] 原因」、整批未启动时写「没有启动」，原始堆栈在 `logs\app.log`。
- 默认冒烟 `python smoke_test.py`（8 项基线）未单独跑；`--affected` 已含 10 项检查全过。
- `git status` 收尾核对在提交后记录。

## 卡外发现（只记录，未顺手修）

- `run_selftests.py -k` 输出尾部偶现 `[SUSPECT_CONCURRENCY]`（他 PID 持 GUI 令牌）提示；本轮红/绿均为确定性逻辑结果，未受影响。
- `ui/desktop_storyboard_direct.py` 的 `drain()` 每批消息都会 `pet_report('storyboard', text)`；失败集 `[E-…]` 文字现在同句进宠物播报，属预期一致口径。
