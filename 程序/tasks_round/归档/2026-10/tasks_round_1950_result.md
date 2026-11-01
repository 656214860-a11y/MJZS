# R1950 功能轮：版本更新提示（客户端）

## 范围
- 新增 `update_notice.py`（L1，纯判定）：宽松版本比较（`0.6-20260918`、`V0.7` 都能比），三种状态 none／soft／hard，下载链接只收 https。
- `account_controller.check_update`：联网读 `/v1/meta`，返回判定结果与 `proactive`；软提示同一版本只主动提示一次（`account_store.update_seen/mark_update_seen`，退出登录保留）。
- `desktop_account_page`：账号页顶部常驻「发现新版本／必须升级」卡片（有链接带「去下载」）；`start_update_check` 首帧后单独排程（`desktop_automation_tick`），不动续签流程；续签遇 `client_too_old` 时重新检查。
- 架构登记：`tests/architecture/_layers.py` 把 `update_notice` 登记为 L1。
- 服务端（独立仓库 `D:\漫剧服务端`）同步提交：`/v1/meta` 下发 `latest_version`／`download_url`／`release_notes`，静态页 `/download`；pytest 88 项通过。

## 验证
- `run_selftests.py -k test_update_notice test_account_client test_account_page test_account_entry test_account_security test_desktop_automation`（经 `gui_hidden.py`）全绿，新增 `tests/test_update_notice.py` 5 条。
- 架构目录 394 条：剩 4 红，均非本轮造成——`PetVoiceMixin` 行数（R1945 分支已修）、`test_agents_md` 1 条、`test_coverage_baseline` 2 条；本轮新增的 `test_layers`／`test_service_return_contract` 登记红已清。
- 断言未动；未跑 smoke 与 `--all --safe`；未在测试服手工验证（需把 `MJ_LATEST_VERSION` 调高后打开客户端看提示）。
- 三虎暂无单独提示，只有状态栏与账号页；一键升级不在本轮范围。

## 提交
- 功能提交 `3cccb257`（分支 `codex/wip-R1950`）。
