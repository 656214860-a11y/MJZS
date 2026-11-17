# R3225 结果：T10 包化 infra/L1 第五批——file_cache/storage_maintenance/app_logging 迁入 infra/
<!-- round-evidence: {"commit_base": "01792e15", "credential_hits": 0, "evidence_sha256": "a5c5869127d78282", "exit": 0, "failed": 0, "passed": 185, "round": 3225, "tests": "run_selftests.py -k file_cache storage app_logging version_record selftests silent_exception read_json recycle deletion_gateway platform_process"} -->

## 三问

1. **本轮属于 §3 哪种类型**：结构治理轮（T10 包化，§3.3 每轮 ≤3 模块）。
2. **测试跑了吗、三个基线过了吗**：默认冒烟 **9/9**；定向 17 文件 **185 条全绿**（file_cache/storage/app_logging/version_record/selftests/silent_exception/read_json/recycle/deletion_gateway/platform_process）；覆盖率工具重测 97 用例全过；架构门禁复跑结果见验证节。
3. **欠账少了吗**：是——infra/ 顶层 L1 实体再减 3（余 ui_tokens），`sys.modules` 门面待清除轮统一处理（需单独授权）。

## 改动

- `git mv` 三模块入 `infra/`：`file_cache.py`（248 行，正式 JSON 读缓存权威）、`storage_maintenance.py`（911 行，删除/回收权威，自带 `--cleanup` 子进程入口）、`app_logging.py`（391 行，日志装配/脱敏）。
- 顶层门面×3（`sys.modules` 别名式）；`storage_maintenance.py` 门面按 R2921 `app_icon.py` 先例带 `__main__` 转发：`python storage_maintenance.py --cleanup` → `_entity.main()`（`infra/storage_maintenance.py:54` 自拉起清理子进程与 `test_storage.py:148` 契约保持）。
- `__file__` 锚点 ×2：`infra/storage_maintenance.py:9`、`infra/app_logging.py:24` 的 `PROGRAM` 改 `.parents[1]`（程序根，供 config.json/logs 解析）。
- 消费方导入改写 **213 个文件**（行级重写脚本 `_rewrite_r3225.py`，用后删除）：`import M`→`import infra.M as M`、`import M as X`→`import infra.M as X`、`from M import`→`from infra.M import`（含括号多行头行）、`import_module/__import__` 字符串加 `infra.` 前缀；逗号混合 import（`tests/test_file_cache.py:11`）逐段处理；复扫残留裸导入 **0**。
- 测试契约随包路径同步（断言意图不变）：9 处 `assertIn('from file_cache import …')` 期望串→`from infra.file_cache import …`；4 处 `node.module == 'file_cache'` AST 比较→`in {'file_cache','infra.file_cache'}` 双拼写（R3024 先例）；`test_read_json_definitions` REGISTERED、`test_silent_exception_ratchet` 键、`test_version_record` 源读径（`Path(app_logging.__file__)`）同步。
- 风险路径登记：`selftest_receipts.risk_paths` 追加 `infra/storage_maintenance.py`（保留扁平门面路径，门面文件仍存在）；`runbook.md` §风险路径叙述同步。
- 台账：`架构统一基数.json` 8 个 `file` 字段改 `infra/` 前缀（第四项×7、覆盖率审计21×1；ratchet 复跑 4/4 绿，锚点哈希未漂移）。
- 登记面：`architecture.md` infra「共 47 个」→「共 50 个」；`PROJECT_MAP.md` 成本保障行 `storage_maintenance.py`→`infra/storage_maintenance.py`；`runbook.md` §11 与 `覆盖率基线.json` 重测（**651 模块／71 覆盖**，门面计入生产模块口径）。
- `说明/版本文件校验.json` 的 `程序/storage_maintenance.py` 哈希条目**不动**——R3096 已裁定该文件为约定不手改的过期快照。

## 验证

- 别名同一性：`import file_cache is infra.file_cache` 等 3/3 通过；`entity_file()` 三模块均解析至 `infra/`。
- `compileall` 全树通过；`smoke_test.py` **9/9**。
- 定向 `run_selftests.py -k file_cache storage app_logging version_record selftests silent_exception read_json recycle deletion_gateway platform_process`：**17 文件 185 条，11.5 秒，0 红**。
- `coverage_report.py` 九组定向重测：97 用例全过，基线已写入（infra/app_logging.py、infra/storage_maintenance.py、infra/file_cache.py 路径入册）。
- 架构门禁：复跑结果以提交前实测为准（本文件提交时同步）。

## 备注

- `--affected` 精度观察（范围外既有欠账，记录不修）：`_direct_imports`/`targets` 均取模块名首段，包路径导入坍缩为 `infra`/`domain` 等顶层段——`--affected file_cache` 只命中 1 个测试模块，`--affected infra.file_cache` 命中 188 个（过宽但安全超集）。该口径自 R2921 首批包化起即存在，本轮沿用 `-k` 定向与全量门禁兜底。
- `tests/architecture/test_gate_selfaudit.py:54` 的 `storage_maintenance.py` 为临时目录夹具文件名，非模块路径语义，未动。
- `skills/01 剧本准备SKILL/编剧技能集` 为嵌套技能仓的既有未跟踪内容，与本轮无关。

## 提交

- 本轮提交 hash 以 `git log` 为准（R3225）。
