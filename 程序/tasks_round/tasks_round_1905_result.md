# R1905 功能轮：账户会员客户端安全对抗检查（设计文档 §8）

- **本轮类型**：功能轮。按服务端会话（`local_4c2dbe9b-…`）的请求，对照 `说明/账户会员云端设计.md` §8 逐条检查客户端，补齐缺口并写对抗测试。分支 `claude/account-security`，从 master f91edfbc 开出。
- **三问**：
  1. 做了什么：逐条检查 8 项，发现 3 个缺口并修复（成片导出不过闸门；服务端原文提示可能带出邮箱或令牌；后台工作函数抛错时异常原文会进诊断记录）；新增 `tests/test_account_security.py`，共 31 条。
  2. 怎么验证：新测试、账号相关选测、受影响冒烟、架构门禁，结果见下文。
  3. 还差什么：第 8 条服务端吊销需在测试服用真实账号走一遍；以及下文「残留风险」。

## 改动
- `desktop_media_pages.py`：后期剪辑页「按平台导出」先调用 `self.account_blocked('delivery')`，拦截时不导出。核实结果：这个导出原先不经 `stage_handler_registry.start()`，也不过闸门。「质检与交付」页（`delivery()`）本身只有导入、校验、商用资料、版本、目录按钮，没有导出动作。
- `desktop_account_page.py`：新增 `account_blocked(stage)`，供不经 `start()` 的付费动作使用；拦截时把原因写进状态栏并返回 True；总开关关闭时一律放行。
- `account_client.py`：`_failure` 对未登记错误码使用的服务端 `message` 先做遮蔽：邮箱替换为「[邮箱已隐藏]」，24 位以上形似令牌或租约的长串替换为「[已隐藏]」。已登记错误码仍用本地文案。
- `account_controller.py`：新增 `_run(work, done, label)`，原有 5 处 `_submit` 改走它。工作函数意外抛错时，转成 `client_error` 失败结果，提示里只保留异常类型名，原文不交给后台任务的诊断记录。
- 没有新增模块；生产代码没有新增 `json.loads`（新的 `json.loads` 只在测试里）。

## §8 逐项对照
| # | 项 | 结论 | 测试 |
|---|---|---|---|
| 1 | 回拨或前调时钟 | 已满足 | 新增 `ClockTamperTests` 4 条（回拨到 `server_time` 之前、回拨到签发之前、前调越过宽限、前调后联网再回拨）；已有 `test_clock_rewind_is_suspect`、`test_valid_grace_locked_by_time` |
| 2 | 篡改状态文件、换用别人的文件 | 已满足 | 新增 `FileTamperTests` 4 条（改 state/plan/expires_at/did/kid 但保留原签名、改未签名字段、lease 类型不对或文件损坏、别的账号别的机器的文件）；已有 `test_tampered_payload_is_rejected`、`test_corrupt_file_reads_as_empty`、`test_signed_out_without_lease_bad_signature_or_other_device` |
| 3 | 重放与离线伪造 | 已满足 | 新增 `ForgeAndReplayTests` 5 条（攻击者私钥冒用可信 kid、测试钥签的租约过不了内置正式公钥、无签名或零签名、重放过期旧租约、退出后改服务器时间再重放）；已有 `test_unknown_kid_wrong_version_and_garbage_are_rejected`、`test_loose_padding_is_rejected`、`test_logout_keeps_clock_floor_against_replay` |
| 4 | 设备复用 | 已满足 | 新增 `DeviceReuseTests` 3 条（拷到别的机器后 signed_out、续签带的是那台机器的指纹且遇 `invalid_device` 时清会话、服务端误发原设备租约也不落盘）；已有 `test_unverifiable_or_foreign_lease_is_not_saved` |
| 5 | 闸门覆盖 | **补缺口**：成片导出 | 新增 `GateCoverageTests` 5 条（遍历全部付费阶段，手动和自动经 `start()` 均被拦、fallback 未调用；免费阶段和非阶段动作放行；登录后放行；导出经 `account_blocked`；总开关关闭不拦）；已有 `StageGateTests` 4 条。三虎经 `desktop_pet_bridge` 调 `start(trigger='auto')`，与自动路径相同 |
| 6 | 凭据不外流 | **补缺口**：服务端原文、异常原文 | 新增 `SecretLeakTests` 4 条（捕获 root 日志跑完登录、续签、兑换、设备、注销、撤销八个流程，日志、任务标签、提示、data 都不含邮箱、令牌、验证码、租约；服务端回显遮蔽；异常原文不带出；网络错误只留类型名） |
| 7 | 续签节奏 | 已满足 | 新增 `RenewalScheduleTests` 3 条（启动读本地租约不联网，首帧后 `after(RENEW_DELAY_MS)` 才启动；首次立即续签，12 小时内不重复，满 12 小时再续，每次排下一次检查；断网完全静默，其他失败只写状态栏，不弹窗） |
| 8 | 服务端吊销全部会话 | 已满足（客户端侧） | 新增 `RevokedSessionTests` 3 条（续签 401 → 清会话、signed_out、提示「请重新登录」，下一轮不再发请求；业务调用 401 → 续签一次也 401 → 只发两次请求后停；之后账号页按未登录绘制）；已有 `test_renew_rotates_and_dead_session_clears`、`test_lease_calls_renew_once_on_stale_lease` |

## 残留风险（未改，如实记录）
- `session.json` 里的 `server_time` 未签名。攻击者若同时把它改小、把本机时钟回拨到旧租约有效期内、再放回旧租约，可以通过离线闸门（时钟基线还取 `issued_at`，所以最多回到旧租约签发之后）。这是离线授权的固有局限，影响范围限于旧租约本身的有效期加宽限（最多 10 天）；联网续签时服务端按真实状态重新签发。没有为它写断言「不安全行为」的测试。
- `device_seed` 只在取不到 MachineGuid 时作兜底；同一台机器上的另一个 Windows 账号共用 MachineGuid，属于合法使用。
- 手动页面上的其他付费按钮（多数不经 `start()`）仍未逐一接入 `account_blocked`，留作后续。
- `GATE_ENFORCED` 仍为 False（用户决定正式服上线时再打开）；测试均以 `enforce=True` 运行。

## 测试（本轮运行）
- `python -B -m unittest tests.test_account_security`（经 `gui_hidden`）：31 条，OK。
- `run_selftests.py -k account_security account_client account_page account_entry copy_rules`（经 `gui_hidden`）：ALL TESTS PASSED。
- `smoke_test.py --affected account_controller account_client desktop_account_page desktop_media_pages`：通过 9 项，失败 0 项。
- 架构门禁 `python -B -m unittest discover -s tests/architecture -t .`：394 条，失败 1、错误 1，均为已知的既有失败（`test_skill_reference_injection`、`test_agents_md`），与本轮无关。
- 未运行：全量自检；测试服真实账号的吊销演练。
- **断言未动**：没有修改任何已有测试。
