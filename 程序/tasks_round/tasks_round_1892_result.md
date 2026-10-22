# R1892 功能轮：侧栏「00 会员账户」入口（只读占位页）

- **本轮类型**：功能轮。用户要求“主界面的会员账户入口，左侧排 00”。
- **做法**：`PAGES` 不动（01–13 的页序号与 `pet_bus.STAGES`／`pet_state.PAGE_OF` 一一对应，14 仍是参考网站）。`desktop_page_registry` 新增 `PAGE_ACCOUNT=len(PAGES)`、`ACCOUNT_TITLE='00  会员账户'`、`page_title(index)`；账户按钮不进 `self.nav`，在侧栏里放在 01 之上。
- **改动文件**：
  - `desktop.py`：侧栏调用 `build_account_nav`；`go_page` 和 `_show_reset_page` 的高亮改调 `mark_nav`，标题改用 `page_title`；`show()` 中账户页与参考网站页共用一个“不需要项目”的分支；为首帧计时新增指标名 `page.paint.account`。`Desktop` 类的净行数不变，class-size 棘轮上限 1302 未调。
  - `desktop_project_pages.py`：新增 `build_account_nav`、`mark_nav`、`account_page`。页面只读，显示“当前状态：未登录”，以及 01/02 免登录、03 起需要试用或会员、试用 3 天、每账号 3 台电脑、离线 7 天＋3 天宽限。「邮箱登录（即将开放）」按钮禁用，不发网络请求。
  - `desktop_async_tasks.py`：页名改用 `page_title`，在账户页时不再越界。
  - 新测试 `tests/test_account_entry.py`：校验 PAGES 与页序号不受影响、按钮在 01 之上且不在 nav 里、无项目时也能进账户页、高亮切换正确、登录按钮禁用。
- **测试（本轮运行）**：
  - 经 `工作流任务\gui_hidden.py` 运行 `run_selftests.py -k account_entry ui_batch3_shell ui_batch6_pages pet_ui stage_display_boundary`，结果 ALL TESTS PASSED。
  - `unittest discover -s tests/architecture -t .` 共 394 条，其中 1 failure、1 error，两条都与本轮无关：
    - `test_skill_reference_injection`：`skills/00全流程SKILL/.../screenplay-gate-engine.md` 不在 git 跟踪内，主工作区有、本 worktree 没有。
    - `test_agents_md`：`维护记录/基准历史.json` 不在 git 跟踪内，本机也不存在。
  - 改动前，class-size 棘轮因本轮新增行数超限（1313 > 1302）；把逻辑移进 mixin 后通过。
- **断言未动**：现有测试一条未改。
- **后续**：A2 客户端（`lease_verifier`、`account_store`、`account_client`、`entitlement_service`、闸门、登录页）接入后，把占位页换成真实登录流程。
- **提交**：`R1892: 侧栏「00 会员账户」入口与只读占位页（功能轮）`，未推送；`project_status.md` 待合入 master 时补记。
