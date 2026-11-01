# R1778：审计健壮性整改——后台线程必回送结果、子进程不遗留、发布清理不误报、错误体脱敏、读取上限（修复轮）

1. 本轮类型：§3.2 修复轮。来源：对源码做的五维只读审计（R1777 前的《应用优化清单》）中，实测确认存在、且改动范围小的一批健壮性问题；每一项先复现或读代码确认，再改，实测不成立的项不动（记录在 `BLOCKED_ISSUES.md`）。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k publication desktop_async_tasks desktop_settings_service model_pool script_text_reader workflow_engines qwen line_endings idea_attach architecture`：532 条，1 个文件有红（见「未通过项」，非本批引入）。
   - 默认冒烟通过。
   - 完整安全全量：本轮改了 `desktop.py`、`model_pool.py`、`agent/publication.py` 等启动与发布路径，合入 master 后由 `scripts/auto_full_safe.py --run` 补跑，未跑前不写通过。

3. project_status.md 欠账少了吗：本轮改源码 +9；全量欠账由合入后补跑清账。

## 改动（每项均有对应测试）

- `agent/publication.py`：事务已提交后的临时目录清理失败只记警告并留待下次访问清理，不再让调用方把已落盘的成果当成发布失败。`tests/test_publication_transaction.py`。
- `desktop_async_tasks.py`：`async_` 的工作线程出异常时，先把结果压回队列，再做诊断，诊断本身出错也不挡结果。`tests/test_desktop_async_tasks.py`。
- `desktop.py`：`discover()` 与阶段模型同步两个后台线程改为捕获 `Exception` 并必送结果，线程不再静默退出让输入框一直处于加载态。
- `desktop_settings_service.py`＋`desktop.py`：新增 `load_desktop_settings`，桌面设置文件被手改或半写时不挡启动，先留 `.corrupt` 副本再回落默认值。副本由 L4 调用方注入 `preserve` 回调写入（L2 不直接写正式路径，守住 `test_unification_ratchet` 第三项）。
- `model_pool.py`：HTTP 错误体先替换请求头里的密钥值，再过 `app_logging.redact`，避免服务端把密钥回显进错误信息。`tests/test_model_pool.py::HttpErrorBodyScrubTests`。
- `workflow_engines.py`、`qwen_adapter.py`：`_run` 被异常（含 Ctrl+C）打断时先结束子进程树再注销登记，否则进程脱离登记表后「强制停止」找不到它。`tests/test_workflow_engines_run.py`。
- `script_text_reader.py`：Word 剧本 `word/document.xml` 解压后设 20MB 上限，超限报明确中文错误，防压缩炸弹。`tests/test_script_text_reader.py`。
- `line_endings.py`：写临时文件后 `fsync`，并在写入、校验、换名任一步失败时都清理本轮临时文件（与 `agent.core.save_text` 对齐）。

## 未通过项

- `architecture.test_round_baselines.test_round_number_continuous`：状态页轮次头是 1776，最新结果文件已是 R1778，要求头＝最新结果＋1。`project_status.md` 只允许 master 提交（规则 41），合入 master 后单独补一次；分支上此项预期为红，非本批引入。

## 提交

- 已在分支 `claude/project-handoff-f6eb50` 提交，commit hash 见 git log `R1778:`。
