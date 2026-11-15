# R2530 结果

1. 轮次类型：功能轮（工程闸门落地清单批次 2：C1／C4／C3）。
2. 测试：定向 `test_agent_doc_budget`、`test_outbound_http_authority`、`test_rule_guard_map`、`test_agents_md`、`test_keyframe_comfy`、`test_assets` 全绿；证据文件 `tasks_round/evidence/R2530.json`。先红后绿的实证：`test_agent_doc_budget` 首次运行因 `程序/AGENTS.md` 加入规则 42 后 16015 字节而红，压缩措辞到 15860 字节后绿。
3. 欠账：无新增。断言未动。

## 改动

- C1：`tests/architecture/test_agent_doc_budget.py`（体积、关键章节在前 16384 字节内、链接存在）。
- C4：调查结论——生产代码直接建连的只有 `platform_tools.py`（宿主适配层）和 `comfy_service.py`；后者迁到 `platform_tools.open_https()`；新增规则 42 与 `test_outbound_http_authority.py`（白名单仅 `platform_tools.py`，含坏样本自审）。
- C3：`scripts/rule_guard_map.py`、`维护记录/规则守卫基线.json`、`维护记录/规则守卫对照.md`（生成物）、`test_rule_guard_map.py`。原计划用文本引用扫描，误报太多（“第 30 期”“规则 12”等无关引用），改为手工登记。
- 暂无守卫的规则（上限固定、只许减少）：16、25、26、30a、32，均为流程性规则。是否降为建议由用户决定，本轮未改规则文字。
