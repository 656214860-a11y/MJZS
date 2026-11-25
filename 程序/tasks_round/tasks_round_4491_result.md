# tasks_round_4491_result — UX-LOGIN-CLEAN 登录页极简居中登入器重构
<!-- round-evidence: {"commit_base": "b52fdd59f", "credential_hits": 0, "evidence_sha256": "66919d6e90cc9b45", "exit": 0, "failed": 0, "passed": 89, "round": 4491, "tests": "run_selftests.py -k login_gate account_page account_inputs account_entry"} -->

- 本轮属于 §3.1 功能轮（任务卡 `UX-LOGIN-CLEAN`，波次 `W2`，含 §16.3 交互规范同步与规则 35 GitHub 复用评估留痕，基准 `master` `b52fdd59f`）。
- 改了什么：采用用户确认的方案 A（零新增 pip 依赖、零新建 `.py` 模块），将 GitHub 成熟开源 Tkinter 极简登入器架构移植到现有 `ui_widgets`/`ui_tokens` 体系——登录闸与「00 会员账户」未登录态共用居中定宽单卡（`DESKTOP_LAYOUT['login_gate_width']`）、顶部等宽双段式胶囊页签（`Selected.RailIcon.TButton` / `RailIcon.TButton`，不再置灰当前页签）、精简四视图短标题、内联验证码行（左框右发码钮同行）、输入框下方／主按钮上方的固定提示位、全宽强调色主按钮（每屏唯一 `Tokens.Primary.TButton`）与单行底部极简文字链接栏；并精简 `EmailInput` 后缀定宽（`CHAR_WIDTH['xl']`）及 `PasswordInput` 无框文字显隐钮（`显示`/`隐藏`，`Tokens.Text.TButton`）。同步 `docs/specs/05_UIUX与交互规范.md` §16.3。
- 测试跑了吗、三个基线过了吗：跑了。卡面两条验收命令均 100% 全绿、退出码 0、0 跳过——定向 `run_selftests.py -k login_gate account_page account_inputs account_entry`（89 条用例全部通过，0 红，0 跳过）；全量架构门禁 `smoke_test.py --architecture`（708 条 OK）。默认冒烟（无参 `smoke_test.py`）与全量安全自检（`--all --safe`）未单跑（按分支车道规则不累计，卡面未要求）。
- 欠账少了吗：无新增欠账；`AccountPageMixin` 类行数由 599 行降至 464 行（上限 600），`ui/desktop_account_page.py` 整文件 914 行（上限 1000），单函数最长 56 行（上限 150），`STYLED_LABEL_CAPS` 精确维持 4 / 1。

## 规则 35：GitHub 成熟方案复用评估与取舍

- **候选开源参考**：
  1. `TheRustifyer/Login_Register_Screen`（MIT，纯 Tkinter OOP 单容器登录／注册切页架构）；
  2. `cfunkz/CustomTkinter-Login-Registration`（单容器多帧切换 Login／Register／Reset 模式，避免反复销毁重建窗口）；
  3. `rdbende/Sun-Valley-ttk-theme`（MIT，Win11 极简居中登录卡片层级与表单对齐规范）。
- **取舍结论（方案 A，用户已确认）**：`tests/architecture/test_dependency_whitelist.py` 硬锁定 8 个生产依赖包，且应用控件／主题／圆角已收口在 `ui_widgets`/`ui_tokens`/`ui_rounded`。本轮零新增第三方包，直接移植上述方案的「居中定宽单卡＋等宽双段胶囊页签＋内联验证码行＋全宽强调色主按钮＋单行底部极简链接」结构，完整保留既有 `account_controller`/`account_client`/`lease_verifier` 协议与全部 25 个 `account_*` 控件契约。

## 改动清单（文件:行号）与门禁核实

- `程序/account_inputs.py`（L5–L28、L68–L75，总计 108 行）：引入 `CHAR_WIDTH`；`PASSWORD_SHOWN_ICON, PASSWORD_HIDDEN_ICON = '隐藏', '显示'`；`EmailInput.suffix` 固定 `width=CHAR_WIDTH['xl']`；`PasswordInput.toggle_button` 改为 `width=0, style='Tokens.Text.TButton'`。
- `程序/ui/desktop_login_gate.py`（L17、L49–L55，总计 177 行）：精简 `LOGIN_GATE_NOTE`；`show_login_gate` 顶部品牌标题与副标题居中对齐，保持无 `ui_widgets` 同层边、`STYLED_LABEL_CAPS` 精确 1 处（L51 `APP_NAME`）。
- `程序/ui/desktop_account_page.py`（L27–L28、L50、L652–L913，总计 914 行，`AccountPageMixin` L200–L663 共 464 行）：
  - 精简 `LOGIN_VIEWS = {'pw': '欢迎登录', 'reg': '创建新账号', 'code': '验证码登录', 'reset': '找回密码'}`；
  - `_account_login_form` 改为 3 列居中网格容器（中列 `minsize=DESKTOP_LAYOUT['login_gate_width']`），收束未登录态卡片宽度不再拉满宽屏；
  - `_build_login_form` 收薄为薄委托，拆出模块级函数 `_auth_field_label`、`_auth_code_row`、`_auth_pw_view`、`_auth_reg_view`、`_auth_reset_view`、`_login_code_view`、`_auth_kit`、`_build_auth_card`（单函数 ≤ 56 行、参数 ≤ 5 个）；
  - `STYLED_LABEL_CAPS` 精确保持 4 处（L309、L344、L388、L864），新增字段标签全部使用 `style='Muted.TLabel'`。
- `程序/docs/specs/05_UIUX与交互规范.md`（L313）：同步 §16.3「登录面板」布局契约。
- `程序/tests/test_login_gate.py`（L112–L163）：新增 `test_gate_auth_card_segmented_tabs_full_width_primary_and_inline_code_row`。
- `程序/tests/test_account_page.py`（L335–L355）：新增 `test_signed_out_login_card_is_compact_and_segmented`。
- `程序/tests/test_account_inputs.py`（L91–L105）：新增 `test_password_toggle_uses_clean_text_and_email_suffix_is_compact`。

## 先红 → 后绿验证记录

### 改前先红证据（仅新增测试、未改生产代码）

命令（工作目录 `程序`）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k login_gate account_page account_inputs account_entry`
退出码：`1`（共 89 条用例，0 跳过；5 条红均为新增 3 个测试方法及其子类继承执行，既有 84 条全绿）：

1. `test_account_inputs.PasswordInputTests.test_password_toggle_uses_clean_text_and_email_suffix_is_compact`：
   `AssertionError: 'Tokens.Secondary.TButton' != 'Tokens.Text.TButton'`
2. `test_account_page.AccountPageTests.test_signed_out_login_card_is_compact_and_segmented`：
   `AssertionError: 891 not less than or equal to 500 : 未登录页登录卡应收束在定宽居中容器内，不拉满整个宽屏`
3. `test_login_gate`（`LoginGateTests` / `ModelGuideTests` / `FirstRunMatrixTests` 三组继承运行 `test_gate_auth_card_segmented_tabs_full_width_primary_and_inline_code_row`）：
   `AssertionError: 'Tokens.Secondary.TButton' != 'Selected.RailIcon.TButton'`

### 改后验收命令输出（退出码均为 0）

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k login_gate account_page account_inputs account_entry`（退出码 `0`）：
```
共 89 条用例，39.9 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 `0`）：
```
----------------------------------------------------------------------
Ran 708 tests in 320.848s

OK
✅ 架构治理测试：tests/architecture
```

## 变更统计（`git diff --numstat`）

```
8	6	程序/account_inputs.py
1	1	程序/docs/specs/05_UIUX与交互规范.md
15	0	程序/tests/test_account_inputs.py
21	0	程序/tests/test_account_page.py
52	0	程序/tests/test_login_gate.py
247	176	程序/ui/desktop_account_page.py
5	4	程序/ui/desktop_login_gate.py
```

## 未验证项与卡外发现

- 未验证项：
  - 未在可见桌面人工目视截屏核对明暗主题观感（隐藏桌面真实 Tk 几何与样式断言已覆盖宽度、同行、上下层级、胶囊页签与主按钮铺满）；
  - 未单跑无参 `smoke_test.py` 与 `run_selftests.py --all --safe`（按分支车道规则由合并阶段统一处理）。
- 卡外发现：无。
