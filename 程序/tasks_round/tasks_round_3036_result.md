# R3036 结果：SKILL 生命周期 T3——远程链接导入（GitHub／.zip 直链）＋台账来源字段
<!-- round-evidence: {"commit_base": "ea5ab39e", "credential_hits": 0, "evidence_sha256": "42c9ac7f3179fe08", "exit": 0, "failed": 0, "passed": 192, "round": 3036, "tests": "run_selftests.py -k skill_remote skill_archive skill_repo skill_panel skill_import skill_user_layer"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T3）。
**测试**：跑了——先红后绿（`skill_remote_service` 缺失整文件报错→实现后全绿；首轮非 GUI 15 条暴露 Content-Length 预检被 `except ValueError` 误吞的真 bug，已修）；`run_selftests -k skill_remote` 67 条全绿；`smoke_test.py --affected` 首跑 463 条中 `test_skills` 2 红，根因是新工作树 4 个 gitlink 子仓未初始化（`剧本锻造`／`编剧技能集` 等为空目录，真实注册表 71≠73），从主检出补齐后 `RegistryTests` 15/15 绿，复跑见下。
**基线**：冒烟 8/8＋门禁复跑结果见下；架构门禁结果见下；全量回归未跑（分支不累计欠账）。
**欠账**：无新增；覆盖率基线已随新模块刷新（模块数见下，`skill_remote_service` 在 9 组定向用例口径下覆盖率如实记录）。

## 本轮做了什么

1. **新模块 `skill_remote_service.py`（L4 服务，无 Tk）**：
   - `parse_source(text)` 只收两种形态：`github.com/<owner>/<repo>`（可带 `#<ref>` 与 `/tree/<ref>/<子目录>`，`.git` 后缀与裸 host 宽容；`#ref` 优先于路径 ref）→ codeload `…/zip/<ref>`（缺省 `HEAD`）；`http(s)://…/*.zip` 直链（path 后缀判定，查询串保留在下载地址）。其余形态（git@、npm、tar.gz、ftp、含账密 URL、不支持的 GitHub 子页）一律 `ImportBlocked` 明确文案。
   - `download(url, dest, *, opener, timeout)`：唯一出站口径 `platform_tools.open_https`；`DRAMA_SUPPRESS_NETWORK` 下默认入口直接按不联网返回（与 `account_client` 同规矩），测试注入 `opener` 不受影响。**边界决策**：二进制 ZIP 不走 `http_client.request_json`（那是 JSON API 口径），本模块是文件下载边界，任务书已注明。护栏：Content-Length 预检＋实读双上限（复用 `PACKAGE_MAX_BYTES`）、HTTP 404/403/超时/网络不通/中断各有文案、半截文件即删、响应必 close。
   - `import_from_url(...)`：下载落 `data/skills/下载缓存/`（用户层内、升级保留、文件名不带阶段编号前缀故不被注册表扫描；文件名＝来源主干＋URL 散列防互覆）→ `skill_archive.import_archive(install_source=…, scope=…)` 同一条解包→候选→预检→确认→换入→试冻结→登记管线。
2. **`skill_archive.import_archive` 扩展**：新增 `install_source`（覆盖台账来源信息）与 `scope`（包内子目录作用域，`..`／越界／非目录均拦）两个关键字参数，本地 ZIP 行为不变。
3. **台账字段（T3 步骤 4）**：`record()` 每行新增 `source_url`／`source_ref`（远程可更新坐标，本地来源空串）与 `version`（已安装入口文件 frontmatter `version`，无则空串）；`_InstallSource` 增同名两字段，`_install_candidate_plans` 透传到 plan；`import_from_repo` 的 url 形态（owner/repo、完整 URL）同样落 `source_url`/`source_ref`，本地目录形态留空。`_read_items` 对旧行缺字段天然容忍（有测试）。
4. **UI**：面板下拉新增「从链接导入」（`MANAGE_ADD_URL`），`add_skill_from_url` 复用 `ask_string` 输入框；ZIP／仓库／链接三条批量入口的成功收尾抽为 `_report_batch` 共用。

## 先红后绿证据

新增 `tests/test_skill_remote_import.py`（18 个测试方法，继承 `PanelTests` 后共 67 条用例）：实现前 `import skill_remote_service` ModuleNotFoundError；实现后 `run_selftests -k skill_remote` 67 条全绿（387 秒，含 GUI 令牌等待）。覆盖：parse 各形态与拒绝类、下载成功/Content-Length 超限/实读超限弃半截/404/超时/自检开关、zip 链接与 GitHub `/tree/` 子目录全链路、台账新字段与旧行兼容、仓库 url 形态台账字段、面板入口接线与端到端（注入 `open_https` 不真联网）。

## 验证记录

- `run_selftests.py -k skill_remote`：67 条全绿（首跑）；回收站重构后复跑 67 条 0 红 `ALL TESTS PASSED`（130.6 秒，GUI 令牌排队后正常取得）。
- `smoke_test.py --affected skill_remote_service skill_archive skill_import_service skill_panel_import skill_panel`：首跑 463 条用例、`test_skills` 2 红——根因非代码：新工作树 4 个 gitlink 子仓（`程序/reference/HoLLMwood`、`00全流程SKILL/AIGC创作全流程`、`01 剧本准备SKILL/剧本锻造`、`编剧技能集`）未初始化为空目录，真实注册表 71≠73；T1 工作树已有同法补齐先例。从主检出复制 4 个目录实体后 `test_skills.RegistryTests` 15/15 绿，git status 不受影响（gitlink 内容不入父仓跟踪）。复跑 **463 条 0 红、9/9 检查全过**（318.9 秒门禁）。
- `smoke_test.py --architecture`：470 条中 3 红 1 错全部处理——①`skill_remote_service` 直接 `unlink` 半截下载：改经 `storage_maintenance.recycle_paths`（`download` 增 `recycle_root`，失败半截进回收站，回收失败 `app_logging.swallowed` 留痕）；②`except Exception: pass`：改 `app_logging.swallowed`；③`维护记录/基准历史.json` 为 gitignore 运行文件、工作树缺失：从主检出补齐（只读基线记录）；④`test_round_number_continuous` 2989≠3037 为堆叠分支固有失败（状态页未含本栈轮次，同 T2 情形，合并轮抬头自愈）。复验 `test_recycle_service`＋`test_silent_exception_ratchet`＋`test_agents_md`＋`test_atomic_write_boundary`＋`test_coverage_baseline` 31 条全绿（`test_agents_md` 单测需 `PYTHONPATH=.;tests`，门禁自身路径下通过）。
- 覆盖率基线：重跑 `scripts/coverage_report.py`（同 9 组定向用例 97 条全绿）刷新 `维护记录/覆盖率基线.json` → 548 模块／71 覆盖（`skill_remote_service` 在该口径下 0% 覆盖，如实记录），`runbook.md` §11 同步 548/477。

## 改动文件

`skill_remote_service.py`（新增）、`skill_archive.py`（`install_source`/`scope`/`_scope_root`）、`skill_import_service.py`（`_InstallSource` 两字段、plan 透传、`record()` 三字段、`import_from_repo` 台账坐标）、`skill_panel.py`（下拉项与分发）、`skill_panel_import.py`（`add_skill_from_url`＋`_report_batch`）、`tests/test_skill_remote_import.py`（新增）、`tests/architecture/_layers.py`（登记 L4）、`tests/architecture/test_atomic_write_boundary.py`（下载缓存登记 `_TEMPORARY_BOUNDARIES`）、`architecture.md`、`维护记录/覆盖率基线.json`、`runbook.md`（若数字变）、`tasks_round/tasks_round_3036_result.md`。

## 未做/移交

- T4 台账消费：`check_updates` 按 `source_url`/`source_ref` 重拉摘要、`local-modified` 判定、删除闭环、UI「检查更新」——本轮只备好字段。
- codeload URL 形态按业界通用端点实现（`…/zip/<ref>`，`HEAD` 取默认分支）；自检环境无法真联网验证，真实可用性以首次联网导入为准，失败会走明确 HTTP 错误文案。
- GitHub URL 仅支持仓库首页与 `/tree/` 子目录；`/blob/`、release 附件等形态不收（任务书「其余 URL 形态先只收 zip」口径）。
