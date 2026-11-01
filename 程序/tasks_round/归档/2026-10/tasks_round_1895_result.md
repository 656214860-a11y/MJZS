# R1895 功能轮：A2 桌面客户端（租约验签、本机会话、HTTP 客户端、授权判定、阶段闸门、登录页），接测试服

- **本轮类型**：功能轮。用户要求：“Start the desktop A2 client: lease_verifier, account_store, account_client, entitlement_service, the gate, and the login page, connected to the test instance.” 服务端仓库 `D:\漫剧服务端` 由服务端会话负责，本轮没有改动它。
- **三问**：
  1. 做了什么：设计文档 §4、§5、§8 的 P1 客户端全部落地，`00 会员账户` 页从占位页换成真实的邮箱验证码登录流程。
  2. 怎么验证：新增 27 条无 Tk 单测和 2 条 Tk 页面测试；在测试服 `https://8.138.223.126` 上做了真实只读联调。
  3. 还差什么：见文末「后续」。其中最重要的一项是：闸门总开关 `GATE_ENFORCED` 默认关闭，正式服上线时再打开。

## 新模块（已登记 `tests/architecture/_layers.py` 与 `architecture.md`）

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L1 | `lease_verifier.py` | 纯 Python 实现 RSA-2048 PKCS#1 v1.5 + SHA-256 验签。按完整 EM 字节比对，拒绝宽松填充；内置公钥 `k2026a`，已与服务端 JSON 核对一致。 |
| L1 | `account_store.py` | 读写 `private/账户/session.json`。读用 `agent.core.read_json`，写用 `agent.core.save`。`server_time` 只增不减；退出登录时保留 `device_seed` 和 `server_time`，用于防止回拨时钟重放旧租约。设备指纹取 `sha256(MachineGuid)`。 |
| L2 | `entitlement_service.py` | §4.3 离线状态机：valid／grace／locked／signed_out／clock_suspect，时钟容差 300 秒。免费阶段取 `pet_bus.STAGES[:2]`。 |
| L2 | `account_client.py` | 每个接口一个函数，返回 `service_contract` 结果。出站请求走 `platform_tools.open_https`，用内置自签证书钉住（`cadata`），不关闭校验。失败结果的 `data['code']` 是服务端稳定错误码，断网时为 `network`。 |
| L3 | `account_controller.py` | 编排登录、续签、退出和 `stage_gate`。先验签再落盘：验签失败或不是本机的租约，不覆盖本机已有会话；`session_invalid`、`account_pending_deletion`、`invalid_device` 清掉会话；断网保留旧租约。 |
| L4 | `desktop_account_page.py` | `AccountPageMixin`：登录表单（先发验证码，登录按钮才可用；含年满 18 周岁确认）；已登录时显示套餐、到期时间、离线可用至，提供「立即续签」「退出登录」。首帧后 3 秒开始后台续签检查，每 30 分钟一次，到期（12 小时）才发请求。 |

## 改动的已有文件

- `stage_handler_registry.py`：`start()` 入口前置 `_account_gate_error`，手动与自动一致。手动返回拦截原因；自动经 `_fail` 发出 `stage.failed`。宿主没有挂载 `account`，或闸门返回值不是字符串时，不拦截。
- `platform_tools.open_https`：新增 `method=`、`context=` 两个参数。
- `desktop.py`：类声明加 `AccountPageMixin`，只多一行 import，`Desktop` 类体行数不变。
- `desktop_project_pages.py`：删除旧的占位 `account_page`。
- `desktop_automation_tick.py`：首帧后排队续签检查。
- 台账 `维护记录/架构统一基数.json`：
  - 第一项：`account_client` 进 adopters，`entitlement_service` 进 exempt_items（纯函数，返回 `Entitlement`，不返回服务结果）。
  - 第四项：`lease_verifier.verify`、`account_client._read_json` 两处 `json.loads` 解析的是内存数据，登记为 exempt 并写明理由。
  - `tests/architecture/test_service_return_contract.py` 的采用方集合按该测试要求显式加入 `account_client`。这是棘轮登记，不是放宽断言。
- `维护记录/覆盖率基线.json`：按原 8 组定向用例重跑 `scripts/coverage_report.py` 刷新，生产模块从 300 个变为 306 个；`runbook.md` 中的口径数字同步更新。

## 闸门总开关（用户 2026-10-23 确认：保持关闭，正式服上线时再打开）

设计文档没有约定上线开关。测试服目前只有 IP 自签证书，也还没备案；如果闸门默认生效，合入 master 并打包后，所有用户从「03 初步分镜」起都会被锁住。因此本轮新增 `entitlement_service.GATE_ENFORCED = False`：判定、页面状态和续签照常运行，但不拦截付费阶段，页面会标注「测试期暂不拦截」。正式服上线时把它改为 `True`。测试用 `AccountController(enforce=True)` 显式打开开关，覆盖拦截路径。

## 测试（本轮运行）

- `tests.test_account_client`（27 条，无 Tk）：
  - 验签：篡改 payload、未知 kid、版本号不对、垃圾输入、哈希后夹带字节、错误摘要。
  - 状态机：全部状态；回拨时钟、早于签发时间、换设备、退出后重放旧租约。
  - 本机会话：会话落盘、`server_time` 单调、文件损坏。
  - HTTP 客户端：请求头、DELETE、证书校验上下文、HTTPError／426／断网错误码映射。
  - 编排：登录、续签、会话失效清除、断网保留会话、验签失败不覆盖会话、开关关闭时放行。
  - 闸门：手动、自动、非字符串结果、放行。
- `tests.test_account_page`（2 条 Tk）：发码后登录 → 已登录视图（账号、套餐）→ 退出后回到表单；登录失败时显示原因并留在表单。
- 经 `工作流任务\gui_hidden.py` 运行 `run_selftests.py -k account_entry account_client account_page ui_batch3_shell ui_batch6_pages pet_ui stage_display_boundary stage_command stage_handler animatic_scope`：全部通过。
- `smoke_test.py --affected stage_handler_registry platform_tools desktop_automation_tick desktop_project_pages`：8 项通过、1 项失败。失败的是 `test_master_skill.test_manifest_change_resyncs_master_items_and_keeps_user_extras`，在临时 worktree 中检出 HEAD（7d7a4773）复跑同样失败，与本轮无关。
- 架构门禁 `unittest discover -s tests/architecture -t .`：共 394 条，剩 3 failure、1 error，均为既有问题：
  - `test_skill_reference_injection`、`test_agents_md`：同 R1892，本 worktree 缺未跟踪的文件。
  - `test_round_number_continuous`：状态页轮次头 1892 落后于结果文件，按约定只能在 master 上同步。
- 测试服真实联调（只读，不发邮件）：
  - `meta` 返回 `kids=['k2026a']`、`min_client_version=0.0.0`，本客户端版本 0.7。
  - 伪造验证码返回 `code_invalid`（400）；伪造刷新令牌返回 `session_invalid`（401）；`devices` 用无效租约返回 `session_invalid`。
  - 证书钉住生效。
- **未运行**：真实邮箱的端到端登录（需要服务端会话从日志读出验证码）；全量测试。
- **断言未动**：已有测试的断言一条未改。改动只有两处：`test_service_return_contract` 采用方集合按其要求登记新采用方；`test_account_entry` 未改动，其中“登录按钮禁用”的断言仍然成立。

## 后续

1. 正式服上线（域名＋系统 CA、备案）时：`GATE_ENFORCED=True`，删除 `PINNED_CERT`，`BASE_URL` 改为域名。
2. 大多数手动页面按钮不经 `stage_handler_registry.start()`，目前闸门只覆盖三虎／自动路径和分镜批量。手动入口需要另开一轮统一接入。
3. 「质检与交付」的导出闸门。
4. P2 UI：设备列表与解绑、注销账号与撤销注销、数据导出。`account_client` 中对应的接口函数已经就绪。
5. 用真实邮箱做一次端到端登录。

- **提交**：`R1895: A2 桌面客户端——租约验签、本机会话、账号客户端、授权判定、阶段闸门与登录页（功能轮）`，未推送；`project_status.md` 待合入 master 时补记。
