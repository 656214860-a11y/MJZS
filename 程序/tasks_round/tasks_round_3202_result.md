# R3202 结果（零依赖边界与媒体预览任务书 M7：登录后首次配置引导）
<!-- round-evidence: {"commit_base": "f092c36c", "credential_hits": 0, "evidence_sha256": "9162ac0fdc20baee", "exit": 0, "failed": 0, "passed": 26, "round": 3202, "tests": "run_selftests.py -k test_login_gate test_pet_login_quiet"} -->

- 轮次类型：功能轮（任务书 M7；实领 **R3202**，分支 `codex/wip-R3202`）。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮：登录闸通过后模型池为空时打开既有模型管理并给一行说明。
2. **测试跑了吗、三个基线过了吗？** 跑了。冒烟 9/9；`run_selftests.py -k login` 26 条 0 红（`test_login_gate` 新增 `ModelGuideTests` 3 条：空池开门＋状态行、有模型不开、未过闸不开）。
3. **欠账少了吗？** 减少：新账号登录后不再是「发了请求才撞到没有可用模型」，引导到唯一配置入口。A7（内置默认模型／试用额度，依赖 A4）仍登记在 `维护记录/优化待办队列.md`，不在本任务书范围。

## 本轮改动

| 文件 | 改动 |
| --- | --- |
| `ui/desktop_login_gate.py` | `_login_gate_passed` 末尾挂 `_guide_first_model_setup()`：读 `model_pool.raw()['models']` 判空（空 dict／缺键／读不出来都算「要引导或读不出」——读不出按已有处理不拦登录），空则 `status` 置一行说明并经 `self.pet.open_model_manager()` 打开既有模型管理；异常吞掉不穿透登录后续。 |
| `tests/test_login_gate.py` | 新增 `ModelGuideTests` 3 条，复用既有闸门登录流（`account_use_code_button`→`account_login_button`）与 `model_pool.raw`/`pet.open_model_manager` 补丁面。 |

## 决策与边界

- **「模型池为空」＝存储区 `models` 为空**：`pool()` 有出厂兜底与桌面引擎补位，永不真空；用户「从未配过模型」的判据取 `raw()['models']`，与「填入 key 后可发起一次模型调用」的验收口径一致。
- **不另建向导**：只调用已有 `pet.open_model_manager()`（模型池＋API 配置唯一入口），一行说明走既有状态栏。
- **密钥边界**：本函数不读不写密钥；密钥仍只经模型管理 → `model_pool.env_file`/本机加密通道，测试断言里也不出现密钥形态（`test_secret_sink_audit` 不受影响）。
- **不实现内置默认模型／试用额度**：A7 依赖 A4，仍登记待办。

## 验证

- `smoke_test.py`：9/9。
- `run_selftests.py -k login`：26 条 0 红（含新 3 条）。
- 密钥不出现在配置／日志／结果文件：本函数不写任何文件；`test_secret_sink_audit` 在全量统一验。

## 遗留

- M8 收尾：任务完成文件＋预案现状更新。
