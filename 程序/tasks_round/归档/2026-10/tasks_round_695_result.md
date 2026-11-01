# R695 功能轮结果：SKILL 指令仅注入编剧

## 结果

`hollmwood_roles.run()` 已把全局节奏模板与 SKILL 指令拆开：节奏模板继续供全部角色使用；SKILL 指令只拼入编剧 system，因此初稿与导演退回后的编剧改写都生效，导演规划/审核、编辑、演员均不接收。

## 变更与边界

- `hollmwood_roles.py`：维持函数签名与 `writing_api.py` 调用形式；更新 96k 超限提示为“编剧角色 SKILL 指令”。
- `tests/test_hollmwood_roles.py`：新增严格请求级断言，确认编剧初稿及返工含 SKILL、其余全部角色不含，且全体仍含节奏模板。
- `skill_panel.py`：HOLLMWOOD 说明增加“SKILL 指令仅作用于编剧角色”。

本次改测试因契约有意变更；断言强度不降，仅改注入口径。未改注册表、产品配置字段、`writing_api` 调用形式、取消令牌、空正文重试、96k 预算、APPROVED 门禁或逐步日志。

## 三项基线

| 基线 | 结果 |
| --- | --- |
| 默认冒烟 | 8/8 通过 |
| 架构门禁 | 历史登记 101/101，本轮未改分层或架构门禁 |
| 全量回归 | 本轮 HOLLMWOOD 范围 16/16；未执行全量安全回归 |

受影响门禁 `--affected hollmwood_roles writing_api`：35/35；`-k hollmwood`：16/16，均 0 红。

[TASK_COMPLETE]
