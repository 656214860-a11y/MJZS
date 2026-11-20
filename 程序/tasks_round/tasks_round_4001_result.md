# R4001 结果文件：DOC-T9A 专题九「账户、会员、设置、模型管理的页面交互」盘点
<!-- round-evidence: {"commit_base": "5b23275a", "credential_hits": 0, "evidence_sha256": "456843586b0ed4ea", "exit": 0, "failed": 0, "passed": 0, "round": 4001, "tests": "docs-only"} -->

## 三问

1. **本轮类型**：只读诊断轮（§3.5）。不改任何 `.py`/`.pyw`、不搬目录、不删文件；新增盘点报告与本结果文件两个 `.md`。
2. **测试跑了吗、三个基线**：只跑任务卡验收命令 `python -B -m unittest tests.architecture.test_layers tests.architecture.test_structure -v`，54 条全过（架构门禁当轮实际数 54，失败集合为空；输出末尾 `{"ok": true, "finding_count": 0}`）。默认冒烟基线不适用（只读诊断轮默认不跑测试，本卡未要求）；全量基线不适用（本卡未要求，欠账口径以 `full-safe-receipts.json` 为准，本轮不产生新欠账）。
3. **欠账少了吗**：无关。只读盘点不消账也不欠新账；盘点报告 §5 列了 5 个待主控决策的问题。

## 改动文件

- `tasks_round/专题九账户会员设置模型管理盘点报告.md`（新增）：六块结构——范围、事实表 31 行（每行带 `文件:行号`）、现有文档写到哪了、文档和代码对不上的地方 6 条、给主控的问题建议 5 条（含可选方案与建议）、读过的文件清单。
- `tasks_round/tasks_round_4001_result.md`（新增，本文件）。

## 验收命令结果

- `python -B -m unittest tests.architecture.test_layers tests.architecture.test_structure -v`：Ran 54 tests in 56.218s，OK，`{"ok": true, "finding_count": 0}`。
- `git status --short` / `git diff --stat`：除上述两个新增 `.md` 外无其他改动；`.py`/`.pyw` 与既有文档零改动。

## 未核实项（不猜）

- `app.py:1345`「设置」窗是否存在活动调用方（疑似遗留兜底路径：云端桌面注入 `cloud_video.settings_window`、本地走 `local_video.settings_window`）。
- 账号页「推荐模型线路」卡片（§7.9.7／R1925 实现记录有，当前 `ui/desktop_account_page.py` 无 `providers`/「线路」UI）被移除的具体轮次与是否有意。
- `project_settings_dialog.py` 是否完全无生产调用点（仅在死代码审计名单出现）。
- 「所有导出路径都过 `account_blocked` 闸」未逐点核实，只确认闸函数存在且注释注明导出用途。

## 盘点要点摘要

- 「00 会员账户」页按会话状态整页两态：已登录（状态卡＋续签/退出＋兑换码＋密码/设备/导出/注销四弹窗）与未登录（四视图共享表单：密码登录/注册/验证码/重置）。
- 登录闸只拦 `SIGNED_OUT`（全屏覆盖），`VALID/GRACE/LOCKED/CLOCK_SUSPECT` 先进主界面；收费页经侧栏锁图标＋整页替换卡拦截，阶段启动经 `stage_gate`，导出经 `account_blocked('delivery')`；免费范围＝前两阶段＋站点页＋账号页。
- 设置类窗口 13 扇（对照 L4 §1.2 P7）：「设置」hub 七格只管三虎；模型管理与各 API 设置窗按域入口进入，没有一扇从 hub 进；生效时机分立刻/新任务/下次开麦/重启照办四类。
- 模型管理操作齐备：增（新建＋保存、密钥 .env 名或 DPAPI 直输）、切（三虎右键档位/三虎模型配置四维/共享输入框阶段模型——三路语义不同）、测（五维探针只提示不禁用、设置窗各自测试连接）、删（确认框列 SKILL 预设与阶段引用，.env 密钥不动）。
- 07 册设计层完整（§7.9 契约/状态机/决策台账），但四域均无「页面交互」小节；发现 6 条文档与代码不符（含「推荐模型线路」卡片疑似已移除）。
