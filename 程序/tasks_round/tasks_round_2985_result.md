# tasks_round_2985_result
<!-- round-evidence: {"commit_base": "aecb90f2", "credential_hits": 0, "evidence_sha256": "ae378f3f6805a2dd", "exit": 0, "failed": 0, "passed": 22, "round": 2985, "tests": "run_selftests.py -k ui_status"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（P0）：新增统一文字提示模块——`ui/ui_status_bus.py`（消息模型+StatusBus）与 `ui/ui_status_bar.py`（StatusBar 组件），含根 shim、L4 分层登记与定向测试。范围外未动。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；定向 `run_selftests.py -k ui_status` **22/22**；`--affected ui_status_bus ui_status_bar` **9/9**；分层+静态名门禁定向（`test_layers`+`test_static_names`）**14/14**。增量串行门禁（`smoke --gate`）一次 **900 秒超时**（日志见 GUI 长尾与 `after` 脚本残留，与 R1706/R1713 历史超时同型），已修复 StatusBar 的 after 回调泄漏（`_after` 托管+`_destroyed` 守卫）并复跑定向全绿；未再重跑 `--gate`。
3. **project_status.md 的欠账少了吗？** 未改（仅 master 可提交）；无欠账变化。

## 本轮内容

- `ui/ui_status_bus.py`＋`ui_status_bus.py`（shim）：`Message(level,text,ttl,source)` 四级消息模型（error/warning 常驻、info/success 8 秒自动消失）、`StatusBus`（线程安全 publish、UI 线程 pump、3 秒幂等合并、历史 50 条上限、expire/dismiss、订阅/退订）。API 形态借鉴 PyPubSub，零第三方依赖。
- `ui/ui_status_bar.py`＋`ui_status_bar.py`（shim）：左区常驻段（`set_segment`/`clear_segment`，EllipsisLabel 截断+悬停全文+点击命令）、右区四级消息（token 着色）、点击展开历史面板（Esc/失焦/× 收起）、100ms 心跳 pump、after 全托管防泄漏。
- `tests/architecture/_layers.py`：登记 `ui_status_bus`/`ui_status_bar` 为 L4。
- `design_tokens.md`：`color.success.subtle` 行顺带修正（去重，#DCFCE7 与代码一致）。
- 测试：`tests/test_ui_status_bus.py`（14 条纯逻辑）、`tests/test_ui_status_bar.py`（8 条真 Tk）。

## 后续

R2986 P1 剧本准备页接入+错误分级；R2987 P2 标题行删除+Token 迁移；R2988 P3 路径收敛+文案规范；R2989 收尾全量。
