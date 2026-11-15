# R2864 修复轮结果
<!-- round-evidence: {"commit_base": "a7ecd950", "credential_hits": 0, "evidence_sha256": "fece566dd8209bcf", "exit": 0, "failed": 0, "passed": 111, "round": 2864, "tests": "run_selftests.py -k selftest temp_sandbox stdlib_closure static_names source_text_contracts"} -->

- 轮次类型：修复轮（§3.2，范围限定在自检工具链与开发基础设施；不改业务模块、阶段行为、UI 文案与既有断言）。
- 三问：① 本轮是修复轮；② 默认冒烟 8/8、新增用例 8/8、定向回归 116 条 0 红、架构门禁 470 条 3 个文件红（工作树缺文件 2 个＋状态页轮次头待合并轮同步 1 个，见下）；③ 不新增欠账，只把「自检临时目录不回收」这笔既有欠账清掉。
- 来源：用户报「应用一直弹 Windows『位置不可用』，路径是 `%TEMP%\tmpn6j4hgkn`」后单独授权的一轮「测试临时目录回收」。

## 根因

用例大量用 `tempfile.mkdtemp()` / `TemporaryDirectory()`；Windows 上文件句柄晚一步释放、或用例根本没登记清理，临时目录就删不掉，越积越多。本机实测 `%TEMP%` 下 `tmp*` 目录 **10044 个**（最早 2026-09-19），内容多是本项目夹具（`config.json`、`ui_settings.json`、`06分镜定稿`、`p`、`program`、`project`、`.git`+`tasks_round`…），合计只有约 1 MB —— 危害不是占盘，而是让资源管理器、临时目录扫描和「最近位置」类功能一直对着上万个空目录干活。

单点举证：把 `TEMP` 指到空目录只跑 `run_selftests.py -k app_logging`（13 条用例），跑完留下 **13 个** `tmp*` 目录，一条用例一个；`test_app_logging.setUp` 里 `Path(tempfile.mkdtemp())` 没有配 cleanup。

## 改动

1. `程序/selftest_env.py`：新增自检临时目录沙盒。
   - `TEST_TEMP_PREFIX='drama-test-'`、`TEST_TEMP_ENV='DRAMA_TEST_TEMP'`；
   - `sweep_stale_temp()`：只回收本前缀且超过 24 小时的临时根，跳链接/联接点，逐个计数并上报失败；
   - `install_temp_sandbox()`：子进程把 `tempfile.tempdir` 指到本轮根；
   - `begin_temp_run()`：先回收超期残留，再建本轮根并写环境变量交给子进程；
   - `finish_temp_run()`：整根删除，重试 6 次（去只读位兜底），删不净就留给下一轮按超期回收。
2. `程序/run_selftests.py`：进入 `try` 即 `begin_temp_run()`，`finally` 收尾 `finish_temp_run()`；回收数量打印一行，删不净给警告。
3. `程序/selftest_scheduling.py`：`_run_unit()` 里 `install_temp_sandbox()`，并行池、串行隔离单元、性能单元走的都是这条路径。
4. `程序/tests/test_temp_sandbox.py`：新增 8 条，覆盖前缀整段匹配、超期判定、删除失败要保留、`tempfile` 重定向（`mkdtemp`/`TemporaryDirectory`/`NamedTemporaryFile`）、无根时不动、环境变量交接、重试后成功、仍失败留给下一轮。

## 验证

- 先红（改动前）：`run_selftests.py -k temp_sandbox` → 8 条全红，`AttributeError: module 'selftest_env' has no attribute 'sweep_stale_temp' / 'install_temp_sandbox' / 'TEST_TEMP_ENV' / 'shutil'`。
- 后绿：同命令 8/8 通过（0.6 秒）。
- 端到端：同一条 `-k app_logging`，改前 `%TEMP%` 的 `tmp*` 目录 +13；改后 +0，且收尾后 `drama-test-*` 为 0（第一次抓到一个收尾失败残留，因此把重试从 5 次加到 6 次并补只读位兜底，之后复跑不再残留）。
- 默认冒烟：`smoke_test.py` 8/8。
- 定向回归：`run_selftests.py -k selftest temp_sandbox stdlib_closure static_names source_text_contracts round_baselines` → 116 条，0 文件有红；提交证据用同一组关键词去掉 `round_baselines`（该文件断言状态页轮次头，本分支按 §2.6 不能改状态页）后 111 条，同样 0 红。
- 架构门禁：`run_selftests.py -k architecture` → 470 条，3 个文件红，均与业务改动无关：
  - `architecture.test_agents_md`：缺 `维护记录/基准历史.json`（主工作区有，工作树无）；
  - `architecture.test_skill_reference_injection`：缺 `skills/00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md`（该目录是未检出的 submodule）；
  - `architecture.test_round_baselines`：`2859 != 2865` —— 本分支新增了 2864 结果文件，而 `project_status.md` 轮次头按 §2.6 只能在 master 改，合并轮补登后自然转绿。
  前两处在改前同样红，合入主工作区后应复跑确认。

## 一次性历史清理（手工执行，不在代码里）

判据：`%TEMP%` 下 `tmp*` 目录、最后写入早于 7 天、不含 `png/jpg/jpeg/mp4/mov/zip/exe/dll/msi` 等媒体或安装包，内容为夹具形态。

- 删除空目录 4063 个；删除非空夹具目录 3433 个；合计 **7496 个**，释放约 1 MB。
- 585 个因占用删除失败，原样保留；剩余 2548 个都在 7 天内，交给它们自然变旧或系统清理。
- 没有删除 7 天内的任何目录，也没有删除任何非 `tmp*` 名字的目录。

## 边界与后续

- 只动自检工具链与新增测试文件，未改业务模块、阶段行为、UI 文案、既有断言。
- 未改 `project_status.md`：按 §2.6 仅 master 可提交，合并轮同步轮次头。
- 用户报的「位置不可用」弹窗本身仍未定位（窗口归属进程待抓），与本轮解耦；本轮只把它的可疑诱因之一（上万个残留临时目录）清掉并止住新增。
- 回滚：`git revert` 本提交即可，沙盒前缀目录可随时手工删除。
