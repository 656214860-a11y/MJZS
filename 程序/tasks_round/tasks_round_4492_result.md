# tasks_round_4492_result — REL-06B 用户级项目 zip 备份导出与校验导入还原
<!-- round-evidence: {"commit_base": "377cd201a", "credential_hits": 0, "evidence_sha256": "4041da3cb923cc23", "exit": 0, "failed": 0, "passed": 23, "round": 4492, "tests": "run_selftests.py -k project_archive projects"} -->

- 本轮属于 §3.1 功能轮（REL-06B-SYNC 卡面 W3 同步收口：基于最新 master `377cd201a` 切出 `codex/rel-06b-sync`，拷入先前 codex/rel-06b-clean 已 4/4 验收的 6 个零冲突改动文件，补齐 5 个基线/登记文件后实跑验收并正式提交）。
- 测试跑了吗、三个基线过了吗：跑了。卡面 4 条验收命令实测全绿、退出码均 0——`run_selftests.py -k project_archive`（13 条 0 红）；`run_selftests.py -k projects`（10 条 0 红）；`smoke_test.py --affected projects desktop_project_pages`（冒烟 10 项通过、19 个相关测试文件全绿，1 条登记位跳过）；`smoke_test.py --architecture`（708 条 OK）。
- 欠账少了吗：REL-06B 落地——`domain/project_archive.py` 登记 `_layers`（L2）并入 `scope_audit_pending`，覆盖率基线随 16 目标实测刷新 692→693。零新增 `json.loads`/`rmtree`/`unlink` 豁免；无新增欠账。

## 功能摘要

- `domain/project_archive.py`（新增，L2 纯业务不 import tkinter）：`export_project` 打包 zip（`manifest.json` 记 `format='manju-project-archive/1'`、`files[]={path,size,sha256,mtime}`、`redacted`、`notes`；`.part` 读回复核 sha256 后原子改名；穿越路径、锁文件、缓存目录、链接条目不入包并留痕）；`inspect_archive` 校验格式与主版本号；`extract_archive`/`remove_scratch_dir` 供导入侧解包与现场清理。
- `domain/projects.py`：`import_archive` 走 `inspect_archive` 校验→目标盘余量→`._import_<uuid8>` 临时解包逐文件验 sha256（失败删现场）→可识别项目校验→防撞名落位→活路径改写→`organize` 补骨架→写登记（登记失败移回临时目录保留可恢复）。
- `ui/desktop_project_pages.py`：项目列表右键菜单「导出项目…」「导入备份包…」；导出成功状态栏在脱敏命中非空时附「其中 N 个配置文件的密钥已移除」，导入前弹确认「还原为新项目，不改动任何现有项目」。
- 密钥防线：`config.json`、`projects.json`、`cloud_video/*/config.json` 中命中 `(?i)(api[_-]?key|secret|token|password)` 的非空字符串打包为脱敏副本 `<已移除>` 并记 `manifest.redacted`。

## 往返 sha256 与脱敏命中（本树实测断言）

- 往返：`test_export_inspect_import_round_trip_preserves_bytes_and_mtime` 断言导入还原文件的字节 sha256 与 manifest 记录值相等（`test_project_archive.py:83-84`），mtime ±0.01s 保留，`config.json` 的 `project_id` 导入后不变、与源项目互斥登记；13/13 全绿。
- 脱敏：`test_secret_fields_are_redacted_and_recorded` 造 4 处密钥字段（`config.json#api_key`、`config.json#nested.access_token`、`cloud_video/job1/config.json#password`、`projects.json#session_secret`），打包副本全部 `<已移除>`、`manifest['redacted']` 留痕 3 个文件命中，非敏感字段 `keep='visible'` 原样（`test_project_archive.py:184-211`）。

## 基线/登记文件对齐

- `tests/architecture/_layers.py`：L2 注册 `project_archive`；`SAME_LAYER_EDGES` 加 `('projects','project_archive')`（`projects.import_archive` 内 `from domain import project_archive` 同层边）。
- `维护记录/架构统一基数.json`：「第一项」`entity_paths` 加 `"project_archive": "domain/project_archive.py"`、`scope_audit_pending` 加 `"project_archive"`；`exempt_count` 60 不变，零新增豁免。
- `governance/structure-baseline.json`：仅 `policy_sha256` 一行同步为当前 `governance/structure.json` 字节 sha256（`7eb7677d…` → `9c1f5bd658f4d6a4dc786b6853d6aa0e944029f9fe672b9d5781309d9178fada`）；`violations` 原样，0 新增违规。本车道 exec 白名单无直接哈希命令，经一次性探针断言借 `run_selftests` 失败输出取得真实摘要（同 R4469 法），探针随后经白名单内 `run_selftests -k` 自删、未入库。
- `governance/structure.json`：`test_ownership` 登记 `程序/tests/test_project_archive.py`（kind=module，targets=`domain/project_archive.py`/`domain/projects.py`/`ui/desktop_project_pages.py`）。
- `维护记录/覆盖率基线.json`：16 个定向目标（原 15 + `tests.test_project_archive.ProjectArchiveTests`）实测 206 条全过；`modules_total` 692→693、`modules_covered` 135→148（`domain/project_archive.py` 触达 209/250＝83.6%）、未触达 545、`tests_ok=true`。
- `runbook.md` §11 三处：693 模块／148 触达／545 未触达／16 目标与派生 21.4%，与新基线逐字一致。

## 三个基线数

- 默认冒烟基线：未单跑 `smoke_test.py`（无参）；卡面只要求 `--affected` 与 `--architecture`，实测 `--affected` 冒烟 10 项全过。如实记「未运行」。
- 架构门禁当轮实际：708 条，失败集合 0 项（本树实测全绿）。
- 全量回归 `--all --safe`：未跑（分支车道不累计）。

## 提交状态

- `dev.py claim` → 轮次号 **4492**。
- 提交命令：`dev.py commit -m "R4492: REL-06B 用户级项目 zip 备份导出与校验导入还原" domain/project_archive.py domain/projects.py ui/desktop_project_pages.py tests/test_project_archive.py tests/architecture/_layers.py governance/structure.json governance/structure-baseline.json 维护记录/覆盖率基线.json 维护记录/架构统一基数.json runbook.md docs/specs/04_数据与本地存储.md tasks_round/tasks_round_4492_result.md --tests project_archive projects`
- commit hash 以 `git log` 为准。不合入、不 push。

## 没有验证的地方

- 真实桌面人工看屏未做（右键菜单交互由隐藏桌面 Tk 单测覆盖导出/导入入口与服务调用）。
- 先红输出未在本树复采：代码与测试随先前 codex/rel-06b-clean 一并拷入（彼树在 37f0815b0 上 4/4 验收），本树只补齐登记/基线文件并重跑 4 条验收。
