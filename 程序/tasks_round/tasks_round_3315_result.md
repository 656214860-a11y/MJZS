# R3315 结果文件
<!-- round-evidence: {"commit_base": "f69fa690", "credential_hits": 0, "evidence_sha256": "ce1912ca9c93d82b", "exit": 0, "failed": 0, "passed": 56, "round": 3315, "tests": "run_selftests.py -k platform_tools selftest_env merge_queue local_ci tools_lock mutation_sample environment_check"} -->

1. **本轮属于 §3 哪种类型**：§3.2 修复轮——master 全量自检暴露的编码门禁缺陷：cp936 本地化下 `subprocess text=True` 缺省按 GBK 解码，工具/git 的 UTF-8 输出触发 reader 线程 `UnicodeDecodeError`，`stdout/stderr` 变 `None`，导致 `test_lane_merge_queue`/`test_git_hooks`/`test_selftests_gui_token`/`test_storyboard_catalog_scan_count`/`test_stage_prompt_governance` 批量红、合并自动化与本地 CI 输出丢失。
2. **测试跑了吗、三个基线过了吗**：跑了。先红：上述 5 个测试文件在全量中红（merge_queue `_lane_name` 解码崩溃、gui_token 队列读取 None 等）；改后同批 67 条全绿、`platform_tools` 34 条全绿、受影响批（merge_queue/local_ci/tools_lock/mutation_sample/environment_check/agent/skill_import/http_client）101 条全绿；默认冒烟 10/10、`--affected platform_tools selftest_env merge_queue` 冒烟 10/10；架构门禁未单独跑（合入轮出口 CI 含）；全量凭据以 `full-safe-receipts.json` 为准，后台补跑中。
3. **欠账少了吗**：少了——消除全部已实测的 GBK 解码崩溃路径；新欠账：skills/ 内 vendored 脚本仍有未钉编码的 `text=True`（技能包内部工具，非交付主路径），登记不修。

## 改动

- `selftest_env.py`：新增 `os.environ.setdefault("PYTHONUTF8", "1")`——自检派生的全部子进程（工作单元、隐藏桌面、用例自起 git/python）一律 UTF-8 模式，从根上消除测试侧 GBK 解码崩溃。
- `contract/platform_tools.py` `run_process`：`text=True`/`universal_newlines` 且调用方未显式给 `encoding`/`errors` 时，缺省注入 `encoding='utf-8', errors='replace'`——覆盖 `agent/core.py`、`ui/skill_import_service.py`、`environment_check.py` 等全部走该入口的调用方。
- `scripts/merge_queue.py`：3 处 `text=True` 补 `encoding='utf-8', errors='replace'`（common_dir/toplevel/round_claim show）。
- `scripts/local_ci.py`：benchmark_trend 调用补编码钉。
- `scripts/tools_lock.py`：2 处 git rev-parse 补编码钉（第 3 处此前已钉）。
- `scripts/mutation_sample.py`：变异采样子进程补编码钉。
- `tests/test_platform_tools.py`：新增 `RunProcessEncodingTests` 3 条——行为断言：UTF-8 子进程输出按 UTF-8 解码正确、显式 `encoding='gbk'` 不被覆盖、二进制模式不注入编码。

## 验证证据

- 先红：全量批中 `test_lane_merge_queue`/`test_git_hooks`/`test_selftests_gui_token`/`test_storyboard_catalog_scan_count`/`test_stage_prompt_governance` 红（reader 线程 UnicodeDecodeError → stdout=None）。
- 改后：`-k lane_merge_queue git_hooks selftests_gui_token storyboard_catalog_scan_count stage_prompt_governance` → 67 条 0 红；`-k platform_tools` → 34 条 0 红；`-k merge_queue local_ci tools_lock mutation_sample environment_check agent_core skill_import platform_tools http_client` → 101 条 0 红。
- 冒烟：默认 10/10；`--affected platform_tools selftest_env merge_queue` 10/10。
- 三个基线：默认冒烟 10/10 ✅；架构门禁随合入轮出口 CI；全量凭据以 `full-safe-receipts.json` 为准。

## 备注

- 本轮源于 R3309 备注预告的「subprocess cp936 解码崩溃」批量暴露；`skills/` vendored 脚本同类隐患登记为欠账（非本轮范围、不影响交付主路径）。
- `PYTHONUTF8` 用 `setdefault`：用户显式设 `PYTHONUTF8=0` 时尊重其选择。
