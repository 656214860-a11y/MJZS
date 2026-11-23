# R4249 REL-01：随包工具齐全检查 tools_lock.py --verify-bundle（修复轮）
<!-- round-evidence: {"commit_base": "cb33bcfe", "credential_hits": 0, "evidence_sha256": "2191527a742f3bd5", "exit": 0, "failed": 0, "passed": 17, "round": 4249, "tests": "run_selftests.py -k tools_lock ffmpeg_runtime"} -->

## 三问
- 轮次类型：§3.2 修复轮（卡面 REL-01，发布就绪调研缺口：没有独立的「随包工具齐全」命令，也没有测试固定 ffmpeg/LICENSE）。
- 测试跑了吗、三个基线过了吗：跑了卡面指定验收。定向 `run_selftests.py -k tools_lock ffmpeg_runtime` 改前 7 条红、改后 17 条全绿退出码 0；`smoke_test.py --architecture` 首跑 1 红（新增 `json.loads` 调用点触发债务棘轮），调整后 700 条全绿退出码 0。默认冒烟与全量 `--all --safe` 未跑（卡面验收未要求）。
- 欠账少了吗：补齐「随包齐全」可自动化检查的欠账；`json.loads` 裸读债务零新增（共用 `main` 既有唯一调用点）；无新增欠账。

## 范围与基线
- 基准版本：`cb33bcfebd3d3936f400b12fdd0af5d8d6c74533`（开工三查：`git status --porcelain` 无输出、`git log -1 --format=%h` 输出 `cb33bcfe`、分支 `codex/rel-01`）。
- 任务：REL-01 / 波次 W2 / 共享资源 `release-docs`。
- 缺陷：`scripts/tools_lock.py` 只有 `--check`（锁内条目核对）与 `--update`，没有「随包齐全」检查：不验证 ffmpeg/ffprobe 实际在位且 sha256 与锁一致，也不验证 `运行环境/ffmpeg/LICENSE` 存在；缺失时没有可操作报错。
- 设计取舍：卡面允许「并入 --check 或新增 --verify-bundle」。取新增 `--verify-bundle`：`dev_lint.py:20` 每次 lint 都跑 `--check`，真实包内许可文件名在主工作区（未核实，见下），并入 `--check` 有把 lint 门禁打红的风险；新开关不改变任何既有行为。
- 改动文件：`scripts/tools_lock.py`、`tests/test_tools_lock.py`、`docs/process/发布检查单.md`、本结果文件；`tasks_round/evidence/R4249.json` 由 `scripts\dev.py commit` 生成。

## 缺陷复现
`tools_lock.main(['--verify-bundle'])` 在未改产品前由 argparse 以 `SystemExit: 2` 拒绝（无此开关），`tools_lock.bundle_problems` 不存在（`AttributeError`）。新测试 `tests/test_tools_lock.py` 的 `BundleVerifyTests` 用临时目录造四种情形：齐全、缺 exe、sha256 不符、缺 LICENSE，另加 CLI 级退出码/报错断言。

## 改前红（退出码 1，7 条红 / 共 17 条）
命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tools_lock ffmpeg_runtime`（工作目录 `程序`）

```text
  test_ffmpeg_runtime            9 条     0.5 秒
  test_tools_lock                8 条     4.0 秒  ✗ 7
共 17 条用例，4.8 秒；1 个文件有红
```

红因原文（与缺陷一致）：
- `test_complete_bundle_has_no_problems` / `test_missing_executable_reports_item_and_expected_path` / `test_sha256_mismatch_reports_item_and_expected_path` / `test_missing_license_reports_item_and_expected_path`：`AttributeError: module 'scripts.tools_lock' has no attribute 'bundle_problems'`（各 1 条，共 4 条）。
- `test_verify_bundle_complete_exits_zero` / `test_verify_bundle_failure_is_actionable` / `test_verify_bundle_missing_lock_fails_without_creating_it`：`SystemExit: 2`（argparse 不识别 `--verify-bundle`，共 3 条）。

## 改动内容（文件:行号）
- `scripts/tools_lock.py:6`：用法补 `--verify-bundle` 行。
- `scripts/tools_lock.py:86-92`：新增 `BUNDLE_ITEMS`（ffmpeg.exe、ffprobe.exe、`运行环境/ffmpeg/LICENSE`）、`BUNDLE_HASHED`（前两项做 sha256）、`BUNDLE_FIX`（「从备份拷回或重新下载后运行 tools_lock.py --check」，卡面原文）。
- `scripts/tools_lock.py:132-143`：新增 `bundle_problems(locked, resolver=None)`：逐项经 `_resolve`（含工作树→主工作区回落）定位；文件缺失或 sha256 与锁不符时给出缺哪一项与预期路径；只报告，不拷贝、不联网。
- `scripts/tools_lock.py:150`：注册 `--verify-bundle` 开关。
- `scripts/tools_lock.py:152-154`：`--verify-bundle` 且锁文件不存在时退出 1（不自动重建锁，区别于 `--check` 的缺锁即 `--update` 语义）。
- `scripts/tools_lock.py:165-172`：读完锁后分派 `--verify-bundle`：有问题逐条写 stderr「随包缺失：<项与预期路径>；<修复提示>」并退出 1，全过打印「随包工具齐全：3 项」退出 0。`json.loads` 复用 `main` 既有唯一调用点（`tools_lock.py:164`），不新增裸读债务。
- `tests/test_tools_lock.py:2-9`：补 `contextlib/hashlib/io/json/tempfile/Path/patch` 导入；`:31-126` 新增 `BundleVerifyTests` 7 条（4 条情形级 + 3 条 CLI 级：退出码、stderr 含缺失项/预期路径/修复提示、缺锁不建锁）。原有 `ToolsLockTests` 断言逐字未动。
- `docs/process/发布检查单.md:12`：§1 新增第 5 项「随包齐全检查」——发布前跑 `python -B scripts\tools_lock.py --verify-bundle`，任一缺失退出码非 0、阻断发布、只报错不替用户拷贝；原第 5–8 项顺延为 6–9（`:13`、`:16-18`）。

## 验证命令与结果
Python 命令工作目录均为 `程序`，逐条单独执行。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tools_lock ffmpeg_runtime`（改前）：退出码 1（7 条红，见上）。
2. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tools_lock ffmpeg_runtime`（改后）：退出码 0，尾部原文：
   ```text
     test_ffmpeg_runtime            9 条     0.2 秒
     test_tools_lock                8 条     0.5 秒
   共 17 条用例，1.3 秒；0 个文件有红
   ALL TESTS PASSED
   ```
3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（首次）：退出码 1——`test_bare_json_load_debt_is_a_nonincreasing_subset` 报 `第四项 出现未登记新增债务：['scripts/tools_lock.py:main:json.loads:17afbd0aa15e669e:2']`；据此把锁读取收敛为 `main` 单调用点。
4. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（复跑）：退出码 0，尾部原文：
   ```text
   Ran 700 tests in 251.422s
   ✅ 架构治理测试：tests/architecture
   OK
   ```
5. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`：退出码 0，输出 `4249`。

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4249: REL-01 修复" scripts/tools_lock.py tests/test_tools_lock.py docs/process/发布检查单.md tasks_round/tasks_round_4249_result.md --tests tools_lock ffmpeg_runtime`（`commit_retry.stage_inputs` 以 `程序` 为 cwd 跑 `git add`，文件参数按 `程序` 相对路径给出；`--tests` 为 `nargs='*'`，须放在文件参数之后，否则把文件路径吞作关键词——GIT_TRACE 实证 `args.files` 曾因此为空）
- 提交哈希以完成报告与证据回执为准，不在本文件自引用。

## 未验证项 / 未核实
- `tools_lock.py --verify-bundle` 未对真实 `运行环境` 运行（卡面命令清单未包含；锁内 sha256 由 `--check` 既有契约守卫）。
- 真实包内 `运行环境/ffmpeg/` 的许可文件是否名为 `LICENSE`（而非 `LICENSE.txt`）：未核实——主工作区目录列举与工作树 `运行环境` 列举均被权限拒绝。仓库文档（任务书、`docs/specs/03_安装签名与分发.md:58`）与卡面权威规格统一写作 `LICENSE`，故按 `运行环境/ffmpeg/LICENSE` 实现；若实物为 `LICENSE.txt`，该检查会在发布时按设计报「文件缺失」并给出预期路径。
- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面验收未要求）。
- 未合入、未 push；合入由合并车道按正式流程处理。

## 被拒绝的命令（原文，未重试）
- `Get-ChildItem -Name 'D:\漫剧制作助手\运行环境\ffmpeg'`（主工作区目录列举）
- `Get-ChildItem -Name 'D:\漫剧制作助手\运行环境\ffmpeg\bin'`
- `Get-ChildItem -Name '运行环境'`（工作树根）
- `Select-String -Path 'tasks_round\evidence\R3749\manifest_pre_install.json' -Pattern 'ffmpeg[^"]*' -AllMatches | ...`（且与卡面禁管道冲突，弃用）
- `([regex]::Matches((Get-Content -Raw -Encoding UTF8 'tasks_round\evidence\R3749\manifest_pre_install.json'), '运行环境/ffmpeg/[^"\\]{1,80}')).Value`
