# R1371：O44 保留安全机制，补可诊断但不泄露的状态区分

类型：功能轮（§3.1；本项「事实／建议」→ 密钥状态可诊断＋诊断预览显示导出范围与保留期限，未改任何写入／删除路径与付费逻辑）。承接 R1267 清单 O44（O01—O43 已完成）。中央轮次 1371（主树含他人已暂存 WIP，故在干净临时工作树 `o44-claim` 调用 round_claim.py next 领取）。本轮 1371 − last_full_safe_all_round(1370) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径／Tk 控件生命周期／删除语义／层级登记表；改的是 L1 密钥与诊断层），收口仍按流程在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：新增 `tests/test_secret_status_diagnostics.py` 13/13；定向 `-k secret_status_diagnostics diagnostic_capture model_diagnostics model_pool pet_llm writing_api hollmwood_roles pet_settings` 共 269 条、仅 `test_model_pool` 1 条红（`test_desktop_options_are_marked_only_when_the_shared_probe_cannot_find_them`：「未安装」出现在 claude-desktop 标签）——已用路径限定 `git stash push -- <本轮 3 个文件>` 复现：**不加载本改动同样红**，确认是既知主树环境项（本机 claude-desktop 探测与未跟踪 `程序/配置/宠物/配置.json` 不一致），与本改动无关；另 `-k test_api test_recycle` 全绿；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8。
- 欠账：O44 关闭，清单剩 O45—O48；1371 − 1370 = 1 < 5，无五轮欠账；未命中 §5；收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O44）
- 证据：`model_secrets.py:81` DPAPI 解密失败与未配置都返回空；`diagnostic_capture.py:103` 已用白名单和脱敏导出；`model_diagnostics.py:37` 不保存响应正文。
- 建议：区分未配置、当前用户无法解密、文件损坏、鉴权失败；诊断预览显示将导出哪些文件及保留期限。响应正文属于用户作品，与安全诊断分区保存和授权删除。
- 验收：迁移 Windows 用户、损坏密文、服务端回显凭据、异常 URL 参数、用户文稿敏感字段都不泄露；本轮没有发现或读取明文密钥。

## 实现
- `model_secrets.py`（L1）新增 `_BLOB_HEADER`（DPAPI 密文头＝版本号 4B ＋ provider GUID 16B）与五个状态常量 `READY`／`UNCONFIGURED`／`OTHER_USER`／`CORRUPT`／`AUTH_FAILED`＋`_STATE_TEXT`；新增 `looks_like_blob(data)`、`diagnose(name, program, root)`、`verdict(name, program, root, error_class='')`：
  - `diagnose`：名字为空或文件不存在 → `unconfigured`；文件读不出或头不是 DPAPI 头 → `corrupt`；头对得上但当前用户解不开 → `other-user`（换过 Windows 用户或系统密钥变了）；解得开 → `ready`。返回 `{'name','path','state','ok','text'}`，**不含任何密钥字节**。
  - `verdict`：本机没配好时以本机原因为准；本机 `ready` 而调用方已把错误分成 `auth`／`authentication`／`unauthorized`（`pet_agent.classify`／`model_router` 的既有分类）时才报 `auth`（鉴权失败）——把「没配」与「配了但被服务端拒绝」彻底分开。
  - `load()` 契约不变（仍对未配置与解不开都返回空串），新增能力只走新函数，`model_pool`／`pet_llm`／界面不用改。
- `diagnostic_capture.py`（L1）新增 `redact(value)`（对外共用同一套脱敏）、`RETENTION_DAYS`（直接复用 `log_maintenance.RETENTION_DAYS`，不另立政策）、`retention_note()`、`preview_detail()`（白名单文件＋`bytes`／`modified`／`keep_days`／`expires_at`／`expired`，**只看不动文件**）；`_SECRET` 增加 URL 查询参数分支（`?api_key=…`／`&token=…`／`?signature=…` 这类异常 URL 参数一并按值脱敏）。
- `model_diagnostics.py`（L1）新增 `_scrub()`：`response_meta` 的字符串与 `context` 的每个值落盘前都过一遍 `redact`——服务端回显的凭据不会变成诊断副本；正文仍不落盘（原有白名单不变）。
- 未新增顶层模块／裸 `json.loads`／`skipTest`；未新增删除路径（保留期限只显示，实际轮转／删除仍归 `log_maintenance`），故不触发 §5「删除语义」。

## 契约变化与同步
- `model_secrets.load`／`save`／`clear`／`path`／`redacted`／`name_for`／`migrate_legacy_env` 全部不变；新增 `diagnose`／`verdict`／`looks_like_blob` 与常量。
- `diagnostic_capture.preview()`／`export()`／`export_candidates()` 行为不变（`preview` 仍返回路径元组）；`export` 仍拒绝含受保护名或仍含凭据形态的文件；新增 `redact`／`preview_detail`／`retention_note`。
- `model_diagnostics.event` 的输出字段不变，只对 `context`／`response_meta` 的字符串做脱敏（既有断言 `response_id=='req_safe_001'` 等照旧通过）。
- 新增同层 import：`diagnostic_capture → log_maintenance`、`model_diagnostics → diagnostic_capture`（都是 L1→L1，不算越层）；架构门禁 312/312、`_layers.py` 与 `架构统一基数.json` 无需同步。

## 测试（`tests/test_secret_status_diagnostics.py`，13 条）
- 状态：缺文件／空名字 → `unconfigured`；损坏文件与空文件 → `corrupt`（不是 `unconfigured`）；带 DPAPI 头的密文但解不开 → `other-user`；正常 → `ready` 且返回值里搜不到密钥明文；五种状态文案互不相同。
- 合成：`verdict(..., error_class='auth')` 在本机 `ready` 时给 `auth`（文案与「没配」不同），在本机没配时仍报本机原因。
- 诊断预览与保留：`preview_detail()` 列出白名单文件与 `keep_days == log_maintenance.RETENTION_DAYS`；把 mtime 拨到 35 天前 → `expired=True` 但文件仍在（只报告不删）。
- 不泄露：异常 URL 参数（`?api_key=sk-live-abc&…`、`?signature=S3CR3T&…`）导出后原值消失、出现 `[已脱敏]`；白名单外的项目正文（`projects/第1集/script.txt`）不进诊断包；`record` 的 `context` 里回显的 `api_key=sk-echoed-123`、`response_meta` 里塞的 `secret=leak-me` 落盘后都已被替换。

## 边界
- `other-user` 与 `corrupt` 的判定用密文头做启发式：**头对得上但解不开**一律当「当前用户解不开」，所以「恰好头部完好、中段被截断」的坏文件会被报成 `other-user`；这不是解密成功，只是把可行动作（重新保存）指向同一处，绝不当成 `ready`。
- `diagnose`／`verdict` 是纯读，不写文件、不发请求、不落日志；`verdict` 的鉴权判断依赖调用方已经分好的 `error_class`（本次未改 `pet_agent.classify`／`model_router.classify` 的分类规则，只做合成）。
- `preview_detail()` 只显示保留期限，**不执行删除**；真正的轮转／超期清理仍由 `log_maintenance.launch_cleanup` 负责（本轮未改其政策）。
- 响应正文与安全诊断本来就分区：正文在项目目录、诊断只写 `程序/logs`；本轮新增的是「回显防漏」加固，不是新的分区机制。
- 本轮**没有**读取任何真实明文密钥：测试全部用假 `PROTECTOR`；`diagnose` 只在本地用它自己的 `PROTECTOR` 验证能否解密。

## 全量判定
- 1371 − last_full_safe_all_round(1370) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径／Tk 控件生命周期／删除语义／层级登记表；改的是 L1 密钥与诊断层）。
- 复用检查：`.git/full-safe-receipts.json` 最近绿凭据为 round=1370、tree=4a7be90a…（2026-10-12，7 日内），但本轮改了 `model_secrets.py`／`diagnostic_capture.py`／`model_diagnostics.py` 并新增测试，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：待收尾补记。

## 提交
- 本轮改动：`程序/model_secrets.py`、`程序/diagnostic_capture.py`、`程序/model_diagnostics.py`、`程序/tests/test_secret_status_diagnostics.py`（新）、`程序/tasks_round/tasks_round_1371_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`。
- 内容提交：待收尾补记（只含 `程序/model_secrets.py`／`程序/diagnostic_capture.py`／`程序/model_diagnostics.py`／`程序/tests/test_secret_status_diagnostics.py`；未含主树他人已暂存的 `程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）。
- 提交状态：待收尾补记。
