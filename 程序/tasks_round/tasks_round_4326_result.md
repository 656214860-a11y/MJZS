# R4326 REL-04 升级安装保留用户数据的自动化测试（功能轮）
<!-- round-evidence: {"commit_base": "493479834", "credential_hits": 0, "evidence_sha256": "0ec67e9bd3c00a62", "exit": 0, "failed": 0, "passed": 22, "round": 4326, "tests": "run_selftests.py -k distribution_build"} -->

## 来源
任务卡 REL-04（W2，车道 `codex/rel-04`，基线 49347983）：规格《docs/specs/03_安装签名与分发.md》§2.3 要求升级「只覆盖程序文件」，保留 `config.json`、`projects.json`、`desktop_settings.json`、`private`、`data` 运行数据、`配置/宠物`、`配置/素材库.json`、用户项目与素材。现状 `test_distribution_build` 只证明「机器状态不进包」，`scripts/acceptance_release_probe.py` 是探针脚本不是 unittest。

## 轮次类型／三套基线／债务
功能轮（补测试＋最小入口）。测试跑了：定向 `run_selftests.py -k distribution_build` 22 条全过（19 原有＋3 新增）；架构门禁 `smoke_test.py --architecture` 702 条全过。默认冒烟基线未跑（卡面验收命令不含默认冒烟，未运行）。无新增债务：首轮提交前架构棘轮曾检出 `check_upgrade` 里一处裸 `json.loads`，已改为 `distribution_build.read_json_file`（与产品同一条读取链），无欠账遗留。

## 缺陷复现与改前红
新增三条 `test_upgrade_preserves_*` 用例调用 `release_snapshot.check_upgrade`（升级后核对入口）。改前 `run_selftests.py -k distribution_build` 共 22 条，3 条红，原因一致：

```
AttributeError: module 'scripts.release_snapshot' has no attribute 'check_upgrade'
```

（test_upgrade_preserves_user_data_byte_for_byte / _replaces_program_files_with_new / _rollback_restores_old_install 各一条；红的原因即卡面缺陷：`release_snapshot.py` 只有 `--snapshot`/`--drill`，缺升级后核对入口。）

## 改动
- `scripts/release_snapshot.py`：新增 `check_upgrade(package, install)`（对照包内 `分发清单.json` 逐文件核对安装目录 sha256，返回 `{'ok','checked','missing','mismatch'}`，`ok=False` 即混合态）；`main()` 增 `--check-upgrade <安装目录> --package <分发副本>`，不一致退出码 1；docstring 同步。不写安装目录外的任何东西，也不触碰包外文件。
- `tests/test_distribution_build.py`：新增 `UPGRADE_DATA_EXCLUDE`、`UPGRADE_USER_FILES`、`UPGRADE_PROJECT_FILES`、`UPGRADE_PROGRAM_V2` 常量与 `upgrade_manifest()`；新增 `_write_payloads`／`_overlay`（zip 覆盖模型，limit 模拟中断）／`_tree`／`_upgrade_fixture` 四个夹具方法；新增三条用例：
  - `test_upgrade_preserves_user_data_byte_for_byte`：临时目录造「旧版安装目录」（旧源构建＋config/projects/desktop_settings/private/data/配置宠物/素材库/项目素材），新副本覆盖后上述文件逐字节不变，且新副本 `分发清单.json` 不含机器状态路径。
  - `test_upgrade_preserves_replaces_program_files_with_new`：程序文件（含随包内置数据 `data/skill_note_terms_zh.json`）被新版逐字节替换，同目录本机数据保留。
  - `test_upgrade_preserves_rollback_restores_old_install`：半量覆盖模拟升级中断 → `check_upgrade` 检出混合态（mismatch 非空）→ 从升级前整份快照恢复后安装目录逐字节等同旧态。
- `docs/process/发布检查单.md` 第 8 步：补 `--check-upgrade` 用法与自动化覆盖位置，注明真实安装目录演练仍属待办。

## 测试
- `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k distribution_build`：退出码 0，`共 22 条用例，2.5 秒；0 个文件有红 … ALL TESTS PASSED`。
- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：退出码 0，`Ran 702 tests in 317.039s … OK ✅ 架构治理测试：tests/architecture`。

## 未验证与遗留
- 只覆盖并排构建与快照渠道（zip 覆盖安装）的文件面；快照与演练未在真实安装目录跑过（检查单原注保持），按卡面「拿不准」列入 REL-12 实机清单。
- 覆盖模型不清理新版已移除的程序文件（残留旧文件不会被检出为失败）；现状并排切换渠道不受影响，记录不修。
- `check_upgrade` 只核对包内清单条目；包自身完整性由 `distribution_build.verify()` 承担（检查单 §1.3、规格 §3.3）。
- 未运行默认冒烟与全量 `--all --safe`（卡面未列入）。

## 回滚
`git revert` 本轮提交。
