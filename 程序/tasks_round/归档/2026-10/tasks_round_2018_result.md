# R2018 结果（功能轮）：强制登录进入主界面，侧栏常驻试用／会员到期摘要

## 起因
用户截图「00 会员账户」（当前状态：未登录），问：未登录是否没有限制功能；统计里看不到试用何时到期。随后要求“必须注册登录账号才能进入主界面”。

## 现状结论（改前）
- 未登录本来就拦付费阶段（`GATE_ENFORCED=True`，`stage_handler_registry` 拦 03 起）；01、02 与主窗口有意不限。
- 到期信息只在登录后、且只在「00 会员账户」页里。

## 本轮改动
- 新增 `desktop_login_gate.py`（L4，`LoginGateMixin`）：真实启动（`Desktop(..., require_login=True)`）且本机无可用会话（SIGNED_OUT）时，在主窗口上盖全屏登录页；登录成功前不启动首帧流程（不选项目、不检查更新），登录后才补做；会话被清（退出、解绑、注销、续签判死）后回到登录页。
- `desktop_account_page.py`：登录表单抽成 `_build_login_form(parent, on_success)`，账号页与登录闸共用；新增 `_account_changed()` 在退出、解绑、注销、兑换、续签后刷新到期摘要并重判登录闸；账号页规则文案改为“需登录账号后使用……”。
- `entitlement_service.expiry_summary()`：“试用至 日期（还剩 N 天）／会员至 …／已到期，请到「00 会员账户」兑换续期”；`membership_view` 未改。
- 侧栏账号入口下方常驻一行到期摘要（`membership_badge`，无内容不占位）。
- `desktop.py` 仅加基类与一处启动调用（类行数未增，仍是原有 1303>1302 旧红）；`desktop_launcher.py`、`启动漫剧制作助手.pyw` 传 `require_login=True`，启动画面在登录页出现时直接揭开。
- 已登录但到期（LOCKED／GRACE／CLOCK_SUSPECT）照常进主界面，只拦付费阶段（用户裁定）。
- 登记：`tests/architecture/_layers.py`（L4）、`维护记录/覆盖率基线.json`（64 行，模块数 315）、`architecture.md`、`runbook.md` §11 数字。

## 验证（本轮实跑）
- `test_login_gate` 10 条通过（新增：不要求登录不盖层、未登录盖层并推迟启动、总开关关闭不强制、valid／locked／grace 直进、经闸登录后撤层并启动、退出后闸回来且摘要清空，以及 expiry_summary 4 条）。
- `run_selftests -k account membership entitlement login startup_perf ui_edges desktop_layout master_update coverage_baseline layers`：除 `test_ui_edges#5/#7` 并行池 180 秒无进展超时外全绿；单独重跑 `ui_edges`＋`coverage_baseline` 120 条全绿（超时系 8 路并行负载所致，非代码红）。
- 默认冒烟 8/8；`--architecture` 仅剩 4 条旧红（Desktop 类 1303>1302、`skill_reference_injection`、`agents_md` 性能历史、轮次连续性＝本轮号未同步前的旧状态）。
- 断言未动；覆盖率基线新行 `covered=0` 为未重测值，未重跑测量工具。

## 未做／未验证
- 未跑 `--all --safe`；未用真实邮箱验证码在真机登录；`.pyw` 启动画面到登录页的衔接、窗口快捷键（Ctrl+数字）是否能穿透登录页未实机验证，也未加守卫。
- 回滚：`git revert` 本轮提交；或把 `Desktop(..., require_login=True)` 两处改回 False。
