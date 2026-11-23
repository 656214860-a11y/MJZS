# R4143 结果：FIX-AUD-SKILL-REMOTE——SKILL 远程导入两处修复
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "e3e4180e9388ff73", "exit": 0, "failed": 0, "passed": 93, "round": 4143, "tests": "run_selftests.py -k skill_remote skill_import"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。审查 AUD-SKILL D3/D4 经验收窗口读码核实的两处缺陷，工作树 `.agents/worktrees/fix-aud-skill-remote`，分支 `codex/fix-aud-skill-remote`，基准 `3383684c`。
- （二）测试跑了吗、三个基线：跑了。`run_selftests.py -k skill_remote skill_import` 改前 93 条用例 5 红（红因即卡面两处缺陷），改后同一命令 93 条 0 红「ALL TESTS PASSED」；`smoke_test.py --architecture` 退出码 0，700 条全绿。默认冒烟未单独跑；全量自测未跑。
- （三）欠账少了吗：少了——还清远程链接导入的两处缺陷。无新增欠账，未动门禁阈值、基线与登记表。

## 缺陷与复现方式

先在 `tests/test_skill_remote_import.py` 写测试／改断言到新契约，未改产品时代码下跑 `run_selftests.py -k skill_remote skill_import`，共 93 条用例、5 红，红因与卡面一致：

1. **github.com 下 releases/download 形态的 *.zip 直链被 `_github()` 拒**（卡面缺陷 1）：新增 `test_github_release_asset_zip_is_archive_link`（:114）、`test_github_release_asset_query_stays_out_of_source_url`（:126）、`test_github_release_asset_end_to_end`（:259）。三条均在 `parse_source` → `_github` 抛 `ImportBlocked: GitHub 链接只支持仓库首页或 /tree/<ref>/<子目录> 形式`（改前 `ui/skill_remote_service.py:72`）。
2. **带查询串的签名 .zip 直链把完整查询串写进台账 `source_url`**（卡面缺陷 2）：`test_zip_link_keeps_query_in_download_but_not_label`（:102，`source_url` 断言由「含 sig=abc123」改为「等于去查询串 URL」，契约有意变更见 §2.4）与 `test_zip_link_end_to_end_with_ledger_fields`（:213，台账行 `source_url` 期望去掉 `?sig=1`）红——实际值仍带完整查询串。

改前红的条数与原因原文（摘自运行输出）：

```
共 93 条用例，8.5 秒；2 个文件有红

===== test_zip_link_end_to_end_with_ledger_fields =====
AssertionError: 'https://cdn.example.com/packs/remote.zip?sig=1' != 'https://cdn.example.com/packs/remote.zip'
 : 台账 source_url 去掉查询串

===== test_github_release_asset_end_to_end =====
ui.skill_install_recovery.ImportBlocked: GitHub 链接只支持仓库首页或 /tree/<ref>/<子目录> 形式
  （抛于 ui/skill_remote_service.py:72 _github，经 parse_source:141、import_from_url:261）

===== test_zip_link_keeps_query_in_download_but_not_label =====
AssertionError: 'https://cdn.example.com/packs/my-skill.zip?sig=abc123' != 'https://cdn.example.com/packs/my-skill.zip'
 : 台账 source_url 不带查询串（签名参数可能夹带令牌）

===== test_github_release_asset_query_stays_out_of_source_url =====
ui.skill_install_recovery.ImportBlocked: GitHub 链接只支持仓库首页或 /tree/<ref>/<子目录> 形式

===== test_github_release_asset_zip_is_archive_link =====
ui.skill_install_recovery.ImportBlocked: GitHub 链接只支持仓库首页或 /tree/<ref>/<子目录> 形式
```

## 改了哪些文件

- `ui/skill_remote_service.py`：
  - 模块 docstring（:9-12）：补 release asset 按直链处理、台账 `source_url` 不含查询串的口径。
  - 新增 `_github_release_asset(path)`（:102-108）：识别 `/<owner>/<repo>/releases/download/<tag>/<asset>.zip` 形态（路径须以 `.zip` 结尾、分段第 3、4 段为 releases/download）。
  - `parse_source`（:154-157）：github.com 主机下命中 release asset 形态时分流 `_archive_link`，其余仍走 `_github`；非 GitHub 主机的 `.zip` 判定不变。
  - `_archive_link`（:111-127）：`source_url` 改用不含查询串的 `urlunsplit`（:124-125）；下载地址 `url`、缓存名散列（仍按含查询串完整 URL 计算）与 `label` 口径不变。
- `tests/test_skill_remote_import.py`：上述 5 条新断言／新用例；`test_rejected_forms` 增一条边界 `https://github.com/acme/tools/archive/refs/heads/main.zip`（非 release 形态的 github .zip 仍拒，防过宽放行）。
- `tasks_round/tasks_round_4143_result.md`：本文件。

行为变化只限缺陷本身：GitHub 仓库链接（含 `#ref`、`/tree/` 子目录）、非 release 形态的 github.com 路径、非 .zip 直链的拒绝口径均逐字未变；`probe_row`／重新导入消费 `source_url` 的路径不变（旧台账行带查询串的 `source_url` 仍可解析、仍能下载）。

## 命令与结果

以下命令都在车道 `程序` 目录下跑，解释器 `..\..\..\..\运行环境\Python\python.exe -B`（主工作区解释器）。

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git -c core.quotepath=false status --porcelain`（开工） | 0 | 无输出 |
| `git log -1 --format=%h` / `git rev-parse --abbrev-ref HEAD` | 0 | `3383684c` / `codex/fix-aud-skill-remote` |
| `run_selftests.py -k skill_remote skill_import`（改前） | 1 | 93 条用例，5 红（上文原文） |
| `run_selftests.py -k skill_remote skill_import`（改后） | 0 | 93 条用例 0 红，尾部原文见下 |
| `smoke_test.py --architecture` | 0 | 700 条全绿，尾部原文见下 |
| `scripts\dev.py claim` | 0 | 轮次 4143 |
| `scripts\dev.py commit -m "R4143: FIX-AUD-SKILL-REMOTE 修复" --tests skill_remote skill_import <文件>` | 见下方提交记录 | |

改后定向命令输出尾部原文：

```
共 93 条用例，7.7 秒；0 个文件有红
最慢 7 路工作单元：
  test_skill_remote_import#2    4.8 秒 / 16 条
  test_skill_remote_import#4    3.8 秒 / 16 条
  test_skill_remote_import#3    3.6 秒 / 16 条
  test_skill_remote_import#5    1.7 秒 / 13 条
  test_skill_import_validation#2    1.3 秒 / 12 条
  test_skill_remote_import#1    0.9 秒 / 11 条
  test_skill_import_validation#1    0.5 秒 / 9 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：2.0 秒

ALL TESTS PASSED
```

架构门禁输出尾部原文：

```
----------------------------------------------------------------------
Ran 700 tests in 260.365s

✅ 架构治理测试：tests/architecture
OK
```

## 未覆盖项

- 未跑默认冒烟、未跑全量自测（卡面只要求定向命令与 `--architecture`）。
- 未做真实网络验证：全部用例注入 `opener`；GitHub release asset 真实 302 跳转到对象存储的行为未实测（`platform_tools.open_https` 按既有直链口径处理重定向）。
- `test_skill_update_check.py` 不在本次 `-k` 关键词命中范围（2 个匹配文件为 `test_skill_remote_import`、`test_skill_import_validation`）；`probe_row` 对 archive 行的重下逻辑未改，带查询串旧台账行仍可解析下载，新写入行 `source_url` 无查询串后真实签名链接重下会按无签名 URL 处理（去令牌的既定取舍）。
- 未 push、未 merge、未动主工作树与 master。
