# R2048 未授权时锁定付费页面（功能轮）

轮次类型：功能轮。日期：2026-10-25。

## 起因
用户反馈：账号未登录或授权失效（试用、会员到期）时，除了「00 会员账户」「01 剧本准备」，其余页面仍然都能进、都能用。

原因：
- 登录闸只拦 `SIGNED_OUT`（本机完全没有会话）。到期账号（`LOCKED`）、超出宽限期、时钟异常都照常进主界面。
- 付费限制只挂在 `stage_handler_registry.start()`（阶段启动）和 `account_blocked()`（成片导出）上。页面本身、页内的手动编辑和采用等按钮都不设闸。

## 用户拍板
- 「02 剧本结构」保持免费。免费阶段仍按 `FREE_STAGES`：剧本准备、剧本结构。
- 「14 参考网站」也锁住。
- 锁定方式：整页换成锁定页，侧栏条目挂锁标记。

## 改动
- `entitlement_service.py`：
  - 新增 `page_block_message(entitlement, stage, title)`：免费阶段与可用授权放行；工具页传 `stage=None`，一律视为付费页。
  - 拦截文案抽成 `_block_text`，与 `stage_block_message` 共用。`stage_block_message` 的行为不变。
- `account_controller.py`：新增 `page_gate(pages)`，一次判定授权，返回 {页序号: 原因}；总开关 `enforce` 关闭时全放行。
- `desktop_account_page.py`：
  - `page_lock_reasons()`：只在真实启动（`_require_login`）时设闸，测试宿主一律放行。
  - `locked_page(reason)`：锁定页，内容为原因加「去会员账户」按钮，原因同时写进状态栏。
  - `refresh_nav_locks()`：给侧栏被锁的页加或去 `NAV_LOCK_MARK`（`  🔒`）。当前页的锁定状态翻转时，就地重建这一页。
  - 已挂在 `_account_changed()` 上，登录、续签、兑换、退出、解绑、注销后都会刷新。会员页内登录成功后也会调一次。
- `desktop_page_nav.show()`：换页时，被锁的页改建锁定页，不再建原页面。三虎和代码内部跳页走的也是 `show()`，同样被拦。
- `desktop_login_gate.py`：启动时与登录闸通过后刷新侧栏锁标记。

## 测试
- 新增 `tests/test_page_lock.py`（7 条）：
  - 判定：免费阶段放行；付费阶段与参考网站被拦；到期文案；可用授权全开；`stage_block_message` 不变。
  - 控制器：只读一次授权；总开关关闭时全放行。
  - 侧栏：挂锁与去锁；只在翻转时重建当前页；不要求登录的宿主从不加锁。
- `tests/test_login_gate.py` 新增端到端用例 `test_unlicensed_pages_are_locked_and_unlock_after_renewal`（真实 Desktop，到期租约）：
  - 03 与 14 挂锁，02 不挂锁。
  - 14 显示锁定页，状态栏提示“试用或会员已到期”；会员页正常。
  - 换成有效租约后，14 去锁并解除锁定。
- 已有断言未动。

## 验证（本轮实跑）
- `run_selftests -k page_lock account login membership entitlement desktop_page_nav ui_edges startup`（隐藏桌面）：全绿。
- 单独跑 `test_login_gate` 7 条，含新增的端到端用例：OK。
- 默认冒烟通过。
- `--architecture` 余 3 条，与本轮文件无关：
  - `test_round_number_continuous`：合入后补记即可消除。
  - `test_script_stages_name_only_their_approved_00_references`。
  - `test_performance_history_is_declared_as_historical_only`。

## 边界与未做
- 侧栏锁标记用了 🔒 字符。没在真机上看它在侧栏字体下的显示效果。
- 页内残留的老入口（如右键菜单直接调页内动作）没有逐一排查。阶段启动仍有原来的 `stage_gate` 兜底。
- 未运行：`--all --safe`、真实界面目测。未 push。
