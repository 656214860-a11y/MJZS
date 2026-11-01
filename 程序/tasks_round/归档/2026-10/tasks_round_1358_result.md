# R1358：O33 剪辑／交付统一采用版本、粗剪覆盖率与可恢复成片清单

类型：功能轮（§3.1；本项为「事实／建议」→ 实现＋回归）。承接 R1267 清单 O33（O01—O32 已完成）。中央轮次 1358（在干净 master 工作树 `o07-fullsafe-master` 领取）。本轮非五轮全量欠账点，按 O06—O48 验证策略默认只跑定向＋关联＋架构＋默认冒烟。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k test_edit_adoption test_editing_page_controller` 11/11（其中新用例 7 条）；关联 `-k test_ui_edges` 115/115、`-k test_integration` 27/27、`-k test_edit_service test_delivery_import_service test_animatic_timeline` 14/14、`-k stage_execution stage_completion final_viewer handoff delivery skill_tools engine_probe` 98/98；架构门禁 `--layer architecture --all` 312/312；`-k test_copy_rules` 14/14；默认冒烟 8/8；全 0 红。
- 欠账：O33 关闭，清单剩 O34—O48；1358 − 1356 = 2 < 5，且未命中 §5（未改启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表），本轮不跑全量；下一欠账点 1361。先查无「7 天内同 HEAD:程序 内容树」绿凭据可复用需求，`full-safe-receipts.json` 最近绿全量为 1356（round=1356、tree=006d0295、4749/4749、425.3 秒）。

## 目标（R1267 清单 O33）
- 证据：`engine.py` 拼接会选择已审核且摘要匹配的版本；`desktop.py` 交付视图主要读最新版本；`engine.py` 成片、QC、manifest 分步发布。各处「最新／已审核／已采用」应区分。
- 建议：统一显式采用版本；粗剪显示已包含／缺失镜头与总时长，不让部分粗剪冒充完整成片；成片、QC、来源清单以同一发布事务或可恢复清单提交。
- 验收：最新版本失败但旧版通过、跳过未就绪镜头、发布第二文件失败、清理旧版本后，界面与实际成片来源一致；已有「跳过未验收镜头」按钮说明应保留。

## 实现（`engine.py`，L3）
- 新增采用版唯一口径 `adopted_edit_version(versions, root=None)`：已下载＋技术合格＋已验收的最后一条，且文件在、内容与验收摘要一致；返回 `(version, reason)`，`reason` ∈ `unapproved`／`missing`／`replaced`／`unreadable`；配 `ADOPT_*` 常量与 `ADOPT_REASON_TEXT`。
- 新增界面事实 `adoption_summary(root, versions)`：给出 `source`（要显示状态的那一版：有采用用采用版，没有才退回最新版）、`adopted`、`latest`、`latest_is_adopted`、`reason_text`；只给原始事实，文案留给界面拼。
- `auto_edit_ready` 与 `assemble` 改用 `adopted_edit_version`——两处「取哪一版」收敛到一份实现（错误／跳过文案原样保留，另补「视频无法读取」分支，不再让 OSError 直接上抛）。
- `assemble` 记录粗剪覆盖率 `coverage={included, expected, duration, skipped}` 写入调用方 report，并透传给 `_encode`。
- `publish_edit_bundle` 改为「先写一份可恢复清单 `edit_bundle.json`（成片名＋`master_sha256`＋`output_spec`＋qc 报告＋来源清单＋coverage＋`published_at`）一次性原子落盘，再写 `qc.json`／`edit_manifest.json` 两份索引」；新增常量 `QC_NAME`／`EDIT_MANIFEST_NAME`／`EDIT_BUNDLE_NAME`；新增只读读取器 `read_edit_bundle(out)`（无 bundle 的老成片退回两份索引并标 `legacy`）。
- `_encode(chosen, out, coverage=None)`：质检报告写入 `coverage`（`qc.json` 一并可见）。

## 实现（`editing_page_controller.py` L3／`desktop.py` L4）
- `EditingPageController.assembled_message` 变成粗剪覆盖率提示：`已包含 N/M 镜；总时长 X；已跳过 …／全部镜头已包含；成片：…`；只给 `skipped` 的老调用方仍退回原字符串（不改既有行为）；新增 `duration_text`（60 秒以上说「X分YY秒」）。
- 交付视图逐镜行改用 `adoption_summary`：状态／技术QC／验收跟着真实采用版走；最新版不是采用版时加「；最新 vY 未采用」；无采用版时写「无（原因）」；按钮「自动粗剪整集（跳过未验收镜头）」与页面说明保留。

## 验证
- `tests/test_edit_adoption.py`（新）7 条：最新失败版不顶替采用版（`latest_is_adopted` 为假、`source` 仍是采用版）；缺失／被替换文件不判采用；仅未验收报 `unapproved`；bundle 绑定成片名＋`master_sha256`＋来源清单＋coverage；删掉 `qc.json`（模拟第二份文件写失败）后仍能从 bundle 恢复来源；老索引兼容读取（`legacy`）；空目录无 bundle。
- `tests/test_editing_page_controller.py` +2 条：覆盖率消息含「已包含 1/2 镜／总时长 8秒／已跳过 …」；完整粗剪标「全部镜头已包含」。
- `tests/test_integration.py`：部分粗剪用例加断言 `report` 的 `included`/`expected`/`duration` 与 `edit_bundle.json` 的 `master`/`manifest`/`coverage`（真实 ffmpeg：3 镜 2 就绪 → master 可播、coverage 2/3）。
- `tests/test_ui_edges.py`：更新 `ApprovedVersionSourceGuardTests`——engine 两处改走 `adopted_edit_version`（`approved_versions(...)` 现场调用降为 0，只留 `adopted_edit_version` 内部一处）；desktop 须导入 `adoption_summary`。

## 边界
- 「采用」判定口径未变（`approved_versions` 的 pass＋downloaded＋qc_pass 不变），只是取到具体版本时统一走同一 helper；交接包仍按自己的口径（有已验收取最后一条、否则退最新版）——属 O34。
- `read_edit_bundle` 是给交付／离线完整性校验用的只读面，本轮无生产调用方，供 O34 接入。
- 主树环境观察（与本轮改动无关）：主树 `程序/desktop.py` 工作树为 LF，而 `.gitattributes` 钉 `程序/desktop.py text eol=crlf`，故主树 `tests/test_line_endings.ProgramTreeTests.test_the_victims_keep_their_own_line_endings` 红；改动前该文件即 LF、git status 判净，干净 master 工作树按 checkout 为 CRLF、同一用例 16/16 绿。提交后 blob 归一化，不受影响。
- 未实发模型请求、未重启应用、未真实点击界面（`test_ui_edges` 的 Tk 交付页／多页构建用例除外，已在主树通过）。
- 未命中 §5：`engine`／`editing_page_controller`（L3）、`desktop`（L4）均在分层表内；未新增顶层模块、未新增 `skipTest`、未新增裸 `json.loads` 或 L2 直写或动态导入；`desktop.py` 唯一 TODO 仍在 2753。
