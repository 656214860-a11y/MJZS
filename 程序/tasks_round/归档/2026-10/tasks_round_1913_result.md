# R1913 功能轮结果：会员闸门总开关默认打开

- 改动：`entitlement_service.GATE_ENFORCED` 由 False 改为 True，并更新注释；付费阶段（`pet_bus.STAGES` 前 2 个之外）在未登录、过期、时钟异常时拦截新生成。
- 契约变更：`tests/test_account_client.py` 的 `test_switch_off_only_evaluates_without_blocking` 改名为 `test_switch_on_by_default_and_off_only_evaluates`。默认值断言由「关」翻为「开」，显式 `enforce=False` 时「只判定不拦截」的断言保留。其余断言未动。
- 验证：经 gui_hidden 跑 `run_selftests.py -k account_security account_client account_page account_entry entitlement lease`，87 条全绿。未跑全量、未跑架构门禁。
- 风险：客户端仍指向测试服 `https://8.138.223.126`（自签证书、IP）。测试服不可用时，免费 2 个阶段之外无法新生成。回滚：把 `GATE_ENFORCED` 改回 False。
