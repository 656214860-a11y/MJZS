# R4419：UX-L5-DIALOGS 修复（应用入口弹窗／设置弹窗／登录面板／会员界面简约布局）
<!-- round-evidence: {"commit_base": "2e77de5db", "credential_hits": 0, "evidence_sha256": "ccad19bcfa6a922d", "exit": 0, "failed": 0, "passed": 157, "round": 4419, "tests": "run_selftests.py -k login_gate account_page account_entry pet_settings desktop_compact_layout"} -->

轮次类型：功能轮（§3.1）。测试跑了（先红后绿）；三个基线：默认冒烟 8/8 未跑（卡面未授权该命令）；架构门禁当轮实测 708 条、0 红（修复后）；全量回归未跑（卡面禁全量）。欠账：无新增。

## 改动文件（本批全部清单）

四处界面的实际文件：

- 应用入口弹窗：`desktop_launcher.py`（`startup_gate`/`notify_startup_fatal` 原来走裸 `MessageBoxW`，现改走 `entry_dialog`/`entry_confirm`/`_entry_notify`）
- 设置弹窗：`ui/pet_settings_ui.py`（`open_hub` 左栏分类＋竖分隔线；保存即关闭、关闭有脏先确认）
- 登录面板：`ui/desktop_account_page.py::_build_login_form`（账号页与登录闸共用）＋ `ui/desktop_login_gate.py`（不可达提示前缀匹配修复）
- 会员界面：`ui/desktop_account_page.py`（续签唯一主按钮、低频工具文字样式、注销单独危险组、兑换改文字式）

对应测试与文档：

- `tests/test_desktop_compact_layout.py`（`EntryDialogLayoutTests`，新增 3 条）
- `tests/test_pet_settings.py`（`HubLayoutTests`，新增 5 条）
- `tests/test_account_page.py`（`test_signed_in_view_compact_contract`，新增 1 条）
- `tests/test_login_gate.py`（`test_gate_form_compact_contract`，新增 1 条；另修本用例自身统计口径）
- `docs/specs/05_UIUX与交互规范.md`（新增 §16 REQ-UI-L5-1：通用版式＋保存/关闭统一规则＋四处落点）
- `tasks_round/tasks_round_4419_result.md`（本文件）

## 缺陷复现方式与改前红

定向命令（原样）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k login_gate account_page account_entry settings desktop_compact_layout`

改前（只写了测试、未动产品）红 20 条（6 个文件有红，其中 `test_gate_form_compact_contract` 按三个测试类重复计）：

- `test_desktop_compact_layout` 3 红：`AttributeError: module 'desktop_launcher' has no attribute 'entry_dialog'`／`'entry_confirm'`（入口弹窗不存在——缺陷本义）。
- `test_pet_settings` 4 红：`unexpectedly None : REQ-UI-L5-1：分类列收进左侧一列`；`1 is not false : REQ-UI-L5-1：保存＝写入并关闭`；`module 'ui.pet_settings_ui' ... does not have the attribute 'ask_confirmation'`（×2）。
- `test_account_page` 1 红：`'Tokens.Primary.TButton' == 'Tokens.Primary.TButton' : 「兑换」是次要入口，不占主按钮位`。
- `test_login_gate` 12 红：`test_gate_form_compact_contract` ×3 类——主按钮统计未过滤未映射视图，误数出 `['登录','注册并登录','登录','重置密码']`（测试写法 bug，已在测试内修 `winfo_ismapped`）；**基线红** `test_gate_shows_unreachable_prompts_with_retry` [network/service_timeout/cert_error] ×3 类＝9 条：`闸没有给出服务不可达的提示`——`fail()` 经 `with_help_hint` 给提示追加「；查看帮助：环境类错误指引 · 账号服务不可达」后缀（`desktop_account_page.py:699` + `ENV_HELP_PAGES` 含 network/service_timeout/cert_error，`desktop_account_page.py:138`），`desktop_login_gate._arm_gate_unreachable_notice` 的 `text in unreachable` 精确匹配永不命中，`gate_notice` 永不显示。属登录面板错误提示机制本身、且验收要求该文件全绿，纳入本卡修复。

## 改动点（文件:行号）

- `desktop_launcher.py:124-183`：新增 `entry_dialog`（BaseDialog＋DescriptionBlock 单列说明＋Primary/Text 两键）、`entry_confirm`（注入 `confirm_safe_start(ask=)`，主键→Win32 `_IDYES`=6、次键/Esc/关闭→0）、`_entry_notify`（FATAL 单列诊断＋「退出」主键）；`launch()`：`startup_gate(ask=entry_confirm)`、FATAL 先试 `_entry_notify` 失败回退 `notify_startup_fatal`。
- `ui/pet_settings_ui.py:159-199`：新增 `save_and_close`/`_fields_snapshot`/`hub_dirty`/`request_close`（fields、picked 变量快照判脏；`ui_widgets.ask_confirmation` 复用统一确认窗）；`open_hub`（`ui/pet_settings_ui.py:241-284`）：左栏 `_pet_nav`＋竖 `ttk.Separator`＋右侧 `stack`，底栏「关闭（左）／保存（右，Primary）」不变；Esc 与「关闭」同走 `request_close`。
- `ui/desktop_account_page.py:435-436`（退出登录→Text）、`453-463`（工具三键→Text；「注销账号」→Danger 单独一组）、`652`（「兑换」→Text）、`749-754/786-787/845-846`（忘记密码／用验证码登录／返回密码登录→Text）。
- `ui/desktop_login_gate.py:91-95`：不可达提示改前缀匹配（兼容「（N 秒后可重试）」与「；查看帮助…」后缀）。

## 改后输出（尾部原文）

定向：`共 263 条用例，131.5 秒；0 个文件有红 … ALL TESTS PASSED`，退出码 0。
架构门禁：`Ran 708 tests in 281.996s / ✅ 架构治理测试：tests/architecture / OK`，退出码 0。

## 契约变更注明

设置窗「保存」语义由「写入并留在窗内」改为「写入并关闭」（卡面要求；§15.2 模型管理页同规则）。既有断言 0 条删改：batch7 的「保存在关闭右＋minsize 可见」断言保留原样通过；分页按钮样式断言（Selected=Primary、其余 Secondary、管理键 Secondary）原样通过；仅新增用例覆盖新契约。既有账号/登录用例未改断言，`test_gate_form_compact_contract` 只统计已映射视图内的主按钮。

## 三个基线数

- 默认冒烟基线：8/8——未跑（卡面禁止默认冒烟），未核实当前值。
- 架构门禁：当轮实测 708 条。改后 0 红；中途一轮 3 红全为本轮改动引入（LR-06 私有访问 ×2、`desktop_launcher.py` 数字 padding ×2、`AccountPageMixin` 604>600），已按门禁口径修复（公开接口 `APP_NAME`/字面值 6、`SPACING['none']`、压缩工具卡为 599 行）并复测绿。改前基线：全绿（本树历史）。
- 全量回归/欠账：未跑全量（卡面禁止）；`full-safe-receipts.json` 未核实。

## 框架评估结论（一页，「建议，待确认」按推荐执行）

sv-ttk（rdbende/Sun-Valley-ttk-theme）：MIT 许可、纯 Tcl/PNG 主题包，体积百 KB 级。评估：①许可证友好但属新增依赖，`维护记录/依赖白名单` 未收录；②打包需随包附带 theme 目录并新增打包与隐藏桌面测试回归；③现有 `ui_tokens`/`ui_widgets` 已注册 `Tokens.Primary/Secondary/Text/Danger.TButton` 与 BaseDialog/Card 全套语义组件，本卡所需「强调色主键＋文字式次键＋危险键」全部现成。结论：**不引入任何第三方 ttk 主题库**，四处布局全部复用现有 ui_widgets/ui_tokens（与卡面硬红线一致）。未新增依赖、未动白名单。

## 未验证项

- `entry_confirm`/`_entry_notify` 的 `parent=None` 分支（真实启动预 Tk 环境）未在测试里演练——隐藏桌面测试覆盖了 `parent=` 分支；真实启动路径依赖 Tk 可用性，失败回退 MessageBoxW。
- 窗口三档宽度不溢出：仅在 minsize 下断言动作区不越界（既有 batch7 断言＋新 nav 结构），三档人工目视未做。
- 会员「用量一块」「证书到期告警位」沿用既有 `membership_view`，本轮未改（卡面接线点保留）。
- `entry_dialog` 的图标/告警级视觉未做（`flags` 仅保调用形态）。

## 卡外发现（只记录，不修）

- `test_gate_shows_unreachable_prompts_with_retry` 在基线上即红（根因见上），本轮已随登录面板修复转绿。
- GUI 令牌被其他会话全量自测占用时，定向 Tk 测试会等 60 秒后整体推迟（`[GUI_DEFERRED]`），需错峰重跑——属基础设施现状。

## 被拒绝的命令原文

- `Get-Content -Encoding UTF8 "C:\Users\LAIBIAO\AppData\Roaming\devin\cli\summaries\history_9a19a355409e4bcb.md" | Select-String -Pattern "reject|拒绝|denied|sleep|Start-Sleep" -Context 2,2`（读会话摘要文件，被拒；未重试）
- 早前一次 GUI 令牌等待期间的 sleep/轮询命令被拒（原文不在当前上下文可见，未能逐字恢复）；前一线程另有 4 次早期调用被拒（原文同不可逐字恢复）。

## 「建议，待确认」项

无新增：sv-ttk 评估按推荐执行并完成（结论不引入），无其他待确认项。

## git diff --numstat（提交前原文）

```
69	3	程序/desktop_launcher.py
27	0	程序/docs/specs/05_UIUX与交互规范.md
28	0	程序/tests/test_account_page.py
66	0	程序/tests/test_desktop_compact_layout.py
22	0	程序/tests/test_login_gate.py
59	0	程序/tests/test_pet_settings.py
16	7	程序/ui/desktop_account_page.py
2	1	程序/ui/desktop_login_gate.py
66	16	程序/ui/pet_settings_ui.py
```

提交哈希：（提交后补记）
